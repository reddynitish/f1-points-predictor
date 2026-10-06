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
