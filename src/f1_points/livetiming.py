"""F1 live-timing archive adapter: pre-qualifying practice best laps and observed qualifying weather.

The archive is unofficial and undocumented (the same source FastF1 reads). Raw payloads stay in an ignored,
hash-checked cache and are never redistributed. Requests are throttled; cache hits never wait.
"""

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from .data import USER_AGENT

BASE_URL = 'https://livetiming.formula1.com/static/'
MIN_INTERVAL_SECONDS = 3.0
MATCH_TOLERANCE = timedelta(hours=36)
# A missing page is only cached as permanently absent once its session is comfortably in the past.
ABSENT_SETTLE = timedelta(days=2)


class LiveTimingClient:
    """Immutable cache like SnapshotClient; a missing page (403/404) is cached as absent, not retried forever."""

    def __init__(self, root, *, fetch=requests.get, sleep=time.sleep, clock=time.monotonic):
        self.root = Path(root)
        self.fetch, self.sleep, self.clock = fetch, sleep, clock
        self.last_request = None

    def get(self, path, *, offline=False, cache_absent=True):
        url = BASE_URL + path
        location = self.root / f'{hashlib.sha256(url.encode()).hexdigest()}.json'
        if location.exists():
            saved = json.loads(location.read_text())
            body = saved['body']
            if body is not None and hashlib.sha256(body.encode()).hexdigest() != saved['manifest']['sha256']:
                raise ValueError(f'Cache hash mismatch: {location}')
            return body, saved['manifest']
        if offline:
            raise FileNotFoundError(f'Offline live-timing page unavailable: {url}')
        body, status = None, None
        for attempt in range(3):
            if self.last_request is not None:
                self.sleep(max(0.0, MIN_INTERVAL_SECONDS - (self.clock() - self.last_request)))
            self.last_request = self.clock()
            try:
                response = self.fetch(url, timeout=45, headers={'User-Agent': USER_AGENT})
                status = response.status_code
                if status in (403, 404):
                    break
                response.raise_for_status()
                body = response.content.decode('utf-8-sig')
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                self.sleep(2**attempt)
        manifest = {
            'source_url': url,
            'fetched_at': datetime.now(UTC).isoformat(),
            'status': status,
            'sha256': hashlib.sha256(body.encode()).hexdigest() if body is not None else None,
        }
        if body is None and not cache_absent:
            return body, manifest  # page may appear later (session not run yet); do not freeze its absence
        self.root.mkdir(parents=True, exist_ok=True)
        temp = location.with_suffix('.tmp')
        temp.write_text(json.dumps({'body': body, 'manifest': manifest}))
        temp.replace(location)
        return body, manifest


