import pandas as pd
import pytest

from f1_points.features import FEATURE_COLUMNS, FORBIDDEN_COLUMNS, build_features, build_labels


def fixture():
    """Three races, one team with two teammates (a, b) and one rival (c). Driver d debuts in race 3."""
    events = pd.DataFrame(
        [
            {
                'event_id': f'2024-0{n}',
                'season': 2024,
                'round': n,
                'circuit_id': f'c{n}',
                'race_start_utc': f'2024-0{n}-10T15:00:00+00:00',
                'qualifying_scheduled_start_utc': f'2024-0{n}-09T15:00:00+00:00',
            }
            for n in (1, 2, 3)
        ]
    )
    teams = {'a': 'team', 'b': 'team', 'c': 'rival', 'd': 'rival'}
    entries, labels = [], []
    points = {1: {'a': 25, 'b': 0, 'c': 18}, 2: {'a': 0, 'b': 0, 'c': 0}, 3: {'a': 10, 'b': 8, 'c': 0, 'd': 1}}
    for n, results in points.items():
        for rank, (driver, value) in enumerate(results.items(), start=1):
            entries.append(
                {
                    'event_id': f'2024-0{n}',
                    'driver_id': driver,
                    'constructor_id': teams[driver],
                    'qualifying_rank': rank,
                    'qualifying_available': True,
                }
            )
            labels.append(
                {
                    'event_id': f'2024-0{n}',
                    'driver_id': driver,
                    'race_points': float(value),
                    'final_position': rank,
                    'result_status': 'Finished' if driver != 'c' or n != 2 else 'Engine',
                }
            )
    return events, pd.DataFrame(entries), pd.DataFrame(labels)


def row(features, event_id, driver_id):
    return features.set_index(['event_id', 'driver_id']).loc[(event_id, driver_id)]


def test_target_race_outcome_changes_labels_not_features():
    events, entries, labels = fixture()
    before = build_features(events, entries, labels)
    mutated = labels.copy()
    mutated.loc[mutated['event_id'] == '2024-03', 'race_points'] = 0.0
    after = build_features(events, entries, mutated)
    target = before['event_id'] == '2024-03'
    pd.testing.assert_frame_equal(before[target].reset_index(drop=True), after[target].reset_index(drop=True))
    assert not build_labels(entries, labels).equals(build_labels(entries, mutated))


def test_future_event_does_not_change_earlier_features():
    events, entries, labels = fixture()
    full = build_features(events, entries, labels)
    truncated = build_features(
        events[events['round'] < 3], entries[entries['event_id'] != '2024-03'], labels[labels['event_id'] != '2024-03']
    )
    earlier = full[full['round'] < 3].reset_index(drop=True)
    pd.testing.assert_frame_equal(earlier, truncated.reset_index(drop=True))


def test_teammates_share_prior_event_team_aggregate():
    events, entries, labels = fixture()
    features = build_features(events, entries, labels)
    a, b = row(features, '2024-03', 'a'), row(features, '2024-03', 'b')
    # Prior team rows: race 1 (25, 0) and race 2 (0, 0) -> 1 positive of 4.
    assert a['constructor_points_rate_last5_events'] == b['constructor_points_rate_last5_events'] == 0.25
    assert a['constructor_history_events'] == 2


def test_shuffled_inputs_give_identical_features():
    events, entries, labels = fixture()
    expected = build_features(events, entries, labels)
    shuffled = build_features(
        events.sample(frac=1, random_state=1),
        entries.sample(frac=1, random_state=2),
        labels.sample(frac=1, random_state=3),
    )
    pd.testing.assert_frame_equal(expected, shuffled)


def test_rookie_history_is_missing_not_zero():
    events, entries, labels = fixture()
    d = row(build_features(events, entries, labels), '2024-03', 'd')
    assert d['rookie'] == 1
    assert d['driver_history_count'] == 0
    assert pd.isna(d['driver_points_rate_last5'])
    first = row(build_features(events, entries, labels), '2024-01', 'a')
    assert first['constructor_new'] == 1 and pd.isna(first['constructor_points_rate_last5_events'])


def test_driver_form_uses_prior_races_only():
    events, entries, labels = fixture()
    c = row(build_features(events, entries, labels), '2024-03', 'c')
    assert c['driver_points_rate_last5'] == 0.5
    assert c['driver_dnf_rate_last5'] == 0.5
    assert c['driver_finish_mean_last5'] == 3


def test_feature_allowlist_excludes_forbidden_columns():
    assert not FORBIDDEN_COLUMNS & set(FEATURE_COLUMNS)
    events, entries, labels = fixture()
    assert not FORBIDDEN_COLUMNS & set(build_features(events, entries, labels).columns)


def test_history_after_cutoff_is_rejected():
    events, entries, labels = fixture()
    events.loc[events['round'] == 2, 'race_start_utc'] = '2024-03-12T00:00:00+00:00'
    with pytest.raises(ValueError, match='precede cutoff'):
        build_features(events, entries, labels)


def test_unlabeled_entries_are_dropped_from_labels():
    events, entries, labels = fixture()
    target = build_labels(entries, labels[labels['driver_id'] != 'd'])
    assert 'd' not in set(target['driver_id'])
    assert set(target['scored_points']) <= {0, 1}


def test_renamed_team_inherits_lineage_history_but_keeps_original_id():
    events, entries, labels = fixture()
    entries.loc[(entries['event_id'] == '2024-03') & (entries['constructor_id'] == 'team'), 'constructor_id'] = 'team'
    entries.loc[entries['constructor_id'] == 'rival', 'constructor_id'] = 'sauber'
    entries.loc[(entries['event_id'] == '2024-03') & (entries['constructor_id'] == 'sauber'), 'constructor_id'] = 'audi'
    c = row(build_features(events, entries, labels), '2024-03', 'c')
    assert c['constructor_id'] == 'audi'
    assert c['constructor_new'] == 0
    assert c['constructor_points_rate_last5_events'] == 0.5
