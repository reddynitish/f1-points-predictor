import pytest
from test_data import driver, schedule

from f1_points.collection import audit_event, fetch_races


class Pages:
    def __init__(self):
        self.paths = []

    def get(self, path, **kwargs):
        self.paths.append(path)
        offset = 0 if 'offset=0' in path else 1
        return {
            'MRData': {
                'total': '2',
                'limit': '1',
                'offset': str(offset),
                'RaceTable': {'Races': [{'round': str(offset + 1)}]},
            }
        }, {'sha256': str(offset)}


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


def test_unlabeled_entries_are_reported():
    report, _ = audit_event(schedule(), [driver('a')], [])
    assert report['missing_labels'] == 1


def test_sprint_before_qualifying_limitation():
    from test_data import sprint_schedule

    report, _ = audit_event(sprint_schedule('SprintQualifying'), [driver('a')], [])
    assert report['weekend_format'] == 'sprint_qualifying'
    assert any('exclude from v1 features' in item for item in report['limitations'])


def test_sprint_grid_qualifying_limitation():
    from test_data import sprint_schedule

    report, _ = audit_event(sprint_schedule(), [driver('a')], [])
    assert 'qualifying sets sprint grid; race grid comes from sprint result' in report['limitations']


def test_repeated_rank_detail_names_drivers_and_gap():
    report, _ = audit_event(schedule(), [driver('a'), driver('b')], [])
    assert report['repeated_rank_drivers'] == ['a', 'b']
    assert report['unused_ranks'] == [2]


@pytest.mark.parametrize(
    'endpoint,key',
    [
        ('2024/qualifying.json', 'QualifyingResults'),
        ('2024/results.json', 'Results'),
        ('2024/sprint.json', 'SprintResults'),
    ],
)
def test_nonempty_truncated_session_page_is_rejected(endpoint, key):
    class Truncated:
        def get(self, *args, **kwargs):
            return {
                'MRData': {
                    'total': '20',
                    'limit': '100',
                    'offset': '0',
                    'RaceTable': {'Races': [{'round': '1', key: [driver('a')]}]},
                }
            }, {}

    with pytest.raises(ValueError, match='Truncated'):
        fetch_races(Truncated(), endpoint)


def test_session_pagination_counts_driver_rows_not_races():
    class Complete:
        def get(self, *args, **kwargs):
            return {
                'MRData': {
                    'total': '2',
                    'limit': '100',
                    'offset': '0',
                    'RaceTable': {'Races': [{'round': '1', 'QualifyingResults': [driver('a'), driver('b')]}]},
                }
            }, {}

    assert len(fetch_races(Complete(), '2024/qualifying.json')[0]) == 1


def test_changing_total_between_pages_is_rejected():
    class Changed(Pages):
        def get(self, path, **kwargs):
            payload, manifest = super().get(path, **kwargs)
            if 'offset=1' in path:
                payload['MRData']['total'] = '1'
            return payload, manifest

    with pytest.raises(ValueError, match='pagination'):
        fetch_races(Changed(), '2024.json')
