"""Offline integrity verification and a small synthetic forecast demonstration."""

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .dashboard import REPLAY_PATHS, validate_predictions
from .features import KEY
from .modeling import race_averaged_brier
from .predict import predict_event

CONFIGS = {'v1': 'final.json', 'v2': 'v2.json', 'pre_race': 'pre-race.json'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(root):
    root = Path(root)
    paths = [root / 'configs' / name for name in CONFIGS.values()]
    for directory in REPLAY_PATHS.values():
        paths += [root / 'reports' / directory / name for name in ('predictions.csv', 'summary.json')]
    paths += [
        root / path
        for path in (
            'reports/sprint-audit.json',
            'reports/diagnostics/errors.json',
            'reports/diagnostics/ablations.json',
        )
        if (root / path).exists()
    ]
    payload = {
        'scope': 'Integrity of reviewed frozen configs and historical evaluation artifacts; not proof of authorship.',
        'files': {str(p.relative_to(root)): sha256(p) for p in paths},
    }
    path = root / 'reports/portfolio-manifest.json'
    path.write_text(json.dumps(payload, indent=2) + '\n')
    return path


def verify_artifacts(root):
    root = Path(root)
    manifest = json.loads((root / 'reports/portfolio-manifest.json').read_text())
    required = {
        *(f'configs/{name}' for name in CONFIGS.values()),
        *(
            f'reports/{directory}/{name}'
            for directory in REPLAY_PATHS.values()
            for name in ('predictions.csv', 'summary.json')
        ),
    }
    if not required <= manifest['files'].keys():
        raise ValueError('Integrity manifest is missing required historical artifacts')
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Manifest path leaves repository')
        if sha256(path) != expected:
            raise ValueError(f'Artifact hash mismatch: {name}')
    checked = []
    for key, directory in REPLAY_PATHS.items():
        frame = pd.read_csv(root / 'reports' / directory / 'predictions.csv')
        validate_predictions(frame)
        summary = json.loads((root / 'reports' / directory / 'summary.json').read_text())
        if summary['config_sha256'] != sha256(root / 'configs' / CONFIGS[key]):
            raise ValueError(f'Frozen config mismatch: {key}')
        if len(frame) != summary['rows'] or frame['event_id'].nunique() != summary['races']:
            raise ValueError(f'Coverage mismatch: {key}')
        for model in ('B1', 'M1'):
            actual = race_averaged_brier(frame, 'p_' + model)
            if abs(actual - summary['metrics'][model]['race_brier']) > 0.0001:
                raise ValueError(f'Saved prediction/summary mismatch: {key} {model}')
        checked.append(key)
    frames = [pd.read_csv(root / 'reports' / directory / 'predictions.csv') for directory in REPLAY_PATHS.values()]
    expected_keys = set(map(tuple, frames[0][KEY].to_numpy()))
    if any(set(map(tuple, frame[KEY].to_numpy())) != expected_keys for frame in frames[1:]):
        raise ValueError('Model comparisons do not cover identical prediction rows')
    return {
        'status': 'verified',
        'files': len(manifest['files']),
        'comparisons': checked,
        'brier_tolerance': 0.0001,
        'note': 'Metrics recomputed from rounded saved predictions; no model fitting or new test evaluation.',
    }


def run_demo(root, output):
    root, output = Path(root), Path(output)
    fixture = json.loads((root / 'tests/fixtures/demo.json').read_text())
    if fixture.get('synthetic') is not True:
        raise ValueError('Demo must be explicitly synthetic')
    config = json.loads((root / 'configs/final.json').read_text())
    started = time.perf_counter()
    predictions, metadata = predict_event(
        pd.DataFrame(fixture['events']),
        pd.DataFrame(fixture['entries']),
        pd.DataFrame(fixture['labels']),
        '2024-03',
        config,
        now=datetime(2024, 3, 9, 18, tzinfo=UTC),
    )
    validate_predictions(predictions, outcomes=False)
    prediction_json = predictions.round(8).to_json(orient='records')
    try:
        import resource

        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == 'darwin' else 1024)
    except ImportError:
        peak_rss = None
    measured = {
        'synthetic': True,
        'scope': 'Feature construction and two frozen-model CPU fits on invented fixture; not a production benchmark.',
        'duration_seconds': round(time.perf_counter() - started, 6),
        'process_peak_rss_mib': peak_rss,
        'memory_scope': 'Process lifetime maximum RSS, including Python/library imports; not incremental model memory.',
        'python': platform.python_version(),
        'platform': platform.platform(),
        'prediction_sha256': hashlib.sha256(prediction_json.encode()).hexdigest(),
        'config_sha256': sha256(root / 'configs/final.json'),
        'fixture_sha256': sha256(root / 'tests/fixtures/demo.json'),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'predictions.json').write_text(
        json.dumps({'synthetic': True, 'metadata': metadata, 'predictions': json.loads(prediction_json)}, indent=2)
        + '\n'
    )
    (output / 'performance.json').write_text(json.dumps(measured, indent=2) + '\n')
    return measured


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'demo', 'manifest'])
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('/tmp/f1-points-demo'))
    args = parser.parse_args()
    if args.command == 'manifest':
        print(write_manifest(args.root))
    else:
        result = verify_artifacts(args.root) if args.command == 'verify' else run_demo(args.root, args.output)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
