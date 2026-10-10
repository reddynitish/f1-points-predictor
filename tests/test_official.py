import copy

import pytest

from f1_points.official import qualifying_rows

SOURCE = {'season': 2026, 'title_contains': 'SYNTHETIC', 'expected_rows': 2, 'teams': {'Example Team': 'example'}}
IDENTITIES = {'AAA': {'driver_id': 'alice', 'car_number': 1}, 'BBB': {'driver_id': 'bob', 'car_number': 2}}


def answer():
    return {
        'ok': True,
        'tier': 1,
        'data': [
            {
                'title': 'FORMULA 1 SYNTHETIC GRAND PRIX 2026 - QUALIFYING',
                'positions': ['1', 'RT'],
                'numbers': ['1', '2'],
                'drivers': ['Alice ExampleAAA', 'Bob ExampleBBB'],
                'teams': ['Example Team', 'Example Team'],
            }
        ],
    }


def test_nonnumeric_rank_is_missing_without_dropping_driver():
    rows = qualifying_rows(answer(), SOURCE, IDENTITIES)
    assert len(rows) == 2
    assert rows[0]['position'] == '1'
    assert 'position' not in rows[1]
    assert rows[1]['Driver']['driverId'] == 'bob'
    assert 'Results' not in rows[0]


@pytest.mark.parametrize(
    'change',
    [
        'session',
        'year',
        'event',
        'partial',
        'unequal',
        'code',
        'number',
        'duplicate',
        'rank',
        'team',
        'failed',
        'truncated',
    ],
)
def test_untrusted_table_rejected(change):
    result = copy.deepcopy(answer())
    table = result['data'][0]
    if change == 'session':
        table['title'] = table['title'].replace('QUALIFYING', 'SPRINT QUALIFYING')
    elif change == 'year':
        table['title'] = table['title'].replace('2026', '2025')
    elif change == 'event':
        table['title'] = table['title'].replace('SYNTHETIC', 'OTHER')
    elif change == 'partial':
        for key in ('positions', 'numbers', 'drivers', 'teams'):
            table[key].pop()
    elif change == 'unequal':
        table['numbers'].pop()
    elif change == 'code':
        table['drivers'][1] = 'Unknown DriverZZZ'
    elif change == 'number':
        table['numbers'][1] = '99'
    elif change == 'duplicate':
        table['drivers'][1] = table['drivers'][0]
    elif change == 'rank':
        table['positions'][1] = '1'
    elif change == 'team':
        table['teams'][1] = 'Unknown'
    elif change == 'failed':
        result['ok'] = False
    elif change == 'truncated':
        result['truncated'] = True
    with pytest.raises(ValueError):
        qualifying_rows(result, SOURCE, IDENTITIES)


def test_due_enrichment_has_provenance_and_excludes_future_identities(tmp_path):
    import json
    from datetime import UTC, datetime

    from f1_points.official import enrich_due_events

    normalized = tmp_path / 'normalized'
    normalized.mkdir()
    event = {
        'event_id': '2026-17',
        'season': 2026,
        'round': 17,
        'circuit_id': 'synthetic',
        'race_start_utc': '2026-10-11T12:00:00+00:00',
        'qualifying_scheduled_start_utc': '2026-10-10T13:00:00+00:00',
    }
    path = normalized / '2026-17.json'
    original = {'event': event, 'entries': [], 'labels': [], 'manifests': []}
    path.write_text(json.dumps(original))
    previous = {
        'event': {**event, 'round': 16, 'event_id': '2026-16'},
        'entries': [{**v, 'driver_code': k} for k, v in IDENTITIES.items()],
        'labels': [],
    }
    (normalized / '2026-16.json').write_text(json.dumps(previous))
    future = {
        'event': {**event, 'round': 18},
        'entries': [{'driver_code': 'AAA', 'driver_id': 'wrong', 'car_number': 99}],
    }
    (normalized / '2026-18.json').write_text(json.dumps(future))
    source = {**SOURCE, 'round': 17, 'circuit_id': 'synthetic', 'race': '1234', 'slug': 'synthetic'}
    config = tmp_path / 'sources.json'
    config.write_text(json.dumps({'events': {'2026-17': source}, 'recipe': 'recipe.json'}))
    manifest = {
        'source_url': 'https://www.formula1.com/example/qualifying',
        'fetched_at': '2026-10-10T16:00:00+00:00',
        'sha256': 'synthetic',
    }
    calls = []

    def call(*args):
        calls.append(args)
        return answer(), manifest

    now = datetime(2026, 10, 10, 16, tzinfo=UTC)
    assert enrich_due_events(normalized, tmp_path / 'archives', config, now=now, call=call) == [manifest]
    record = json.loads(path.read_text())
    assert record['entries'][0]['driver_id'] == 'alice'
    assert record['labels'] == []
    assert record['manifests'] == [manifest]
    assert record['event']['qualifying_source'] == manifest['source_url']
    archive = tmp_path / 'archives'
    archive.mkdir()
    (archive / '2026-17-prospective.json').write_text('unchanged')
    assert enrich_due_events(normalized, archive, config, now=now, call=call) == []
    assert len(calls) == 1
    assert (
        enrich_due_events(normalized, tmp_path / 'other', config, now=datetime(2026, 10, 11, 13, tzinfo=UTC), call=call)
        == []
    )
    assert len(calls) == 1


def test_call_caches_full_response_and_uses_isolated_recipe(tmp_path):
    import json
    import subprocess

    from f1_points.official import call_official

    recipe = tmp_path / 'recipe.json'
    recipe.write_text('{"name":"f1-official"}')
    body = json.dumps(answer())
    seen = []

    def run(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=body, stderr='')

    source = {**SOURCE, 'race': '1234', 'slug': 'synthetic'}
    result, manifest = call_official(source, recipe, tmp_path / 'cache', run=run)
    saved = json.loads((tmp_path / 'cache' / f'{manifest["sha256"]}.json').read_text())
    assert saved['body'] == body
    assert result['ok']
    assert 'API_ANYTHING_HOME' in seen[0][1]['env']
    assert manifest['recipe_sha256']
    assert seen[0][1]['timeout'] == 90