def parse_stream(text):
    """jsonStream lines are 'HH:MM:SS.mmm{json}'."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            brace = line.index('{')
            rows.append((line[:brace], json.loads(line[brace:])))
    return rows


def _lap_seconds(value):
    if not value:
        return None
    minutes, seconds = value.split(':') if ':' in value else ('0', value)
    result = int(minutes) * 60 + float(seconds)
    return result if result > 0 else None


def _mean_of(samples, key):
    values = [float(v[key]) for v in samples if v.get(key) not in (None, '')]
    return sum(values) / len(values) if values else None


def meetings_from_schedule(rows, path_for):
    """Meetings in chronological session order. rows: FastF1 event-schedule records; path_for(round, name)."""
    meetings = []
    for row in rows:
        sessions = []
        for n in range(1, 6):
            name = row.get(f'Session{n}')
            if not name:
                continue
            start = row.get(f'Session{n}DateUtc')
            start = None if start is None or pd.isna(start) else pd.Timestamp(start).tz_localize(UTC).to_pydatetime()
            kind = 'Practice' if name.startswith('Practice') else ('Race' if name == 'Race' else name)
            sessions.append(
                {'name': name, 'type': kind, 'start_utc': start, 'path': path_for(row['RoundNumber'], name)}
            )
        if any(s['type'] == 'Race' and s['start_utc'] for s in sessions):
            meetings.append({'name': row['EventName'], 'round': int(row['RoundNumber']), 'sessions': sessions})
    return meetings


def season_meetings(year, cache_dir):
    """Session archive paths from FastF1's maintained schedule; the archive's own Index.json is incomplete."""
    import fastf1  # imported lazily: only needed when resolving paths

    fastf1.Cache.enable_cache(str(cache_dir))
    fastf1.set_log_level('ERROR')
    schedule = fastf1.get_event_schedule(year, include_testing=False)

    def path_for(round_number, name):
        return fastf1.get_session(year, int(round_number), name).api_path.removeprefix('/static/')

    return meetings_from_schedule(schedule.to_dict('records'), path_for)


def match_meeting(meetings, race_start_utc):
    """Pair a Jolpica event with the archive meeting whose race session starts closest to it."""
    target = datetime.fromisoformat(race_start_utc)
    best = None
    for meeting in meetings:
        race = next(s for s in meeting['sessions'] if s['type'] == 'Race')
        gap = abs(race['start_utc'] - target)
        if gap <= MATCH_TOLERANCE and (best is None or gap < best[0]):
            best = (gap, meeting)
    return best[1] if best else None


def event_sessions(client, meeting, *, offline=False, now=None):
    """Best laps from practice sessions that started before qualifying, plus observed qualifying weather."""
    now = now or datetime.now(UTC)

    def settled(session):
        return session['start_utc'] is not None and session['start_utc'] < now - ABSENT_SETTLE

    names = [s['name'] for s in meeting['sessions']]
    if 'Qualifying' not in names:
        raise ValueError(f'No qualifying session in {meeting["name"]}')
    qualifying_index = names.index('Qualifying')
    qualifying = meeting['sessions'][qualifying_index]
    record = {
        'meeting': meeting['name'],
        'qualifying_start_utc': qualifying['start_utc'].isoformat(),
        'practice': [],
        'qualifying_weather': None,
        'manifests': [],
    }
    # Schedule order is chronological; practice listed after qualifying (2021-22 sprint FP2) is excluded.
    for session in meeting['sessions'][:qualifying_index]:
        if session['type'] != 'Practice':
            continue
        keep = settled(session)
        stats, stats_manifest = client.get(session['path'] + 'TimingStats.json', offline=offline, cache_absent=keep)
        drivers, drivers_manifest = client.get(session['path'] + 'DriverList.json', offline=offline, cache_absent=keep)
        record['manifests'] += [stats_manifest, drivers_manifest]
        if stats is None:
            continue
        lines = json.loads(stats).get('Lines', {})
        codes = {
            number: info.get('Tla') for number, info in json.loads(drivers or '{}').items() if isinstance(info, dict)
        }
        record['practice'].append(
            {
                'session': session['name'],
                'start_utc': str(session['start_utc']),
                'best_laps': {
                    number: _lap_seconds((line.get('PersonalBestLapTime') or {}).get('Value'))
                    for number, line in lines.items()
                },
                'codes': codes,
            }
        )
    weather, weather_manifest = client.get(
        qualifying['path'] + 'WeatherData.jsonStream', offline=offline, cache_absent=settled(qualifying)
    )
    record['manifests'].append(weather_manifest)
    if weather:
        samples = [values for _, values in parse_stream(weather)]
        record['qualifying_weather'] = {
            'samples': len(samples),
            # Share of readings with rain; the stream also covers minutes around the session, so a single
            # reading is not evidence of a wet session.
            'rain_fraction': sum(str(v.get('Rainfall', '0')) not in ('0', 'False', 'false') for v in samples)
            / len(samples)
            if samples
            else None,
            'track_temp_mean': _mean_of(samples, 'TrackTemp'),
            'air_temp_mean': _mean_of(samples, 'AirTemp'),
        }
    return record
