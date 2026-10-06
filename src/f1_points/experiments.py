"""Development model selection, frozen-config sealed evaluation and walk-forward replay."""

import hashlib
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from .features import CATEGORICAL_FEATURES, KEY, NUMERIC_FEATURES
from .modeling import (
    DEVELOPMENT_VALIDATION_SEASONS,
    SEED,
    TEST_SEASON,
    Candidate,
    apply_sigmoid,
    bootstrap_race_brier,
    candidates,
    chronological_calibration,
    fit_predict,
    fit_sigmoid,
    make_splits,
    metrics,
    race_averaged_brier,
    reliability,
)

# Complexity order breaks near-ties (within 0.0005 race-averaged Brier) in favour of simpler models.
COMPLEXITY = {'prior': 0, 'rank_logistic': 1, 'grid_logistic': 1, 'logistic': 2, 'hgb': 3}
BASELINES = {'rank_logistic': Candidate('B1', 'rank_logistic'), 'grid_logistic': Candidate('BG', 'grid_logistic')}
TIE_TOLERANCE = 0.0005


def load_dataset(directory):
    features = pd.read_parquet(Path(directory) / 'features.parquet')
    labels = pd.read_parquet(Path(directory) / 'labels.parquet')
    return features.merge(labels, on=KEY, how='inner')


def git_commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment():
    return {
        'python': platform.python_version(),
        'platform': platform.platform(),
        'scikit_learn': version('scikit-learn'),
        'pandas': version('pandas'),
        'seed': SEED,
    }


def development_predictions(rows, candidate, numeric=NUMERIC_FEATURES, seasons=DEVELOPMENT_VALIDATION_SEASONS):
    """Out-of-fold predictions for each development validation season."""
    blocks = []
    for train_seasons, validation_season in make_splits(seasons):
        train = rows[rows['season'].isin(train_seasons)]
        score = rows[rows['season'] == validation_season].copy()
        score['p_points'], _ = fit_predict(candidate, train, score, numeric)
        blocks.append(score[[*KEY, 'season', 'scored_points', 'p_points']])
    return pd.concat(blocks, ignore_index=True)


def run_selection(
    dataset_dir,
    report_path,
    config_path,
    *,
    numeric=NUMERIC_FEATURES,
    seasons=DEVELOPMENT_VALIDATION_SEASONS,
    test_season=TEST_SEASON,
    baseline='rank_logistic',
    cutoff='qualifying_end',
):
    rows = load_dataset(dataset_dir)
    rows = rows[rows['season'] < test_season]  # the sealed test season never enters selection
    started = time.perf_counter()
    results, oof = [], {}
    for candidate in candidates(BASELINES[baseline]):
        predictions = development_predictions(rows, candidate, numeric, seasons)
        oof[candidate.label()] = predictions
        per_season = {int(season): race_averaged_brier(block) for season, block in predictions.groupby('season')}
        results.append(
            {
                'candidate': candidate.label(),
                'name': candidate.name,
                'family': candidate.family,
                'params': candidate.params,
                'race_brier': race_averaged_brier(predictions),
                'race_brier_by_season': per_season,
                **{k: v for k, v in metrics(predictions).items() if k in ('log_loss', 'roc_auc', 'pr_auc')},
            }
        )
    best_score = min(r['race_brier'] for r in results)
    near = [r for r in results if r['race_brier'] <= best_score + TIE_TOLERANCE]
    chosen = min(near, key=lambda r: (COMPLEXITY[r['family']], r['race_brier']))

    chosen_oof = oof[chosen['candidate']]
    calibrated = chronological_calibration(chosen_oof)
    comparable = calibrated[calibrated['season'] > min(seasons)]
    raw_score = race_averaged_brier(comparable, 'p_points')
    calibrated_score = race_averaged_brier(comparable, 'p_calibrated')
    use_calibration = calibrated_score < raw_score - TIE_TOLERANCE

    report = {
        'generated_at': datetime.now(UTC).isoformat(),
        'git_commit': git_commit(),
        'environment': environment(),
        'duration_seconds': round(time.perf_counter() - started, 1),
        'protocol': f'expanding seasonal blocks; validate {min(seasons)}-{max(seasons)}; '
        f'{test_season} excluded from all selection inputs',
        'cutoff': cutoff,
        'validation_rows': len(chosen_oof),
        'validation_events': int(chosen_oof['event_id'].nunique()),
        'candidates': sorted(results, key=lambda r: r['race_brier']),
        'selected': chosen['candidate'],
        'tie_rule': f'simplest family within {TIE_TOLERANCE} of best race-averaged Brier',
        'calibration': {
            'compared_on_seasons': sorted(int(s) for s in comparable['season'].unique()),
            'raw_race_brier': raw_score,
            'sigmoid_race_brier': calibrated_score,
            'selected': 'sigmoid' if use_calibration else 'raw',
            'reliability_raw': reliability(comparable, 'p_points'),
            'reliability_sigmoid': reliability(comparable, 'p_calibrated'),
        },
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')

    config = {
        'frozen_at': report['generated_at'],
        'selected_from_commit': report['git_commit'],
        'model': {'name': chosen['name'], 'family': chosen['family'], 'params': chosen['params']},
        'feature_columns': list(numeric) + CATEGORICAL_FEATURES,
        'numeric_features': list(numeric),
        'baseline': baseline,
        'cutoff': cutoff,
        'calibration': report['calibration']['selected'],
        'threshold': 0.5,
        'seed': SEED,
        'test_season': test_season,
        'protocols': {
            'fixed_season': f'fit seasons 2018-{test_season - 1}; score every {test_season} race once',
            'walk_forward': f'refit before each {test_season} race on all earlier races with these frozen settings',
        },
    }
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config_path).write_text(json.dumps(config, indent=2) + '\n')
    return report


