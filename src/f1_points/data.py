"""Historical snapshots and normalization; no predictive features."""

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib.metadata import version
from pathlib import Path

import requests

BASE_URL = 'https://api.jolpi.ca/ergast/f1/'
USER_AGENT = 'f1-points-predictor/0.1 educational audit'
SCHEMA_VERSION = 1


class SnapshotClient:
    """Immutable, hash-checked cache. Refresh requires a separate cache directory."""

    def __init__(self, root, *, fetch=requests.get, sleep=time.sleep):
        self.root = Path(root)
        self.fetch = fetch
        self.sleep = sleep

    def get(self, path, *, offline=False):
        url = BASE_URL + path
        key = hashlib.sha256(url.encode()).hexdigest()
        location = self.root / f'{key}.json'
        if location.exists():
            saved = json.loads(location.read_text())
            body = saved.get('body', '')
            if hashlib.sha256(body.encode()).hexdigest() != saved.get('manifest', {}).get('sha256'):
                raise ValueError(f'Cache hash mismatch: {location}')
            if saved['manifest']['source_url'] != url:
                raise ValueError('Cache URL mismatch')
            return json.loads(body), saved['manifest']
        if offline:
            raise FileNotFoundError(f'Offline snapshot unavailable: {url}')
        for attempt in range(3):
            response = None
            try:
                response = self.fetch(
                    url, timeout=45, headers={'User-Agent': 'f1-points-predictor/0.1 educational audit'}
                )
                response.raise_for_status()
                body = response.content.decode('utf-8')
                payload = json.loads(body)
                break
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise
                delay = 2**attempt
                retry_after = response.headers.get('Retry-After') if response is not None else None
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        delay = max(delay, (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds())
                self.sleep(delay)
        manifest = {
            'source_url': url,
            'fetched_at': datetime.now(UTC).isoformat(),
            'sha256': hashlib.sha256(body.encode()).hexdigest(),
            'schema_version': SCHEMA_VERSION,
            'adapter_version': version('f1-points-predictor'),
            'requests_version': version('requests'),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        temp = location.with_suffix('.tmp')
        temp.write_text(json.dumps({'body': body, 'manifest': manifest}))
        temp.replace(location)
        self.sleep(1)  # Keep requests below one per second; cache hits do not wait.
        return payload, manifest


def _rows_by_driver(rows):
    output = {}
    for row in rows:
        identifier = row['Driver']['driverId']
        if not identifier or identifier in output:
            raise ValueError('Missing or duplicate driver ID')
        output[identifier] = row
    return output


def _duration(value):
    if value is None or value == '':
        return None
    minutes, seconds = value.split(':') if ':' in value else ('0', value)
    result = int(minutes) * 60 + float(seconds)
    if int(minutes) < 0 or not 0 <= float(seconds) < 60 or not math.isfinite(result) or result <= 0:
        raise ValueError('Invalid qualifying duration')
    return result


def _timestamp(record):
    if not record or not record.get('date') or not record.get('time'):
        return None
    timestamp = datetime.fromisoformat(record['date'] + 'T' + record['time'].replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp must have timezone')
    return timestamp.astimezone(UTC).isoformat()


def weekend_format(schedule):
    """Classify sprint semantics from upstream session keys, never from results.

    sprint_grid_from_qualifying (2021-22): qualifying sets the sprint grid; sprint result sets race grid.
    sprint_shootout (2023): qualifying sets race grid; a separate shootout sets the sprint grid.
    sprint_qualifying (2024+): sprint qualifying sets the sprint grid; qualifying sets race grid.
    """
    if 'Sprint' not in schedule:
        return 'conventional'
    if 'SprintShootout' in schedule:
        return 'sprint_shootout'
    if 'SprintQualifying' in schedule:
        return 'sprint_qualifying'
    return 'sprint_grid_from_qualifying'


def _before(first, second):
    return None if first is None or second is None else first < second


def _car_number(row):
    value = row.get('number') or row['Driver'].get('permanentNumber')
    return int(value) if value not in (None, '') else None


def _grid(row):
    if row is None or row.get('grid') in (None, ''):
        return None
    grid = int(row['grid'])
    if grid < 0:
        raise ValueError('Invalid starting grid')
    return grid


def normalize_event(schedule, qualifying, results):
    """Use separate sessions; roster union is a disclosed retrospective approximation."""
    qrows, rrows = _rows_by_driver(qualifying), _rows_by_driver(results)
    identifiers = sorted(qrows.keys() | rrows.keys())
    event_id = f'{int(schedule["season"])}-{int(schedule["round"]):02d}'
    fmt = weekend_format(schedule)
    qualifying_start = _timestamp(schedule.get('Qualifying'))
    sprint_start = _timestamp(schedule.get('Sprint'))
    event = {
        'event_id': event_id,
        'season': int(schedule['season']),
        'round': int(schedule['round']),
        'circuit_id': schedule['Circuit']['circuitId'],
        'race_start_utc': _timestamp(schedule),
        'race_start_provenance': 'upstream scheduled time',
        'qualifying_scheduled_start_utc': qualifying_start,
        'qualifying_end_utc': None,
        'sprint_weekend': fmt != 'conventional',
        'weekend_format': fmt,
        'qualifying_determines': 'sprint grid' if fmt == 'sprint_grid_from_qualifying' else 'race grid',
        'sprint_scheduled_start_utc': sprint_start,
        'sprint_scheduled_before_qualifying': _before(sprint_start, qualifying_start),
        'roster_provenance': 'retrospective qualifying/results union',
    }
    entries, labels = [], []
    for identifier in identifiers:
        qrow = qrows.get(identifier)
        source = qrow if qrow is not None else rrows[identifier]
        rank = int(qrow['position']) if qrow and qrow.get('position') is not None else None
        if rank is not None:
            if rank < 1 or rank > len(identifiers):
                raise ValueError('Impossible qualifying rank')
        entry = {
            'event_id': event_id,
            'driver_id': identifier,
            'constructor_id': source['Constructor']['constructorId'],
            'qualifying_rank': rank,
            'qualifying_available': qrow is not None,
            'constructor_provenance': 'qualifying' if qrow else 'race result fallback',
            'car_number': _car_number(source),
            'driver_code': source['Driver'].get('code'),
            # Published with race results but fixed before the start; only the pre-race cutoff may use it.
            'starting_grid': _grid(rrows.get(identifier)),
            'starting_grid_provenance': 'race result grid column (0 = pit lane)',
        }
        for segment in ('Q1', 'Q2', 'Q3'):
            entry[segment.lower() + '_seconds'] = _duration(qrow.get(segment)) if qrow else None
        entries.append(entry)
        if identifier in rrows:
            row = rrows[identifier]
            points = float(row['points'])
            position = int(row['position'])
            if not math.isfinite(points) or points < 0 or position < 1:
                raise ValueError('Invalid race label')
            labels.append(
                {
                    'event_id': event_id,
                    'driver_id': identifier,
                    'race_points': points,
                    'final_position': position,
                    'result_status': row['status'],
                }
            )
    counts = {}
    for entry in entries:
        counts[entry['qualifying_rank']] = counts.get(entry['qualifying_rank'], 0) + 1
    for entry in entries:
        # Flag only; observed post-session reclassifications leave collisions that need a design decision.
        entry['qualifying_rank_repeated'] = (
            entry['qualifying_rank'] is not None and counts[entry['qualifying_rank']] > 1
        )
    return event, entries, labels
