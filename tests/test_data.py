
import pytest

from f1_points.data import SnapshotClient, normalize_event


def driver(name, rank='1', **extra):
    return {'Driver': {'driverId': name}, 'Constructor': {'constructorId': 'team'},
            'position': rank, **extra}


def schedule():
    return {'season': '2024', 'round': '1', 'Circuit': {'circuitId': 'test'},
            'date': '2024-03-02', 'time': '15:00:00Z',
            'Qualifying': {'date': '2024-03-01', 'time': '15:00:00Z'}}


def test_missing_qualifying_preserves_race_only_driver():
    event, entries, labels = normalize_event(schedule(), [], [driver('a', points='0', status='DNS')])
    assert entries[0]['qualifying_rank'] is None
    assert entries[0]['qualifying_available'] is False
    assert 'race_points' not in entries[0]
    assert labels[0]['race_points'] == 0
    assert event['qualifying_end_utc'] is None


def test_missing_q3_is_not_zero():
    _, entries, _ = normalize_event(schedule(), [driver('a', Q1='1:20.123')], [])
    assert entries[0]['q1_seconds'] == pytest.approx(80.123)
    assert entries[0]['q3_seconds'] is None


@pytest.mark.parametrize('rows', [[driver('a'), driver('a')], [driver('a', '0')],
                                 [driver('a', Q1='-1:20')]])
def test_invalid_qualifying_rejected(rows):
    with pytest.raises(ValueError):
        normalize_event(schedule(), rows, [])


class Response:
    status_code = 200
    headers = {}
    content = b'{"MRData": {"total": "0"}}'
    def raise_for_status(self):
        pass


def test_cache_reuse_offline_and_integrity(tmp_path):
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return Response()
    client = SnapshotClient(tmp_path, fetch=fetch, sleep=lambda _: None)
    first = client.get('2024.json')
    assert client.get('2024.json', offline=True) == first
    assert len(calls) == 1
    next(tmp_path.glob('*.json')).write_text('{}')
    with pytest.raises(ValueError, match='hash'):
        client.get('2024.json', offline=True)


def test_offline_missing_does_not_fetch(tmp_path):
    with pytest.raises(FileNotFoundError):
        SnapshotClient(tmp_path).get('2024.json', offline=True)


def test_three_attempts(tmp_path):
    import requests
    calls = []
    waits = []
    def fetch(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError('synthetic failure')
    with pytest.raises(requests.ConnectionError):
        SnapshotClient(tmp_path, fetch=fetch, sleep=waits.append).get('2024.json')
    assert len(calls) == 3
    assert waits == [1, 2]


def test_rate_limit_retry_after(tmp_path):
    import requests
    waits = []
    class Limited(Response):
        status_code = 429
        headers = {'Retry-After': '5'}
        def raise_for_status(self):
            raise requests.HTTPError('rate limited')
    responses = iter([Limited(), Response()])
    SnapshotClient(tmp_path, fetch=lambda *a, **k: next(responses), sleep=waits.append).get('2024.json')
    assert waits == [5, 1]


@pytest.mark.parametrize('points', ['nan', 'inf', '-1'])
def test_invalid_points_rejected(points):
    with pytest.raises(ValueError, match='label'):
        normalize_event(schedule(), [], [driver('a', points=points, status='Finished')])


def test_duplicate_result_driver_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        normalize_event(schedule(), [], [driver('a'), driver('a')])


def test_missing_session_start_stays_unknown():
    source = schedule()
    del source['Qualifying']
    source.pop('time')
    event, _, _ = normalize_event(source, [], [])
    assert event['race_start_utc'] is None
    assert event['qualifying_scheduled_start_utc'] is None


def test_constructor_comes_from_qualifying_when_results_differ():
    q = driver('a')
    race = driver('a', points='0', status='DNS')
    race['Constructor'] = {'constructorId': 'different'}
    _, entries, _ = normalize_event(schedule(), [q], [race])
    assert entries[0]['constructor_id'] == 'team'


def test_qualifying_row_without_position_retains_missing_rank():
    row = driver('a', Q1='1:20.123')
    del row['position']
    _, entries, _ = normalize_event(schedule(), [row], [])
    assert entries[0]['qualifying_available'] is True
    assert entries[0]['qualifying_rank'] is None


def test_empty_qualifying_time_is_missing():
    _, entries, _ = normalize_event(schedule(), [driver('a', Q1='')], [])
    assert entries[0]['q1_seconds'] is None


def test_subminute_qualifying_time():
    _, entries, _ = normalize_event(schedule(), [driver('a', Q1='53.904')], [])
    assert entries[0]['q1_seconds'] == pytest.approx(53.904)


def test_upstream_tied_ranks_are_preserved_for_audit():
    _, entries, _ = normalize_event(schedule(), [driver('a'), driver('b')], [])
    assert [row['qualifying_rank'] for row in entries] == [1, 1]


def sprint_schedule(extra_key=None, sprint_time='10:00:00Z'):
    source = schedule()
    source['Sprint'] = {'date': '2024-03-01', 'time': sprint_time}
    if extra_key:
        source[extra_key] = {'date': '2024-02-29', 'time': '15:00:00Z'}
    return source


@pytest.mark.parametrize('source, expected, determines', [
    (schedule(), 'conventional', 'race grid'),
    (sprint_schedule(), 'sprint_grid_from_qualifying', 'sprint grid'),
    (sprint_schedule('SprintShootout'), 'sprint_shootout', 'race grid'),
    (sprint_schedule('SprintQualifying'), 'sprint_qualifying', 'race grid'),
])
def test_weekend_format_semantics(source, expected, determines):
    event, _, _ = normalize_event(source, [], [])
    assert event['weekend_format'] == expected
    assert event['qualifying_determines'] == determines
    assert event['sprint_weekend'] is (expected != 'conventional')


def test_sprint_before_qualifying_is_detected_from_schedule():
    event, _, _ = normalize_event(sprint_schedule('SprintQualifying', '10:00:00Z'), [], [])
    assert event['sprint_scheduled_before_qualifying'] is True
    later, _, _ = normalize_event(sprint_schedule('SprintShootout', '18:00:00Z'), [], [])
    assert later['sprint_scheduled_before_qualifying'] is False


def test_sprint_order_unknown_without_times():
    source = sprint_schedule()
    del source['Sprint']['time']
    event, _, _ = normalize_event(source, [], [])
    assert event['sprint_scheduled_before_qualifying'] is None


def test_repeated_rank_rows_are_flagged_per_driver():
    _, entries, _ = normalize_event(schedule(), [driver('a'), driver('b'), driver('c', '2')], [])
    assert [row['qualifying_rank_repeated'] for row in entries] == [True, True, False]


def test_missing_rank_is_not_flagged_as_repeated():
    rows = [driver('a', Q1='1:20'), driver('b', Q1='1:21')]
    for row in rows:
        del row['position']
    _, entries, _ = normalize_event(schedule(), rows, [])
    assert not any(row['qualifying_rank_repeated'] for row in entries)