def config_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_committed(path):
    """Sealed evaluation runs only against a frozen config that is committed and unmodified."""
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', str(path)], capture_output=True)
    dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', str(path)])
    if tracked.returncode != 0 or dirty.returncode != 0:
        raise SystemExit(f'{path} must be committed unchanged before the sealed evaluation')


def frozen_candidate(config):
    model = config['model']
    return Candidate(model['name'], model['family'], model['params'])


def _calibrator(config, rows, candidate):
    if config['calibration'] != 'sigmoid':
        return None
    oof = development_predictions(rows[rows['season'] < config['test_season']], candidate)
    return fit_sigmoid(oof['p_points'].to_numpy(), oof['scored_points'])


def run_sealed_evaluation(dataset_dir, config_path, report_path, predictions_path):
    require_committed(config_path)
    config = json.loads(Path(config_path).read_text())
    rows = load_dataset(dataset_dir)
    test_season = config['test_season']
    train = rows[rows['season'] < test_season]
    test = rows[rows['season'] == test_season].copy()
    chosen = frozen_candidate(config)
    calibrator = _calibrator(config, rows, chosen)

    comparisons = {'B0': Candidate('B0', 'prior'), 'B1': Candidate('B1', 'rank_logistic')}
    for column, candidate in comparisons.items():
        test['p_' + column], _ = fit_predict(candidate, train, test)
    raw, _ = fit_predict(chosen, train, test)
    test['p_points'] = apply_sigmoid(calibrator, raw) if calibrator is not None else raw

    replay = []
    for event_id in sorted(test['event_id'].unique()):
        target = test[test['event_id'] == event_id].copy()
        season, round_number = int(target['season'].iloc[0]), int(target['round'].iloc[0])
        earlier = rows[(rows['season'] < season) | ((rows['season'] == season) & (rows['round'] < round_number))]
        p, _ = fit_predict(chosen, earlier, target)
        target['p_walk_forward'] = apply_sigmoid(calibrator, p) if calibrator is not None else p
        replay.append(target[[*KEY, 'p_walk_forward']])
    test = test.merge(pd.concat(replay), on=KEY)

    Path(predictions_path).parent.mkdir(parents=True, exist_ok=True)
    test[[*KEY, 'season', 'round', 'qualifying_rank', 'p_B0', 'p_B1', 'p_points', 'p_walk_forward']].to_csv(
        predictions_path, index=False
    )
    report = {
        'generated_at': datetime.now(UTC).isoformat(),
        'git_commit': git_commit(),
        'config_sha256': config_hash(config_path),
        'environment': environment(),
        'model': chosen.label(),
        'calibration': config['calibration'],
        'fixed_season': {
            'B0': metrics(test, 'p_B0'),
            'B1': metrics(test, 'p_B1'),
            'selected': metrics(test, 'p_points'),
            'bootstrap': bootstrap_race_brier(test, ['p_points', 'p_B1', 'p_B0'], reference='p_B1'),
            'reliability': reliability(test, 'p_points'),
        },
        'walk_forward': {
            'selected': metrics(test, 'p_walk_forward'),
            'bootstrap': bootstrap_race_brier(test, ['p_walk_forward', 'p_B1'], reference='p_B1'),
        },
        'worst_events': (
            test.assign(error=(test['p_points'] - test['scored_points']) ** 2)
            .groupby('event_id')['error']
            .mean()
            .sort_values(ascending=False)
            .head(5)
            .round(4)
            .to_dict()
        ),
    }
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    return report
