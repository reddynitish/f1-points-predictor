import pytest
from f1_points.collection import fetch_races, audit_event
from test_data import schedule, driver


class Pages:
    def __init__(self):
        self.paths = []
    def get(self, path, **kwargs):
        self.paths.append(path)
        offset = 0 if 'offset=0' in path else 1
        return {'MRData': {'total': '2', 'limit': '1', 'offset': str(offset),
                          'RaceTable': {'Races': [{'round': str(offset + 1)}]}}}, {'sha256': str(offset)}


def test_pagination():
    client = Pages()
    races, manifests = fetch_races(client, '2024.json', offline=True)
    assert len(races) == len(manifests) == 2
    assert client.paths[-1].endswith('offset=1')


def test_coverage_contains_no_holdout_outcome_values():
    report, normalized = audit_event(schedule(), [driver('a')], [driver('a', points='25', status='Finished')])
    assert report['labels'] == 1
    assert 'race_points' not in report
    assert 'result_status' not in report
    assert report['cutoff_ready'] is False
    assert normalized['labels'][0]['race_points'] == 25


def test_truncated_page_is_rejected():
    class Empty:
        def get(self, *args, **kwargs):
            return {'MRData': {'total': '20', 'limit': '100', 'offset': '0', 'RaceTable': {'Races': []}}}, {}
    with pytest.raises(ValueError, match='Truncated'):
        fetch_races(Empty(), '2024.json')


def test_repeated_ranks_are_flagged():
    report, _ = audit_event(schedule(), [driver('a'), driver('b')], [])
    assert report['repeated_rank_rows'] == 1
    assert 'repeated upstream qualifying ranks require review' in report['limitations']
