"""Paginated collection and availability-only reporting."""
from collections import defaultdict
from .data import normalize_event


def fetch_races(client, endpoint, *, offline=False):
    offset = 0
    races, manifests = [], []
    while True:
        payload, manifest = client.get(f'{endpoint}?limit=100&offset={offset}', offline=offline)
        data = payload['MRData']
        page = data['RaceTable']['Races']
        total, limit = int(data['total']), int(data['limit'])
        if int(data['offset']) != offset or limit <= 0:
            raise ValueError('Invalid pagination metadata')
        if offset < total and not page:
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
    report = {'event_id': event['event_id'], 'season': event['season'], 'round': event['round'],
              'entries': len(entries), 'qualifying_rows': len(qualifying), 'labels': len(labels),
              'missing_qualifying': missing,
              'missing_rank': sum(row['qualifying_rank'] is None for row in entries),
              'missing_q3': sum(row['q3_seconds'] is None for row in entries),
              'sprint_weekend': event['sprint_weekend'],
              'scheduled_qualifying_available': event['qualifying_scheduled_start_utc'] is not None,
              'race_time_available': event['race_start_utc'] is not None,
              'qualifying_end_available': False, 'cutoff_ready': False,
              'limitations': ['actual qualifying end unavailable', 'retrospective roster union',
                              'final published result revision timing not reconstructed']}
    if event['sprint_weekend']:
        report['limitations'].append('sprint qualifying semantics require separate verification')
    if not qualifying:
        report['limitations'].append('qualifying results unavailable')
    if not results:
        report['limitations'].append('race results unavailable')
    return report, {'event': event, 'entries': entries, 'labels': labels}
