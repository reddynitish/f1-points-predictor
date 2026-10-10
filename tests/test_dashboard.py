import json
from pathlib import Path

import pytest

from f1_points.dashboard import build_dashboard, load_dashboard_data

ROOT = Path(__file__).parents[1]


def test_export_is_self_contained_and_preserves_replay_labels(tmp_path):
    path = tmp_path / 'index.html'
    build_dashboard(ROOT, path)
    html = path.read_text()
    assert 'Past race example' in html
    assert 'https://fonts.' not in html
    assert '<script src=' not in html
    assert '2026-16' in html
    assert 'scored_points' in html


def test_invalid_probability_refuses_export(tmp_path):
    import shutil

    shutil.copytree(ROOT / 'reports', tmp_path / 'reports')
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    predictions = tmp_path / 'reports/backtest-2026/predictions.csv'
    predictions.write_text(predictions.read_text().replace('0.925,', '1.925,', 1))
    with pytest.raises(ValueError, match='probability'):
        load_dashboard_data(tmp_path)


def test_archive_text_cannot_close_json_script(tmp_path):
    import shutil

    shutil.copytree(ROOT / 'reports', tmp_path / 'reports')
    shutil.copytree(ROOT / 'configs', tmp_path / 'configs')
    (tmp_path / 'predictions').mkdir()
    record = json.loads(next((ROOT / 'predictions').glob('*.json')).read_text())
    record['warnings'] = ['</script><img src=x onerror=alert(1)>']
    (tmp_path / 'predictions/replay.json').write_text(json.dumps(record))
    build_dashboard(tmp_path, tmp_path / 'index.html', template_dir=ROOT / 'web')
    html = (tmp_path / 'index.html').read_text()
    assert '</script><img src=x' not in html
    assert '\\u003c/script' in html
    explanation = (tmp_path / 'machine-learning.html').read_text()
    assert '</script><img src=x' not in explanation
    assert '\\u003c/script' in explanation


def test_export_fingerprints_all_auxiliary_data_inputs():
    data = load_dashboard_data(ROOT)
    required = {
        'reports/event-catalog.json',
        'reports/live-2026/scorecard.json',
        'reports/live-2026/health.json',
        'reports/diagnostics/errors.json',
        'reports/coverage-2026.json',
    }
    assert required <= data['source_hashes'].keys()
    assert data['source_manifests']
    assert all(m['source_url'].startswith('https://') for m in data['source_manifests'])


def test_export_includes_linked_standalone_explanation(tmp_path):
    path = tmp_path / 'index.html'
    build_dashboard(ROOT, path)
    explanation = tmp_path / 'machine-learning.html'
    assert explanation.exists()
    main = path.read_text()
    ml = explanation.read_text()
    assert 'F1 Points-Scoring Predictor' in main
    assert 'href="machine-learning.html"' in main
    assert 'href="index.html"' in ml
    assert 'How the prediction works' in ml
    assert 'id="dashboard-data"' in ml
    assert '<script src=' not in ml
    assert '/* DASHBOARD_JS */' not in ml
    assert '"DASHBOARD_DATA"' not in ml
