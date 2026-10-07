import json
import shutil
from pathlib import Path

import pytest

from f1_points.portfolio import run_demo, verify_artifacts, write_manifest

ROOT = Path(__file__).parents[1]


def test_integrity_check_rejects_changed_saved_predictions(tmp_path):
    shutil.copytree(ROOT / 'reports', tmp_path / 'reports')
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    write_manifest(tmp_path)
    assert verify_artifacts(tmp_path)['status'] == 'verified'
    path = tmp_path / 'reports/backtest-2026/predictions.csv'
    path.write_text(path.read_text().replace('0.925,', '0.125,', 1))
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_artifacts(tmp_path)


def test_demo_is_deterministic_offline_and_separate_from_real_forecasts(tmp_path, monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError('Demo must never download data')

    monkeypatch.setattr(requests, 'get', forbidden)
    first = run_demo(ROOT, tmp_path / 'one')
    second = run_demo(ROOT, tmp_path / 'two')
    assert first['prediction_sha256'] == second['prediction_sha256']
    assert first['synthetic'] is True
    assert first['duration_seconds'] > 0
    saved = json.loads((tmp_path / 'one/predictions.json').read_text())
    assert len(saved['predictions']) == 4
    assert saved['synthetic'] is True


def test_verification_and_demo_work_when_resource_is_unavailable(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, 'resource', None)
    assert verify_artifacts(ROOT)['status'] == 'verified'
    assert run_demo(ROOT, tmp_path)['process_peak_rss_mib'] is None


def test_integrity_manifest_requires_sealed_and_source_evidence(tmp_path):
    shutil.copytree(ROOT / 'reports', tmp_path / 'reports')
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    manifest_path = write_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    required = {
        'reports/experiments/test_2025.json',
        'reports/experiments/test_2025_predictions.csv',
        'reports/experiments/development.json',
        'reports/coverage.json',
        'reports/coverage-2026.json',
    }
    assert required <= manifest['files'].keys()
    del manifest['files']['reports/experiments/test_2025.json']
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='missing required'):
        verify_artifacts(tmp_path)
