import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_leakage import fixture

from f1_points.live import forecast_due as real_forecast_due
from f1_points.live import score_archives as real_score_archives
from f1_points.live import scorecard_markdown, should_forecast, update_readme


# Synthetic events run under a simulated clock; no real publication claim is made by these unit tests.
def forecast_due(*args, **kwargs):
    kwargs.setdefault('clock', lambda: args[7])
    return real_forecast_due(*args, **kwargs)


def score_archives(*args, **kwargs):
    kwargs.setdefault('publication_lookup', lambda _: '2024-03-09T18:01:00+00:00')
    return real_score_archives(*args, **kwargs)


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


def test_fit_crossing_race_start_never_archives_as_live(tmp_path):
    events, entries, labels = fixture()
    pending = labels[labels['event_id'] != '2024-03']
    started = datetime(2024, 3, 10, 14, 59, tzinfo=UTC)
    finished = datetime(2024, 3, 10, 15, 1, tzinfo=UTC)
    written = forecast_due(
        events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, started, clock=lambda: finished
    )
    assert written == []
    assert not list(tmp_path.glob('*.json'))


def test_archive_needs_a_pre_start_commit_to_enter_live_scorecard(tmp_path):
    events, entries, labels = fixture()
    pending = labels[labels['event_id'] != '2024-03']
    now = datetime(2024, 3, 9, 18, tzinfo=UTC)
    forecast_due(events, entries, pending, CONFIG, tmp_path, CONFIG_PATH, 2024, now)
    assert score_archives(tmp_path, labels, publication_lookup=lambda _: None) == []
    assert score_archives(tmp_path, labels, publication_lookup=lambda _: EVENT['race_start_utc']) == []


def test_first_commit_evidence_requires_unchanged_content(tmp_path):
    import os
    import subprocess

    from f1_points.live import archive_commit_time

    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    path = tmp_path / 'forecast.json'
    path.write_text('{"invented": true}\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'forecast.json'], check=True)
    subprocess.run(
        [
            'git',
            '-C',
            str(tmp_path),
            '-c',
            'user.name=Fixture',
            '-c',
            'user.email=fixture@example.invalid',
            '-c',
            'commit.gpgsign=false',
            'commit',
            '-m',
            'synthetic test archive',
        ],
        env={
            **os.environ,
            'GIT_AUTHOR_DATE': '2024-03-09T18:01:00+00:00',
            'GIT_COMMITTER_DATE': '2024-03-09T18:01:00+00:00',
        },
        check=True,
        capture_output=True,
    )
    assert archive_commit_time(path) == '2024-03-09T18:01:00+00:00'
    path.write_text('{"invented": false}\n')
    assert archive_commit_time(path) is None
