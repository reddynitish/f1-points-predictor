import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from test_leakage import fixture

from f1_points.predict import QualifyingUnavailable, archive, predict_event

CONFIG_PATH = Path(__file__).parents[1] / 'configs' / 'final.json'
CONFIG = json.loads(CONFIG_PATH.read_text())
BEFORE_RACE = datetime(2024, 3, 9, 18, tzinfo=UTC)


def test_target_outcomes_do_not_change_predictions():
    events, entries, labels = fixture()
    first, meta = predict_event(events, entries, labels, '2024-03', CONFIG, now=BEFORE_RACE)
    flipped = labels.copy()
    flipped.loc[flipped['event_id'] == '2024-03', 'race_points'] = 0.0
    second, _ = predict_event(events, entries, flipped, '2024-03', CONFIG, now=BEFORE_RACE)
    pd.testing.assert_frame_equal(first, second)
    assert meta['training_last_event'] == '2024-02'
    assert meta['mode'] == 'retrospective_replay'  # labels already exist for the target


def test_unscored_future_event_is_prospective():
    events, entries, labels = fixture()
    _, meta = predict_event(
        events, entries, labels[labels['event_id'] != '2024-03'], '2024-03', CONFIG, now=BEFORE_RACE
    )
    assert meta['mode'] == 'prospective'
    assert any('d: no prior race history' == w for w in meta['warnings'])


def test_refuses_before_qualifying_is_published():
    events, entries, labels = fixture()
    upcoming = entries['event_id'] == '2024-03'
    with pytest.raises(QualifyingUnavailable):
        predict_event(
            events, entries[~upcoming], labels[labels['event_id'] != '2024-03'], '2024-03', CONFIG, now=BEFORE_RACE
        )


def test_refuses_when_rows_have_no_qualifying_classification():
    events, entries, labels = fixture()
    entries.loc[entries['event_id'] == '2024-03', 'qualifying_available'] = False
    with pytest.raises(QualifyingUnavailable):
        predict_event(events, entries, labels, '2024-03', CONFIG, now=BEFORE_RACE)


def test_prospective_archive_is_never_replaced(tmp_path):
    events, entries, labels = fixture()
    predictions, meta = predict_event(
        events, entries, labels[labels['event_id'] != '2024-03'], '2024-03', CONFIG, now=BEFORE_RACE
    )
    path = archive(predictions, meta, CONFIG_PATH, tmp_path)
    assert json.loads(path.read_text())['primary'] == 'p_B1'
    with pytest.raises(FileExistsError):
        archive(predictions, meta, CONFIG_PATH, tmp_path)


def test_archive_input_fingerprints_exclude_target_outcomes_and_are_order_invariant():
    events, entries, labels = fixture()
    _, first = predict_event(events, entries, labels, '2024-03', CONFIG, now=BEFORE_RACE)
    changed = labels.copy()
    changed.loc[changed['event_id'] == '2024-03', 'race_points'] = 0.0
    _, second = predict_event(
        events.iloc[::-1], entries.iloc[::-1], changed.iloc[::-1], '2024-03', CONFIG, now=BEFORE_RACE
    )
    assert first['input_fingerprints'] == second['input_fingerprints']
    assert first['coverage']['predicted_drivers'] == 4
    changed.loc[changed['event_id'] == '2024-02', 'race_points'] = 99.0
    _, third = predict_event(events, entries, changed, '2024-03', CONFIG, now=BEFORE_RACE)
    assert first['input_fingerprints']['training_sha256'] != third['input_fingerprints']['training_sha256']


def test_normalized_source_inventory_retains_manifests_without_raw_data(tmp_path):
    from f1_points.predict import source_inventory

    manifest = {
        'source_url': 'https://example.invalid/2024.json',
        'fetched_at': '2024-03-01T00:00:00+00:00',
        'sha256': 'abc',
        'schema_version': 1,
    }
    record = {'event': {'season': 2024}, 'manifests': [manifest], 'entries': [{'driver_id': 'private-fixture'}]}
    (tmp_path / '2024-01.json').write_text(json.dumps(record))
    (tmp_path / '2024-02.json').write_text(json.dumps(record))
    inventory = source_inventory(tmp_path, None, 2025)
    assert inventory['manifests'] == [manifest]
    assert len(inventory['normalized_sha256']) == 2
    assert 'private-fixture' not in json.dumps(inventory)
