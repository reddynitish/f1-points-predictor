"""Descriptive saved-output errors and development-only fixed-setting ablations."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .features import KEY, NUMERIC_FEATURES
from .modeling import Candidate, bootstrap_race_brier, build_pipeline, race_averaged_brier


def error_analysis(frame):
    frame = frame.copy()
    frame['qualifying_band'] = frame['qualifying_rank'].map(
        lambda r: (
            'missing' if pd.isna(r) else '01–05' if r <= 5 else '06–10' if r <= 10 else '11–15' if r <= 15 else '16+'
        )
    )
    frame['error_B1'] = (frame['p_B1'] - frame['scored_points']) ** 2
    segments = {}
    for column in ('qualifying_band', 'constructor_id', 'rookie', 'qualifying_rank_missing', 'sprint_weekend'):
        if column not in frame:
            continue
        groups = []
        for value, block in frame.groupby(column, dropna=False):
            groups.append(
                {
                    'group': str(value),
                    'rows': len(block),
                    'events': int(block['event_id'].nunique()),
                    'points_rate': float(block['scored_points'].mean()),
                    'mean_probability': float(block['p_B1'].mean()),
                    'race_brier_B1': race_averaged_brier(block, 'p_B1'),
                    'driver_brier_B1': float(block['error_B1'].mean()),
                }
            )
        segments[column] = groups
    per_race = frame.groupby('event_id').agg(rows=('driver_id', 'size'), brier_B1=('error_B1', 'mean'))
    misses = frame[(frame['p_B1'] >= 0.8) & (frame['scored_points'] == 0)]
    surprises = frame[(frame['p_B1'] <= 0.2) & (frame['scored_points'] == 1)]
    columns = [*KEY, 'qualifying_rank', 'p_B1', 'p_M1', 'scored_points']
    return {
        'scope': 'Descriptive post-hoc analysis of spent 2026 rounds 1–16; no model selection or causal claims.',
        'precision': 'Committed prediction CSV probabilities are rounded to four decimals.',
        'rows': len(frame),
        'events': int(frame['event_id'].nunique()),
        'race_brier_B1': race_averaged_brier(frame, 'p_B1'),
        'uncertainty': bootstrap_race_brier(frame, ['p_B1', 'p_M1'], reference='p_B1'),
        'segments': segments,
        'worst_races': per_race.sort_values('brier_B1', ascending=False).head(5).reset_index().to_dict('records'),
        'confident_misses': misses.sort_values('p_B1', ascending=False)[columns].to_dict('records'),
        'low_probability_scorers': surprises.sort_values('p_B1')[columns].to_dict('records'),
    }


def run_ablations(rows, seasons=(2021, 2022, 2023, 2024)):
    if not seasons or any(s not in (2021, 2022, 2023, 2024) for s in seasons):
        raise ValueError('Ablation validation must stay within 2021–2024 development seasons')
    rows = rows[rows['season'].between(2018, 2024)].copy()
    rank = ['qualifying_rank', 'qualifying_rank_missing']
    driver = [c for c in NUMERIC_FEATURES if c.startswith('driver_') or c == 'rookie']
    team = [c for c in NUMERIC_FEATURES if c.startswith('constructor_')]
    specs = {
        'rank_standardized': (rank, []),
        'rank_driver': (rank + driver, []),
        'rank_team': (rank + team, ['constructor_id']),
        'rank_driver_team': (rank + driver + team, ['constructor_id']),
        'rank_driver_team_circuit': (rank + driver + team, ['constructor_id', 'circuit_id']),
        'full_v1': (NUMERIC_FEATURES, ['constructor_id', 'circuit_id']),
    }
    outputs, folds = {}, []
    for season in seasons:
        train = rows[rows['season'] < season]
        block = rows[rows['season'] == season]
        if train.empty or block.empty:
            raise ValueError(f'Missing training or validation rows for {season}')
        folds.append(
            {
                'validation_season': season,
                'training_events': sorted(train['event_id'].unique()),
                'validation_events': sorted(block['event_id'].unique()),
            }
        )
        for name, (numeric, categorical) in specs.items():
            model = build_pipeline(Candidate(name, 'logistic', {'C': 0.1}), numeric)
            transforms = model.named_steps['features'].transformers
            model.named_steps['features'].transformers = [
                (label, transformer, numeric if label == 'numeric' else categorical)
                for label, transformer, _ in transforms
                if label == 'numeric' or categorical
            ]
            model.fit(train, train['scored_points'])
            scored = block[[*KEY, 'scored_points']].copy()
            scored['p_points'] = model.predict_proba(block)[:, 1]
            outputs.setdefault(name, []).append(scored)
    return {
        'scope': 'Post-hoc development diagnostics only. No tuning, replacement model or new holdout evaluation.',
        'settings': {'family': 'standardized logistic regression', 'C': 0.1, 'calibration': 'raw'},
        'caution': 'Standardized rank diagnostic differs from frozen B1 preprocessing and regularization.',
        'folds': folds,
        'models': {
            name: {
                'numeric': specs[name][0],
                'categorical': specs[name][1],
                'race_brier': race_averaged_brier(pd.concat(blocks)),
                'rows': sum(len(b) for b in blocks),
                'by_season': {
                    str(season): race_averaged_brier(block) for season, block in zip(seasons, blocks, strict=True)
                },
            }
            for name, blocks in outputs.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, default=Path('reports/backtest-2026/predictions.csv'))
    parser.add_argument('--dataset', type=Path, default=Path('data/dataset'))
    parser.add_argument('--output', type=Path, default=Path('reports/diagnostics'))
    parser.add_argument('--ablations', action='store_true', help='requires local data; development years only')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(args.predictions)
    feature_path = args.dataset / 'features.parquet'
    if args.ablations:
        features = pd.read_parquet(feature_path)
        target = pd.read_parquet(args.dataset / 'labels.parquet')
        rows = features.merge(target, on=KEY, validate='one_to_one')
        ablations = run_ablations(rows)
        development = rows[rows['season'].between(2018, 2024)].sort_values(KEY)
        ablations['development_rows_sha256'] = hashlib.sha256(development.to_csv(index=False).encode()).hexdigest()
        (args.output / 'ablations.json').write_text(json.dumps(ablations, indent=2) + '\n')
        available = [*KEY, 'rookie', 'qualifying_rank_missing', 'sprint_weekend']
        available = [c for c in available if c in features]
        frame = frame.merge(features[available], on=KEY, how='left', validate='one_to_one')
    result = error_analysis(frame)
    result['predictions_sha256'] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    (args.output / 'errors.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f'Diagnostics saved to {args.output}; frozen models unchanged')


if __name__ == '__main__':
    main()
