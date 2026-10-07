import pandas as pd
import pytest

from f1_points.analysis import error_analysis, run_ablations


def test_error_analysis_counts_failures_and_keeps_events_together():
    frame = pd.DataFrame(
        {
            'event_id': ['a', 'a', 'b', 'b'],
            'driver_id': ['x', 'y', 'x', 'y'],
            'constructor_id': ['t', 't', 't', 't'],
            'qualifying_rank': [1, 12, 2, None],
            'p_B1': [0.9, 0.2, 0.8, 0.3],
            'p_M1': [0.9, 0.2, 0.8, 0.3],
            'scored_points': [0, 1, 1, 0],
        }
    )
    result = error_analysis(frame)
    assert result['rows'] == 4 and result['events'] == 2
    assert result['confident_misses'][0]['driver_id'] == 'x'
    assert result['confident_misses'][0]['event_id'] == 'a'
    assert result['worst_races'][0]['event_id'] == 'a'
    assert result['segments']['qualifying_band'][-1]['group'] == 'missing'
    assert result['segments']['qualifying_band'][-1]['rows'] == 1
    assert result['race_brier_B1'] == pytest.approx((0.725 + 0.065) / 2)


def test_ablations_refuse_validation_on_spent_holdouts():
    with pytest.raises(ValueError, match='2021–2024'):
        run_ablations(pd.DataFrame(), seasons=(2025,))


def test_ablations_ignore_holdout_rows_and_keep_event_split():
    from test_leakage import fixture

    from f1_points.features import KEY, build_features, build_labels

    events, entries, labels = fixture()
    rows = build_features(events, entries, labels).merge(build_labels(entries, labels), on=KEY)
    rows['season'] = rows['round'].map({1: 2020, 2: 2020, 3: 2021})
    future = rows[rows['round'] == 3].copy()
    future['season'] = 2025
    future['event_id'] = '2025-01'
    rows = pd.concat([rows, future], ignore_index=True)
    before = run_ablations(rows, seasons=(2021,))
    rows.loc[rows['season'] == 2025, 'scored_points'] = 1
    rows.loc[rows['season'] == 2025, 'qualifying_rank'] = 99
    assert run_ablations(rows, seasons=(2021,)) == before
    assert before['folds'][0]['training_events'] == ['2024-01', '2024-02']
    assert before['folds'][0]['validation_events'] == ['2024-03']
