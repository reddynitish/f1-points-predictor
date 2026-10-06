"""Frozen-model prediction for one event at the qualifying cutoff, with refusal and archiving."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .experiments import config_hash, environment, frozen_candidate, git_commit
from .features import KEY, apply_qualifying_overrides, build_features, build_labels, load_normalized
from .modeling import Candidate, fit_predict

PRIMARY_RULE = (
    'Sealed 2025 evaluation did not show M1 beating the rank-only baseline (B1); per the pre-registered rule '
    'B1 is the primary forecast and M1 is shown for comparison.'
)


class InsufficientHistory(RuntimeError):
    """Raised when no earlier labeled race exists to fit on."""


class QualifyingUnavailable(RuntimeError):
    """Raised instead of guessing when the target event has no usable qualifying classification."""


def load_combined(base_dir, live_dir, season):
    """Earlier seasons from the audited cache plus the freshly fetched target season."""
    base_events, base_entries, base_labels = load_normalized(base_dir)
    if live_dir is None:
        return base_events, base_entries, base_labels
    live_events, live_entries, live_labels = load_normalized(live_dir)
    keep = set(base_events.loc[base_events['season'] < season, 'event_id'])
    live = set(live_events.loc[live_events['season'] == season, 'event_id'])
    return (
        pd.concat([base_events[base_events['event_id'].isin(keep)], live_events[live_events['event_id'].isin(live)]]),
        pd.concat(
            [base_entries[base_entries['event_id'].isin(keep)], live_entries[live_entries['event_id'].isin(live)]]
        ),
        pd.concat([base_labels[base_labels['event_id'].isin(keep)], live_labels[live_labels['event_id'].isin(live)]]),
    )


def predict_event(events, entries, labels, event_id, config, *, now=None, overrides=None):
    now = now or datetime.now(UTC)
    if overrides:
        entries = apply_qualifying_overrides(entries, overrides)
    event = events.set_index('event_id').loc[event_id]
    features = build_features(events, entries, labels)
    target = features[features['event_id'] == event_id].copy()
    if target.empty or target['qualifying_rank_missing'].all():
        raise QualifyingUnavailable(f'No qualifying classification published for {event_id}; refusing to predict')

    order = (int(event['season']), int(event['round']))
    earlier = features[[(s, r) < order for s, r in zip(features['season'], features['round'], strict=True)]]
    train = earlier.merge(build_labels(entries, labels), on=KEY, how='inner')
    if train.empty:
        raise InsufficientHistory(f'No earlier labeled races before {event_id}')
    target['p_B1'], _ = fit_predict(Candidate('B1', 'rank_logistic'), train, target)
    target['p_M1'], _ = fit_predict(frozen_candidate(config), train, target)

    has_labels = bool((labels['event_id'] == event_id).any())
    race_start = event.get('race_start_utc')
    started = bool(race_start) and now >= datetime.fromisoformat(race_start)
    mode = 'retrospective_replay' if has_labels or started else 'prospective'

    warnings = []
    for column, text in [
        ('rookie', 'no prior race history'),
        ('constructor_new', 'no prior team history'),
        ('qualifying_rank_missing', 'qualifying rank missing'),
    ]:
        for driver in target.loc[target[column] == 1, 'driver_id']:
            warnings.append(f'{driver}: {text}')
    if event.get('sprint_weekend'):
        warnings.append('sprint weekend: current-weekend sprint results are excluded from inputs')

    last_train = train.sort_values(['season', 'round'])['event_id'].iloc[-1]
    metadata = {
        'event_id': event_id,
        'circuit_id': event['circuit_id'],
        'mode': mode,
        'created_at': now.isoformat(),
        'cutoff': 'qualifying end (interval: scheduled qualifying start to race start)',
        'qualifying_scheduled_start_utc': event.get('qualifying_scheduled_start_utc'),
        'race_start_utc': race_start,
        'primary': 'p_B1',
        'primary_rule': PRIMARY_RULE,
        'model': {'B1': 'qualifying-rank logistic', 'M1': frozen_candidate(config).label()},
        'training_rows': len(train),
        'training_last_event': last_train,
        'feature_columns': config['feature_columns'],
        'warnings': warnings,
        'note': 'Qualifying rank is not the final starting grid. Probabilities are independent per driver and '
        'need not sum to ten.',
    }
    columns = [*KEY, 'constructor_id', 'qualifying_rank', 'p_B1', 'p_M1']
    return target[columns].sort_values('p_B1', ascending=False).reset_index(drop=True), metadata


def archive(predictions, metadata, config_path, directory):
    """Write predictions before outcomes exist; a prospective forecast is never silently replaced."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if metadata['mode'] == 'prospective':
        path = directory / f'{metadata["event_id"]}-prospective.json'
        if path.exists():
            raise FileExistsError(f'{path} already exists; prospective predictions are never replaced')
    else:
        stamp = metadata['created_at'].replace(':', '').split('.')[0]
        path = directory / f'{metadata["event_id"]}-replay-{stamp}.json'
    record = {
        **metadata,
        'git_commit': git_commit(),
        'config_sha256': config_hash(config_path),
        'environment': environment(),
        'predictions': predictions.round(4).to_dict('records'),
    }
    path.write_text(json.dumps(record, indent=2, default=str) + '\n')
    return path
