"""Cutoff-safe feature construction. Features for an event see only labels of strictly earlier events."""

import csv
import json
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

KEY = ['event_id', 'driver_id']
FINISHED_STATUSES = {'Finished', 'Lapped'}  # plus any '+N Lap(s)' status
DRIVER_WINDOW = 5
CONSTRUCTOR_WINDOW = 5
HISTORY_COUNT_CAP = 20

# Team-history continuity across renames of the same entry (factory/entry lineage, not a performance claim).
# Original constructor_id values are kept as model inputs; only history lookup uses the lineage key.
CONSTRUCTOR_LINEAGE = {
    'racing_point': 'force_india',
    'aston_martin': 'force_india',
    'alphatauri': 'toro_rosso',
    'rb': 'toro_rosso',
    'alpine': 'renault',
    'alfa': 'sauber',
    'audi': 'sauber',
}

NUMERIC_FEATURES = [
    'qualifying_rank',
    'qualifying_rank_missing',
    'field_size',
    'qualifying_percentile',
    'driver_points_rate_last5',
    'driver_finish_mean_last5',
    'driver_dnf_rate_last5',
    'driver_history_count',
    'rookie',
    'constructor_points_rate_last5_events',
    'constructor_history_events',
    'constructor_new',
]
CATEGORICAL_FEATURES = ['circuit_id', 'constructor_id']
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
# Never allowed as model inputs; checked on every build.
FORBIDDEN_COLUMNS = {'race_points', 'final_position', 'result_status', 'scored_points', 'fetched_at'}


def load_normalized(directory):
    """Read normalized audit records into separate event, entry and label tables."""
    events, entries, labels = [], [], []
    for path in sorted(Path(directory).glob('*.json')):
        record = json.loads(path.read_text())
        events.append(record['event'])
        entries.extend(record['entries'])
        labels.extend(record['labels'])
    return pd.DataFrame(events), pd.DataFrame(entries), pd.DataFrame(labels)


def apply_qualifying_overrides(entries, path):
    """Apply sourced, hand-reviewed qualifying corrections. Only 'rank_missing' is supported."""
    entries = entries.copy()
    with open(path, newline='') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row['action'] != 'rank_missing' or not row['source_url']:
            raise ValueError(f'Unsupported or unsourced override: {row}')
        mask = (entries['event_id'] == row['event_id']) & (entries['driver_id'] == row['driver_id'])
        if mask.sum() != 1:
            raise ValueError(f'Override does not match exactly one entry: {row}')
        entries.loc[mask, 'qualifying_rank'] = None
    return entries


def is_finished(status):
    return status in FINISHED_STATUSES or status.startswith('+')


def is_dnf(status):
    """Non-finish for reliability purposes; disqualification is a separate outcome."""
    return not is_finished(status) and status != 'Disqualified'


def lineage(constructor_id):
    return CONSTRUCTOR_LINEAGE.get(constructor_id, constructor_id)


def _mean(values):
    return sum(values) / len(values) if values else None


def _cutoff(event):
    """Lower bound of the qualifying-end interval (scheduled qualifying start), else scheduled race start."""
    return event.get('qualifying_scheduled_start_utc') or event.get('race_start_utc')


def build_features(events, entries, labels):
    """One row per qualifying entry. State is updated with an event's labels only after its rows are built."""
    events = events.sort_values(['season', 'round']).reset_index(drop=True)
    roster = entries[entries['qualifying_available'].astype(bool)]
    by_event_entries = {key: group for key, group in roster.groupby('event_id')}
    all_entries = entries.set_index(KEY)['constructor_id']
    by_event_labels = {key: group for key, group in labels.groupby('event_id')}

    driver_history = defaultdict(lambda: deque(maxlen=DRIVER_WINDOW))
    driver_counts = defaultdict(int)
    constructor_history = defaultdict(lambda: deque(maxlen=CONSTRUCTOR_WINDOW))
    last_history_start = None
    rows = []
    for event in events.to_dict('records'):
        cutoff = _cutoff(event)
        if last_history_start and cutoff and last_history_start >= cutoff:
            raise ValueError(f'History event at {last_history_start} does not precede cutoff of {event["event_id"]}')
        group = by_event_entries.get(event['event_id'])
        if group is not None:
            field_size = len(group)
            for entry in group.sort_values('driver_id').to_dict('records'):
                rank = entry['qualifying_rank']
                rank = None if pd.isna(rank) else int(rank)
                past = list(driver_history[entry['driver_id']])
                team_key = lineage(entry['constructor_id'])
                team = [value for event_rows in constructor_history[team_key] for value in event_rows]
                rows.append(
                    {
                        'event_id': event['event_id'],
                        'driver_id': entry['driver_id'],
                        'season': event['season'],
                        'round': event['round'],
                        'qualifying_rank': rank,
                        'qualifying_rank_missing': int(rank is None),
                        'field_size': field_size,
                        'qualifying_percentile': None
                        if rank is None or field_size < 2
                        else min(1.0, (rank - 1) / (field_size - 1)),
                        'driver_points_rate_last5': _mean([p > 0 for p, _, _ in past]),
                        'driver_finish_mean_last5': _mean([position for _, position, _ in past]),
                        'driver_dnf_rate_last5': _mean([is_dnf(status) for _, _, status in past]),
                        'driver_history_count': min(driver_counts[entry['driver_id']], HISTORY_COUNT_CAP),
                        'rookie': int(driver_counts[entry['driver_id']] == 0),
                        'constructor_points_rate_last5_events': _mean([p > 0 for p in team]),
                        'constructor_history_events': len(constructor_history[team_key]),
                        'constructor_new': int(not constructor_history[team_key]),
                        'circuit_id': event['circuit_id'],
                        'constructor_id': entry['constructor_id'],
                        'cutoff_utc': cutoff,
                        'history_last_race_utc': last_history_start,
                    }
                )
        event_labels = by_event_labels.get(event['event_id'])
        if event_labels is None:
            continue
        team_points = defaultdict(list)
        for label in event_labels.sort_values('driver_id').to_dict('records'):
            driver_history[label['driver_id']].append(
                (label['race_points'], label['final_position'], label['result_status'])
            )
            driver_counts[label['driver_id']] += 1
            team_points[lineage(all_entries.loc[(label['event_id'], label['driver_id'])])].append(label['race_points'])
        for constructor, points in team_points.items():
            constructor_history[constructor].append(points)
        last_history_start = max(filter(None, [last_history_start, event.get('race_start_utc')]), default=None)

    features = pd.DataFrame(rows)
    leaked = FORBIDDEN_COLUMNS & set(features.columns)
    if leaked:
        raise ValueError(f'Forbidden columns in features: {sorted(leaked)}')
    return features


def build_labels(entries, labels):
    """Binary target for qualifying entries with a published race result; unlabeled rows are dropped, never zeroed."""
    roster = entries[entries['qualifying_available'].astype(bool)][KEY]
    merged = roster.merge(labels[[*KEY, 'race_points']], on=KEY, how='inner')
    merged['scored_points'] = (merged['race_points'] > 0).astype(int)
    return merged[[*KEY, 'scored_points']]
