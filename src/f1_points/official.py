"""Prospective official qualifying via a credential-free api-anything operation."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .data import normalize_event
from .live import should_forecast


def qualifying_rows(result, source, identities):
    """Reject drift and partial/foreign tables; never manufacture a numeric rank."""
    if result.get('ok') is not True or result.get('truncated'):
        raise ValueError(f'Official qualifying unavailable: {result.get("class")} {result.get("reason", "")}')
    tables = result.get('data')
    if not isinstance(tables, list) or len(tables) != 1:
        raise ValueError('Expected one official qualifying table')
    table = tables[0]
    title = table.get('title', '')
    if not title.endswith(f'GRAND PRIX {source["season"]} - QUALIFYING') or source['title_contains'] not in title:
        raise ValueError('Official event/year/session identity mismatch')
    columns = ('positions', 'numbers', 'drivers', 'teams')
    if any(not isinstance(table.get(c), list) or len(table[c]) != source['expected_rows'] for c in columns):
        raise ValueError('Official qualifying table incomplete or columns misaligned')
    rows, codes, numbers, ranks = [], set(), set(), set()
    for pos, number, name, team in zip(*(table[c] for c in columns), strict=True):
        match = re.search(r'([A-Z]{3})$', name)
        code = match.group(1) if match else None
        if code not in identities or code in codes:
            raise ValueError('Unknown or duplicate official driver identity')
        identity = identities[code]
        if not number.isdigit() or int(number) != identity['car_number'] or number in numbers:
            raise ValueError('Official car number identity mismatch')
        if team not in source['teams']:
            raise ValueError('Unmapped official constructor')
        row = {
            'Driver': {'driverId': identity['driver_id'], 'code': code},
            'Constructor': {'constructorId': source['teams'][team]},
            'number': number,
        }
        if pos.isdigit():
            rank = int(pos)
            if not 1 <= rank <= source['expected_rows'] or rank in ranks:
                raise ValueError('Invalid or duplicate official qualifying rank')
            row['position'] = pos
            ranks.add(rank)
        elif pos not in {'RT', 'NC', 'DSQ', 'DNS'}:
            raise ValueError('Unknown official qualifying position marker')
        rows.append(row)
        codes.add(code)
        numbers.add(number)
    if not ranks:
        raise ValueError('No numeric qualifying ranks published')
    if len({r['Driver']['driverId'] for r in rows}) != len(rows):
        raise ValueError('Duplicate canonical driver identity')
    return rows


def call_official(source, recipe, cache, *, run=subprocess.run):
    """One bounded call in an isolated home: no personal sessions or learned credentials."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    recipe = Path(recipe)
    recipe_bytes = recipe.read_bytes()
    runtime = cache / 'runtime'
    sites = runtime / 'sites'
    sites.mkdir(parents=True, exist_ok=True)
    (sites / 'f1-official.json').write_bytes(recipe_bytes)
    local = Path('tools/api-anything/node_modules/.bin/api-anything')
    executable = str(local.resolve()) if local.exists() else shutil.which('api-anything')
    if not executable:
        raise RuntimeError('Install api-anything: npm ci --prefix tools/api-anything')
    command = [
        executable,
        'call',
        'f1-official',
        'qualifying',
        f'season={source["season"]}',
        f'race={source["race"]}',
        f'slug={source["slug"]}',
    ]
    completed = run(
        command,
        env={**os.environ, 'API_ANYTHING_HOME': str(runtime.resolve())},
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except (ValueError, TypeError) as error:
        raise RuntimeError('api-anything returned invalid JSON') from error
    if completed.returncode or result.get('ok') is not True:
        raise RuntimeError(f'api-anything: {result.get("class")} {result.get("reason", "")}')
    body = completed.stdout
    digest = hashlib.sha256(body.encode()).hexdigest()
    manifest = {
        'source_url': f'https://www.formula1.com/en/results/{source["season"]}/races/'
        f'{source["race"]}/{source["slug"]}/qualifying',
        'fetched_at': datetime.now(UTC).isoformat(),
        'sha256': digest,
        'schema_version': 1,
        'adapter_version': 'official-api-anything/1',
        'recipe_sha256': hashlib.sha256(recipe_bytes).hexdigest(),
        'transport_tier': result.get('tier'),
        'snapshot_scope': 'Complete api-anything response, not original page HTML',
    }
    location = cache / f'{digest}.json'
    if not location.exists():
        location.write_text(json.dumps({'body': body, 'manifest': manifest}, indent=2) + '\n')
    return result, manifest


def enrich_due_events(normalized, archive, sources_path, *, now=None, call=call_official):
    """Prefer configured official classifications only for fresh due, unarchived events."""
    now = now or datetime.now(UTC)
    normalized = Path(normalized)
    if sources_path is None:
        return []
    sources_path = Path(sources_path)
    config = json.loads(sources_path.read_text())
    records = {p.stem: (p, json.loads(p.read_text())) for p in normalized.glob('*.json')}
    manifests = []
    for event_id, source in config['events'].items():
        if event_id not in records:
            continue
        path, record = records[event_id]
        event = record['event']
        if not should_forecast(
            event, bool(record['labels']), (Path(archive) / f'{event_id}-prospective.json').exists(), now
        ):
            continue
        if event_id != f'{source["season"]}-{source["round"]:02d}' or event['circuit_id'] != source['circuit_id']:
            raise ValueError('Official source mapping does not match scheduled event')
        identities = {}
        for _, previous in sorted(records.values(), key=lambda item: item[1]['event']['round']):
            prior = previous['event']
            if prior['season'] == source['season'] and prior['round'] < source['round']:
                for entry in previous['entries']:
                    if entry.get('driver_code'):
                        identities[entry['driver_code']] = entry
        result, manifest = call(
            source, sources_path.parent / config['recipe'], normalized.parent / 'official-snapshots' / event_id
        )
        rows = qualifying_rows(result, source, identities)
        manifest['source_mapping_sha256'] = hashlib.sha256(sources_path.read_bytes()).hexdigest()
        schedule = {
            'season': source['season'],
            'round': source['round'],
            'Circuit': {'circuitId': event['circuit_id']},
            'date': event['race_start_utc'][:10],
            'time': event['race_start_utc'][11:],
            'Qualifying': {
                'date': event['qualifying_scheduled_start_utc'][:10],
                'time': event['qualifying_scheduled_start_utc'][11:],
            },
        }
        _, entries, _ = normalize_event(schedule, rows, [])
        for entry in entries:
            entry['constructor_provenance'] = 'official qualifying via api-anything'
        record['entries'] = entries
        record['event']['roster_provenance'] = 'official qualifying table via api-anything'
        record['event']['qualifying_source'] = manifest['source_url']
        record['event']['qualifying_retrieved_at'] = manifest['fetched_at']
        record.setdefault('manifests', []).append(manifest)
        path.write_text(json.dumps(record, indent=2) + '\n')
        manifests.append(manifest)
    return manifests
