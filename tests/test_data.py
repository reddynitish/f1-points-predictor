import copy
import json

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
