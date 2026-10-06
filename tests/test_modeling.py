import numpy as np
import pandas as pd
import pytest

from f1_points.modeling import (
    bootstrap_race_brier,
    candidates,
    chronological_calibration,
    fit_predict,
    make_splits,
    metrics,
    race_averaged_brier,
)


def test_splits_are_ordered_disjoint_and_exclude_test_season():
    splits = make_splits()
    for train, validation in splits:
        assert max(train) < validation
        assert validation not in train
        assert 2025 not in train and validation != 2025
    assert [v for _, v in splits] == [2021, 2022, 2023, 2024]


def test_race_averaged_brier_matches_hand_calculation():
    # Event A: errors 0.04 and 0.36 -> 0.2. Event B: one error 0.0. Race average 0.1, driver average 0.1333.
    frame = pd.DataFrame({'event_id': ['A', 'A', 'B'], 'scored_points': [1, 0, 1], 'p_points': [0.8, 0.6, 1.0]})
    assert race_averaged_brier(frame) == pytest.approx(0.1)
    assert metrics(frame)['driver_brier'] == pytest.approx(0.4 / 3)
    assert metrics(frame)['precision'] == pytest.approx(2 / 3)


def test_bootstrap_is_seeded_and_resamples_events():
    frame = pd.DataFrame(
        {
            'event_id': list('AABBCC'),
            'scored_points': [1, 0, 1, 0, 1, 0],
            'p_points': [0.9, 0.1, 0.6, 0.4, 0.5, 0.5],
            'p_ref': [0.5] * 6,
        }
    )
    first = bootstrap_race_brier(frame, ['p_points', 'p_ref'], reference='p_ref', resamples=200)
    assert first == bootstrap_race_brier(frame, ['p_points', 'p_ref'], reference='p_ref', resamples=200)
    low, high = first['difference_vs_p_ref']['p_points']
    assert low <= high < 0  # every event is better than the constant reference


def test_chronological_calibration_uses_only_earlier_seasons():
    rng = np.random.default_rng(0)
    oof = pd.DataFrame(
        {'season': [2021] * 50 + [2022] * 50, 'p_points': rng.uniform(0, 1, 100), 'scored_points': [0, 1] * 50}
    )
    result = chronological_calibration(oof)
    first = result[result['season'] == 2021]
    assert (first['p_calibrated'] == first['p_points']).all()
    changed = oof.copy()
    changed.loc[changed['season'] == 2022, 'scored_points'] = 1  # later labels cannot affect 2022 calibration
    again = chronological_calibration(changed)
    np.testing.assert_allclose(
        result[result['season'] == 2022]['p_calibrated'], again[again['season'] == 2022]['p_calibrated']
    )


def test_every_candidate_fits_on_a_tiny_frame():
    from test_leakage import fixture

    from f1_points.features import build_features, build_labels

    events, entries, labels = fixture()
    rows = build_features(events, entries, labels).merge(build_labels(entries, labels), on=['event_id', 'driver_id'])
    for candidate in candidates():
        p, _ = fit_predict(candidate, rows, rows)
        assert ((p >= 0) & (p <= 1)).all()
    assert len(candidates()) == 13
