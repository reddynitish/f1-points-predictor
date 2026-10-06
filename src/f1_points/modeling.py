"""Event-grouped splits, baseline/model pipelines and race-level metrics (milestones C and D)."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

SEED = 42
DEVELOPMENT_VALIDATION_SEASONS = (2021, 2022, 2023, 2024)
FIRST_SEASON = 2018
TEST_SEASON = 2025
LOG_LOSS_EPS = 1e-15
RANK_FEATURES = ['qualifying_rank', 'qualifying_rank_missing']
GRID_BASELINE_FEATURES = ['grid_position', 'grid_pitlane']


def make_splits(seasons=DEVELOPMENT_VALIDATION_SEASONS):
    """Expanding seasonal blocks: train on every earlier season, validate on one whole season."""
    return [(list(range(FIRST_SEASON, season)), season) for season in seasons]


def select(rows, seasons):
    return rows[rows['season'].isin(seasons)]


@dataclass(frozen=True)
class Candidate:
    name: str
    family: str
    params: dict = field(default_factory=dict)

    def label(self):
        return self.name + ('' if not self.params else ' ' + ','.join(f'{k}={v}' for k, v in self.params.items()))


def candidates(baseline=None):
    """Bounded search fixed in docs/MASTER_PLAN.md section 4; not extended after seeing results."""
    found = [Candidate('B0', 'prior'), baseline or Candidate('B1', 'rank_logistic')]
    found += [Candidate('M1', 'logistic', {'C': c}) for c in (0.1, 1.0, 10.0)]
    found += [
        Candidate('M2', 'hgb', {'learning_rate': lr, 'max_leaf_nodes': leaves, 'l2_regularization': l2})
        for lr in (0.05, 0.1)
        for leaves in (7, 15)
        for l2 in (0.0, 1.0)
    ]
    return found


def _preprocess(scale, numeric):
    steps = [('impute', SimpleImputer(strategy='median', add_indicator=True))]
    if scale:
        steps.append(('scale', StandardScaler()))
    return ColumnTransformer(
        [
            ('numeric', Pipeline(steps), numeric),
            (
                'categorical',
                Pipeline(
                    [
                        ('impute', SimpleImputer(strategy='constant', fill_value='unknown')),
                        ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def build_pipeline(candidate, numeric=NUMERIC_FEATURES):
    """Every transformer is fitted inside the training fold only."""
    if candidate.family == 'prior':
        return DummyClassifier(strategy='prior')
    if candidate.family in ('rank_logistic', 'grid_logistic'):
        columns = RANK_FEATURES if candidate.family == 'rank_logistic' else GRID_BASELINE_FEATURES
        single = ColumnTransformer([('single', SimpleImputer(strategy='median', add_indicator=True), columns)])
        return Pipeline([('features', single), ('model', LogisticRegression(max_iter=1000))])
    if candidate.family == 'logistic':
        return Pipeline(
            [
                ('features', _preprocess(True, numeric)),
                ('model', LogisticRegression(max_iter=2000, **candidate.params)),
            ]
        )
    if candidate.family == 'hgb':
        model = HistGradientBoostingClassifier(
            max_iter=200, early_stopping=False, random_state=SEED, **candidate.params
        )
        return Pipeline([('features', _preprocess(False, numeric)), ('model', model)])
    raise ValueError(f'Unknown model family: {candidate.family}')


def fit_predict(candidate, train, score, numeric=NUMERIC_FEATURES):
    """Fit on train rows (features + scored_points) and return P(points) for score rows."""
    model = build_pipeline(candidate, numeric)
    model.fit(train, train['scored_points'])
    return model.predict_proba(score)[:, 1], model


def race_averaged_brier(frame, column='p_points'):
    per_event = frame.assign(error=(frame[column] - frame['scored_points']) ** 2).groupby('event_id')['error'].mean()
    return float(per_event.mean())


def metrics(frame, column='p_points', threshold=0.5):
    y, p = frame['scored_points'].to_numpy(), frame[column].to_numpy()
    predicted = p >= threshold
    true_positive = int((predicted & (y == 1)).sum())
    precision = true_positive / predicted.sum() if predicted.sum() else float('nan')
    recall = true_positive / (y == 1).sum() if (y == 1).sum() else float('nan')
    return {
        'race_brier': race_averaged_brier(frame, column),
        'driver_brier': float(np.mean((p - y) ** 2)),
        'log_loss': float(log_loss(y, np.clip(p, LOG_LOSS_EPS, 1 - LOG_LOSS_EPS), labels=[0, 1])),
        'roc_auc': float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
        'pr_auc': float(average_precision_score(y, p)) if len(set(y)) == 2 else None,
        'precision': precision,
        'recall': recall,
        'f1': 2 * precision * recall / (precision + recall) if precision + recall else float('nan'),
        'rows': len(frame),
        'events': int(frame['event_id'].nunique()),
        'threshold': threshold,
        'log_loss_eps': LOG_LOSS_EPS,
    }


def bootstrap_race_brier(frame, columns, *, reference=None, resamples=1000, seed=SEED):
    """Resample whole events; returns 95% intervals per column and for paired differences vs reference."""
    rng = np.random.default_rng(seed)
    errors = {c: ((frame[c] - frame['scored_points']) ** 2).groupby(frame['event_id']).mean() for c in columns}
    events = errors[columns[0]].index.to_numpy()
    draws = {c: [] for c in columns}
    diffs = {c: [] for c in columns if reference and c != reference}
    for _ in range(resamples):
        sample = rng.choice(events, size=len(events), replace=True)
        for c in columns:
            draws[c].append(errors[c].loc[sample].mean())
        for c in diffs:
            diffs[c].append((errors[c].loc[sample] - errors[reference].loc[sample]).mean())

    def interval(values):
        low, high = np.percentile(values, [2.5, 97.5])
        return [float(low), float(high)]

    return {
        'resamples': resamples,
        'seed': seed,
        'intervals': {c: interval(v) for c, v in draws.items()},
        'difference_vs_' + str(reference): {c: interval(v) for c, v in diffs.items()} if reference else {},
    }


def fit_sigmoid(p, y):
    """Platt scaling on logit of earlier out-of-fold probabilities."""
    logit = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    return LogisticRegression().fit(logit, y)


def apply_sigmoid(calibrator, p):
    logit = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    return calibrator.predict_proba(logit)[:, 1]


def chronological_calibration(oof):
    """For each validation season, calibrate using only out-of-fold predictions of earlier seasons."""
    calibrated = []
    for season in sorted(oof['season'].unique()):
        block = oof[oof['season'] == season].copy()
        earlier = oof[oof['season'] < season]
        if earlier.empty:
            block['p_calibrated'] = block['p_points']  # first block stays raw; no earlier data exists
        else:
            block['p_calibrated'] = apply_sigmoid(
                fit_sigmoid(earlier['p_points'].to_numpy(), earlier['scored_points']), block['p_points'].to_numpy()
            )
        calibrated.append(block)
    return pd.concat(calibrated)


def reliability(frame, column='p_points', bins=10):
    edges = np.linspace(0, 1, bins + 1)
    groups = pd.cut(frame[column], edges, include_lowest=True)
    table = frame.groupby(groups, observed=True).agg(
        count=('scored_points', 'size'), mean_predicted=(column, 'mean'), observed_rate=('scored_points', 'mean')
    )
    return [{'bin': str(index), **{k: float(v) for k, v in row.items()}} for index, row in table.iterrows()]
