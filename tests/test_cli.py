import json
import logging

from f1_points import cli


def test_offline_missing_cache_logs_failure_and_exits_nonzero(tmp_path, monkeypatch, caplog):
    report = tmp_path / 'coverage.json'
    monkeypatch.setattr(
        'sys.argv',
        [
            'f1_points',
            'collect',
            '--offline',
            '--start',
            '2024',
            '--end',
            '2024',
            '--cache',
            str(tmp_path / 'empty'),
            '--output',
            str(tmp_path / 'out'),
            '--report',
            str(report),
        ],
    )
    with caplog.at_level(logging.WARNING, logger='f1_points'):
        assert cli.main() == 1
    assert 'collection failure' in caplog.text
    saved = json.loads(report.read_text())
    assert saved['failures'][0]['stage'] == 'schedule'
    assert saved['events'] == []


def test_seasons_beyond_prospective_rejected(monkeypatch):
    import pytest

    monkeypatch.setattr('sys.argv', ['f1_points', 'collect', '--start', '2027', '--end', '2027'])
    with pytest.raises(SystemExit):
        cli.main()


def test_history_stage_failure_replaces_stale_health_and_keeps_last_success(tmp_path, monkeypatch):
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'health.json').write_text(json.dumps({'status': 'ok', 'last_success_at': '2026-10-01T00:00:00+00:00'}))
    report = tmp_path / 'history.json'
    report.write_text(json.dumps({'failures': [{'stage': 'schedule', 'error': 'HTTP 503'}]}))
    monkeypatch.setattr(
        'sys.argv',
        [
            'f1_points',
            'live-failure',
            '--stage',
            'history_bootstrap',
            '--report',
            str(report),
            '--scorecard',
            str(public),
            '--live-root',
            str(tmp_path / 'runs'),
        ],
    )
    assert cli.main() == 0
    health = json.loads((public / 'health.json').read_text())
    assert health['status'] == 'pipeline_failed'
    assert health['failed_stage'] == 'history_bootstrap'
    assert health['failures'][0]['error'] == 'HTTP 503'
    assert health['last_success_at'] == '2026-10-01T00:00:00+00:00'
    assert list((tmp_path / 'runs').glob('*/health.json'))
