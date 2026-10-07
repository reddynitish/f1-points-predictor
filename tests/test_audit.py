from f1_points.audit import compare_sprint_sessions


def row(driver, **values):
    return {'Driver': {'driverId': driver}, **values}


def test_distinct_session_orders_are_reported_not_corrected():
    qualifying = [
        {'season': '2024', 'round': '1', 'QualifyingResults': [row('a', position='1'), row('b', position='2')]}
    ]
    sprint = [{'round': '1', 'SprintResults': [row('a', grid='2'), row('b', grid='1')]}]
    result = compare_sprint_sessions(qualifying, sprint, 2024)
    assert result[0]['qualifying_pole'] == 'a'
    assert result[0]['sprint_grid_pole'] == 'b'
    assert result[0]['different_ranks'] == 2
    assert result[0]['interpretation'] == 'separate qualifying sessions'


def test_early_sprint_format_and_missing_data_are_explicit():
    q = [{'round': '2', 'QualifyingResults': [row('a', position='1')]}]
    s = [{'round': '2', 'SprintResults': [row('a', grid='1')]}, {'round': '3', 'SprintResults': []}]
    result = compare_sprint_sessions(q, s, 2021)
    assert result[0]['interpretation'] == 'qualifying sets sprint grid; penalties may change ranks'
    assert result[1]['status'] == 'missing comparison'
