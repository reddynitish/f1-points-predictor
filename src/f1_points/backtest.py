"""Retrospective walk-forward backtest of the frozen model over a completed season."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .experiments import config_hash, environment, git_commit
from .features import KEY, apply_qualifying_overrides
from .modeling import bootstrap_race_brier, metrics, reliability
from .predict import InsufficientHistory, predict_event

FRAMING = (
    'Retrospective walk-forward backtest run after the season was played. For each race the models were refit on '
    'earlier races only and given only information available at qualifying end. These are not forecasts that were '
    'published before each race.'
)


def top10_hits(frame, column):
    """Per race: how many of the model's ten most likely drivers actually scored points."""
    return (
        frame.sort_values(column, ascending=False)
        .groupby('event_id')
        .head(10)
        .groupby('event_id')['scored_points']
        .sum()
    )


def run_backtest(events, entries, labels, season, config, overrides=None):
    if overrides:
        entries = apply_qualifying_overrides(entries, overrides)
    rounds = sorted(int(r) for r in events.loc[events['season'] == season, 'round'])
    scored = set(labels['event_id'])
    frames = []
    for round_number in rounds:
        event_id = f'{season}-{round_number:02d}'
        if event_id not in scored:
            continue  # race not run yet
        try:
            predictions, metadata = predict_event(events, entries, labels, event_id, config)
        except InsufficientHistory:
            continue  # nothing earlier to learn from (only possible for the first race in the data)
        predictions['round'] = round_number
        predictions['training_last_event'] = metadata['training_last_event']
        frames.append(predictions)
    frame = pd.concat(frames, ignore_index=True)
    outcome = labels.assign(scored_points=(labels['race_points'] > 0).astype(int))[[*KEY, 'scored_points']]
    frame = frame.merge(outcome, on=KEY, how='inner')
    # B0 floor: ten points places spread evenly over the classified field (no information used).
    frame['p_B0'] = frame.groupby('event_id')['driver_id'].transform(lambda s: 10 / len(s))
    return frame


def summarize(frame, season, config_path):
    per_race = (
        frame.assign(
            err_B1=(frame['p_B1'] - frame['scored_points']) ** 2, err_M1=(frame['p_M1'] - frame['scored_points']) ** 2
        )
        .groupby(['event_id', 'round'])
        .agg(drivers=('driver_id', 'size'), brier_B1=('err_B1', 'mean'), brier_M1=('err_M1', 'mean'))
        .reset_index()
    )
    per_race['top10_hits_B1'] = per_race['event_id'].map(top10_hits(frame, 'p_B1'))
    per_race['top10_hits_M1'] = per_race['event_id'].map(top10_hits(frame, 'p_M1'))
    confident = frame[frame['p_B1'] >= 0.8]
    return {
        'framing': FRAMING,
        'generated_at': datetime.now(UTC).isoformat(),
        'git_commit': git_commit(),
        'config_sha256': config_hash(config_path),
        'environment': environment(),
        'season': season,
        'races': int(frame['event_id'].nunique()),
        'rows': len(frame),
        'metrics': {name: metrics(frame, 'p_' + name) for name in ('B0', 'B1', 'M1')},
        'bootstrap_M1_vs_B1': bootstrap_race_brier(frame, ['p_M1', 'p_B1'], reference='p_B1'),
        'top10_hits_mean': {
            'B1': float(per_race['top10_hits_B1'].mean()),
            'M1': float(per_race['top10_hits_M1'].mean()),
        },
        'confident_B1': {
            'threshold': 0.8,
            'predictions': len(confident),
            'scored': int(confident['scored_points'].sum()),
        },
        'reliability_B1': reliability(frame, 'p_B1'),
        'per_race': per_race.round(4).to_dict('records'),
    }


def write_outputs(frame, summary, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    columns = [*KEY, 'round', 'constructor_id', 'qualifying_rank', 'p_B1', 'p_M1', 'scored_points']
    frame[columns].sort_values(['round', 'p_B1'], ascending=[True, False]).round(4).to_csv(
        directory / 'predictions.csv', index=False
    )
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
