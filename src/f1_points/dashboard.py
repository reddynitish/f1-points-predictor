"""Export a standalone dashboard from saved artifacts; no fitting or network access."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .features import KEY
from .live import valid_prospective

REPLAY_PATHS = {'v1': 'backtest-2026', 'v2': 'backtest-2026-v2', 'pre_race': 'backtest-2026-pre-race'}


def records(frame):
    return json.loads(frame.to_json(orient='records'))


def validate_predictions(frame, *, outcomes=True):
    required = [*KEY, 'qualifying_rank', 'p_B1', 'p_M1'] + (['scored_points'] if outcomes else [])
    if not set(required) <= set(frame.columns) or frame.empty:
        raise ValueError('Missing prediction columns or rows')
    if frame[KEY].isna().any().any() or frame.duplicated(KEY).any():
        raise ValueError('Missing or duplicate prediction keys')
    for name in ('p_B1', 'p_M1'):
        if not frame[name].between(0, 1).all():
            raise ValueError(f'Invalid probability in {name}')
    if outcomes and not frame['scored_points'].isin([0, 1]).all():
        raise ValueError('Invalid outcome label')


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def load_dashboard_data(root):
    root = Path(root)
    reports = root / 'reports'
    replays, hashes = {}, {}
    for name, directory in REPLAY_PATHS.items():
        prediction_path = reports / directory / 'predictions.csv'
        summary_path = reports / directory / 'summary.json'
        frame = pd.read_csv(prediction_path)
        validate_predictions(frame)
        replays[name] = {'predictions': records(frame), 'summary': read_json(summary_path)}
        for path in (prediction_path, summary_path):
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    archives = []
    for path in sorted((root / 'predictions').glob('*.json')):
        archive = read_json(path)
        frame = pd.DataFrame(archive['predictions'])
        validate_predictions(frame, outcomes=False)
        if archive['mode'] == 'prospective' and not valid_prospective(archive):
            raise ValueError(f'Invalid prospective timestamp: {path.name}')
        archive['predictions'] = records(frame)
        archives.append(archive)
        hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'schema_version': 1,
        'replays': replays,
        'archives': archives,
        'catalog': read_json(reports / 'event-catalog.json', {'events': []}),
        'scorecard': read_json(reports / 'live-2026/scorecard.json', {'races': []}),
        'health': read_json(reports / 'live-2026/health.json'),
        'diagnostics': read_json(reports / 'diagnostics/errors.json'),
        'source_hashes': hashes,
        'built_at': max(
            [r['summary']['generated_at'] for r in replays.values()]
            + [a['created_at'] for a in archives]
            + [read_json(reports / 'live-2026/health.json', {}).get('checked_at', '')]
        ),
    }


def build_dashboard(root, output, *, template_dir=None):
    data = load_dashboard_data(root)
    template_dir = Path(template_dir or Path(root) / 'web')
    payload = json.dumps(data, separators=(',', ':'), allow_nan=False)
    for original, escaped in (('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026')):
        payload = payload.replace(original, escaped)
    template = (template_dir / 'index.html').read_text()
    template = template.replace('/* DASHBOARD_CSS */', (template_dir / 'style.css').read_text(), 1)
    template = template.replace('/* DASHBOARD_JS */', (template_dir / 'app.js').read_text(), 1)
    template = template.replace('"DASHBOARD_DATA"', payload, 1)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('docs/dashboard/index.html'))
    args = parser.parse_args()
    print(build_dashboard(args.root, args.output))


if __name__ == '__main__':
    main()
