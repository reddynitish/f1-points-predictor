import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_leakage import fixture

from f1_points.live import forecast_due, score_archives, scorecard_markdown, should_forecast, update_readme

CONFIG_PATH = Path(__file__).parents[1] / 'configs' / 'final.json'
CONFIG = json.loads(CONFIG_PATH.read_text())
EVENT = {'race_start_utc': '2024-03-10T15:00:00+00:00', 'qualifying_scheduled_start_utc': '2024-03-09T15:00:00+00:00'}


@pytest.mark.parametrize(
    'now, has_labels, has_archive, expected',
    [
        (datetime(2024, 3, 9, 15, 30, tzinfo=UTC), False, False, False),  # qualifying may still be running
        (datetime(2024, 3, 9, 18, tzinfo=UTC), False, False, True),
        (datetime(2024, 3, 9, 18, tzinfo=UTC), False, True, False),  # already archived: never replaced
        (datetime(2024, 3, 9, 18, tzinfo=UTC), True, False, False),  # result already known
        (datetime(2024, 3, 10, 15, tzinfo=UTC), False, False, False),  # race started: too late to count
    ],
)
def test_should_forecast(now, has_labels, has_archive, expected):
    assert should_forecast(EVENT, has_labels, has_archive, now) is expected


def test_forecast_once_then_score_after_results(tmp_path):
    events, entries, labels = fixture()
    pending = labels[labels['event_id'] != '2024-03']
    now = datetime(2024, 3, 9, 18, tzinfo=UTC)
    written = forecast_due(events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, now)
    assert [p.name for p in written] == ['2024-03-prospective.json']
    assert forecast_due(events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, now) == []
    assert score_archives(tmp_path, pending) == []  # race not run yet
    races = score_archives(tmp_path, labels)
    assert races[0]['event_id'] == '2024-03' and races[0]['drivers'] == 4
    assert 0 <= races[0]['brier_B1'] <= 1
    assert '1 live race(s)' in scorecard_markdown(races)
    assert len(races[0]['outcomes']) == 4
    assert sum(r['scored_points'] for r in races[0]['outcomes']) == 3


def test_readme_section_is_replaced_between_markers(tmp_path):
    readme = tmp_path / 'README.md'
    readme.write_text('intro\n<!-- live-scorecard:start -->\nold\n<!-- live-scorecard:end -->\noutro\n')
    assert update_readme(readme, 'new table') is True
    assert readme.read_text() == 'intro\n<!-- live-scorecard:start -->\nnew table\n<!-- live-scorecard:end -->\noutro\n'
    assert update_readme(readme, 'new table') is False
    (tmp_path / 'bad.md').write_text('no markers')
    with pytest.raises(ValueError):
        update_readme(tmp_path / 'bad.md', 'x')


def test_partial_results_wait_for_every_archived_driver(tmp_path):
    events, entries, labels = fixture()
    pending = labels[labels['event_id'] != '2024-03']
    forecast_due(events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, datetime(2024, 3, 9, 18, tzinfo=UTC))
    partial = labels.drop(labels[labels['event_id'] == '2024-03'].index[-1])
    assert score_archives(tmp_path, partial) == []


def test_post_start_archive_cannot_count_as_live(tmp_path):
    events, entries, labels = fixture()
    pending = labels[labels['event_id'] != '2024-03']
    path = forecast_due(
        events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, datetime(2024, 3, 9, 18, tzinfo=UTC)
    )[0]
    record = json.loads(path.read_text())
    record['created_at'] = record['race_start_utc']
    path.write_text(json.dumps(record))
    assert score_archives(tmp_path, labels) == []


def test_health_exposes_missing_forecast_and_partial_results(tmp_path):
    from f1_points.live import operational_health

    events, entries, labels = fixture()
    health = operational_health(events, entries, labels, tmp_path, 2024, datetime(2024, 3, 11, tzinfo=UTC))
    assert health['events'][-1]['state'] == 'missed_forecast'
    assert health['events'][-1]['qualifying_drivers'] == 4


def test_live_pipeline_error_is_recorded_and_returns_failure(tmp_path, monkeypatch):
    from argparse import Namespace

    from f1_points import cli

    def broken(args):
        raise RuntimeError('upstream schema changed')

    monkeypatch.setattr(cli, '_run_live', broken)
    args = Namespace(scorecard=tmp_path / 'public', live_root=tmp_path / 'runs')
    assert cli.run_live(args) == 1
    health = json.loads((args.scorecard / 'health.json').read_text())
    assert health['status'] == 'pipeline_failed'
    assert health['failures'][0]['error'] == 'upstream schema changed'
