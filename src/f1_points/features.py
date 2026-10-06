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


# v2 additions (pre-registered in docs/PREREGISTRATION_V2.md).
SESSION_FEATURES = [
    'qualifying_gap_pct',
    'practice_gap_pct',
    'practice_sessions',
    'qualifying_rain',
    'qualifying_track_temp',
]
GRID_FEATURES = ['grid_position', 'grid_pitlane', 'grid_change']
V2_QUALIFYING_FEATURES = NUMERIC_FEATURES + SESSION_FEATURES
V2_PRE_RACE_FEATURES = V2_QUALIFYING_FEATURES + GRID_FEATURES


def _gap_pct(times):
    """Percent slower than the fastest valid time in the same group; None stays None."""
    valid = [t for t in times if t is not None and not pd.isna(t)]
    fastest = min(valid) if valid else None
    return [None if fastest is None or t is None or pd.isna(t) else 100 * (t / fastest - 1) for t in times]


def _practice_by_driver(record, event_entries):
    """Best pre-qualifying practice lap per driver_id, joined on car number and checked against the code."""
    by_number = {str(int(e['car_number'])): e for e in event_entries.to_dict('records') if not pd.isna(e['car_number'])}
    best, sessions = {}, {}
    for practice in record.get('practice', []):
        for number, lap in practice['best_laps'].items():
            entry = by_number.get(number)
            code = practice['codes'].get(number)
            if entry is None or lap is None or (code and entry['driver_code'] and code != entry['driver_code']):
                continue
            driver = entry['driver_id']
            best[driver] = min(lap, best.get(driver, lap))
            sessions[driver] = sessions.get(driver, 0) + 1
    return best, sessions


def add_session_features(features, entries, session_dir):
    """Current-event qualifying gap, pre-qualifying practice pace, qualifying weather and starting grid."""
    features = features.copy()
    lookup = entries.set_index(KEY)
    best_q = lookup[['q1_seconds', 'q2_seconds', 'q3_seconds']].min(axis=1, skipna=True)
    columns = {name: {} for name in SESSION_FEATURES + GRID_FEATURES}
    for event_id, group in features.groupby('event_id', sort=False):
        drivers = group['driver_id'].tolist()
        q_gaps = _gap_pct([best_q.get((event_id, d)) for d in drivers])
        path = Path(session_dir) / f'{event_id}.json' if session_dir else None
        record = json.loads(path.read_text()) if path is not None and path.exists() else {}
        best, sessions = _practice_by_driver(record, entries[entries['event_id'] == event_id])
        p_gaps = _gap_pct([best.get(d) for d in drivers])
        weather = record.get('qualifying_weather') or {}
        field = int((entries['event_id'] == event_id).sum())
        for index, (row_index, driver) in enumerate(zip(group.index, drivers, strict=True)):
            row = lookup.loc[(event_id, driver)]
            grid = row.get('starting_grid')
            grid = None if grid is None or pd.isna(grid) else int(grid)
            rank = group['qualifying_rank'].iloc[index]
            position = None if grid is None else (field if grid == 0 else grid)
            columns['qualifying_gap_pct'][row_index] = q_gaps[index]
            columns['practice_gap_pct'][row_index] = p_gaps[index]
            columns['practice_sessions'][row_index] = sessions.get(driver, 0) if record else None
            columns['qualifying_rain'][row_index] = weather.get('rain_fraction')
            columns['qualifying_track_temp'][row_index] = weather.get('track_temp_mean')
            columns['grid_position'][row_index] = position
            columns['grid_pitlane'][row_index] = None if grid is None else int(grid == 0)
            columns['grid_change'][row_index] = None if position is None or pd.isna(rank) else position - rank
    for name, values in columns.items():
        features[name] = pd.Series(values, dtype='float64').reindex(features.index)
    return features
