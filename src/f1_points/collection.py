"""Paginated collection and availability-only reporting."""

from collections import defaultdict

from .data import normalize_event


def fetch_races(client, endpoint, *, offline=False):
    offset = 0
    races, manifests = [], []
    expected_total = None
    session_key = {
        'qualifying.json': 'QualifyingResults',
        'results.json': 'Results',
        'sprint.json': 'SprintResults',
    }.get(endpoint.rsplit('/', 1)[-1])
    while True:
        payload, manifest = client.get(f'{endpoint}?limit=100&offset={offset}', offline=offline)
        data = payload['MRData']
        page = data['RaceTable']['Races']
        total, limit = int(data['total']), int(data['limit'])
        if (
            int(data['offset']) != offset
            or limit <= 0
            or total < 0
            or (expected_total is not None and total != expected_total)
        ):
            raise ValueError('Invalid pagination metadata')
        expected_total = total
        # Session totals count driver records, not the race objects wrapping them.
        count = sum(len(race.get(session_key, [])) for race in page) if session_key else len(page)
        if count != min(limit, max(0, total - offset)):
            raise ValueError('Truncated source page')
        races.extend(page)
        manifests.append(manifest)
        offset += limit
        if offset >= total:
            break
    return races, manifests


def session_rows(races, key):
    grouped = defaultdict(list)
    for race in races:
        grouped[int(race['round'])].extend(race.get(key, []))
    return grouped


def audit_event(schedule, qualifying, results):
    event, entries, labels = normalize_event(schedule, qualifying, results)
    missing = sum(not row['qualifying_available'] for row in entries)
    ranks = [row['qualifying_rank'] for row in entries if row['qualifying_rank'] is not None]
    repeated = len(ranks) - len(set(ranks))
    unused_ranks = sorted(set(range(1, len(entries) + 1)) - set(ranks))
    report = {
        'event_id': event['event_id'],
        'season': event['season'],
        'round': event['round'],
        'entries': len(entries),
        'qualifying_rows': len(qualifying),
        'labels': len(labels),
        'missing_labels': len(entries) - len(labels),
        'missing_qualifying': missing,
        'repeated_rank_rows': repeated,
        'repeated_rank_drivers': sorted(row['driver_id'] for row in entries if row['qualifying_rank_repeated']),
        'unused_ranks': unused_ranks,
        'missing_rank': sum(row['qualifying_rank'] is None for row in entries),
        'missing_q3': sum(row['q3_seconds'] is None for row in entries),
        'sprint_weekend': event['sprint_weekend'],
        'weekend_format': event['weekend_format'],
        'sprint_scheduled_before_qualifying': event['sprint_scheduled_before_qualifying'],
        'scheduled_qualifying_available': event['qualifying_scheduled_start_utc'] is not None,
        'race_time_available': event['race_start_utc'] is not None,
        'qualifying_end_available': False,
        'cutoff_ready': False,
        'limitations': [
            'actual qualifying end unavailable',
            'retrospective roster union',
            'final published result revision timing not reconstructed',
        ],
    }
    if repeated:
        report['limitations'].append('repeated upstream qualifying ranks require review')
    if event['qualifying_determines'] == 'sprint grid':
        report['limitations'].append('qualifying sets sprint grid; race grid comes from sprint result')
    if event['sprint_scheduled_before_qualifying']:
        report['limitations'].append('current-weekend sprint scheduled before qualifying; exclude from v1 features')
    elif event['sprint_weekend'] and event['sprint_scheduled_before_qualifying'] is None:
        report['limitations'].append('sprint/qualifying session order unknown')
    if not qualifying:
        report['limitations'].append('qualifying results unavailable')
    if not results:
        report['limitations'].append('race results unavailable')
    return report, {'event': event, 'entries': entries, 'labels': labels}
