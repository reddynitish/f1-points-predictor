"""Milestone A commands. No training or final-test evaluation."""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .collection import audit_event, fetch_races, session_rows
from .data import SnapshotClient
from .experiments import run_sealed_evaluation, run_selection
from .features import FEATURE_COLUMNS, apply_qualifying_overrides, build_features, build_labels, load_normalized

logger = logging.getLogger('f1_points')
# 2018–2025 is the study period; 2026 is prospective history/shadow evaluation, never used for tuning.
PROSPECTIVE_SEASON = 2026


def _fail(report, **entry):
    """Record a coverage failure and surface it immediately instead of only in the report."""
    report['failures'].append(entry)
    logger.warning('collection failure: %s', entry)


def build_dataset(args):
    """Write physically separate feature and label files plus a committed missingness/lineage report."""
    events, entries, labels = load_normalized(args.input)
    entries = apply_qualifying_overrides(entries, args.overrides)
    features = build_features(events, entries, labels)
    target = build_labels(entries, labels)
    args.output.mkdir(parents=True, exist_ok=True)
    features.to_parquet(args.output / 'features.parquet', index=False)
    target.to_parquet(args.output / 'labels.parquet', index=False)
    report = {
        'schema_version': 1,
        'generated_at': datetime.now(UTC).isoformat(),
        'feature_columns': FEATURE_COLUMNS,
        'rows': len(features),
        'labeled_rows': len(target),
        'events': int(features['event_id'].nunique()),
        'rows_by_season': {str(k): int(v) for k, v in features.groupby('season').size().items()},
        'missing_by_feature': {c: int(features[c].isna().sum()) for c in FEATURE_COLUMNS},
        'overrides_applied': sum(1 for _ in open(args.overrides)) - 1,
        'lineage': 'history features use labels of strictly earlier events only; see tests/test_leakage.py',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    logger.info('dataset rows=%d labeled=%d report=%s', len(features), len(target), args.report)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    collect = commands.add_parser('collect')
    collect.add_argument('--start', type=int, default=2018)
    collect.add_argument('--end', type=int, default=2025)
    collect.add_argument('--round', type=int)
    collect.add_argument('--offline', action='store_true')
    collect.add_argument('--cache', type=Path, default=Path('data/snapshots'))
    collect.add_argument('--output', type=Path, default=Path('data/normalized'))
    collect.add_argument('--report', type=Path, default=Path('reports/coverage.json'))
    dataset = commands.add_parser('build-dataset')
    dataset.add_argument('--input', type=Path, default=Path('data/normalized'))
    dataset.add_argument('--overrides', type=Path, default=Path('overrides/qualifying.csv'))
    dataset.add_argument('--output', type=Path, default=Path('data/dataset'))
    dataset.add_argument('--report', type=Path, default=Path('reports/dataset.json'))
    selection = commands.add_parser('select', help='development model selection; never reads the test season')
    selection.add_argument('--dataset', type=Path, default=Path('data/dataset'))
    selection.add_argument('--report', type=Path, default=Path('reports/experiments/development.json'))
    selection.add_argument('--config', type=Path, default=Path('configs/final.json'))
    sealed = commands.add_parser('evaluate', help='one-time sealed test evaluation with the committed frozen config')
    sealed.add_argument('--dataset', type=Path, default=Path('data/dataset'))
    sealed.add_argument('--config', type=Path, default=Path('configs/final.json'))
    sealed.add_argument('--report', type=Path, default=Path('reports/experiments/test_2025.json'))
    sealed.add_argument('--predictions', type=Path, default=Path('reports/experiments/test_2025_predictions.csv'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    if args.command == 'build-dataset':
        return build_dataset(args)
    if args.command == 'select':
        report = run_selection(args.dataset, args.report, args.config)
        logger.info(
            'selected=%s calibration=%s report=%s', report['selected'], report['calibration']['selected'], args.report
        )
        return 0
    if args.command == 'evaluate':
        report = run_sealed_evaluation(args.dataset, args.config, args.report, args.predictions)
        logger.info('sealed evaluation written to %s', args.report)
        return 0
    if not 2018 <= args.start <= args.end <= PROSPECTIVE_SEASON:
        parser.error(f'Seasons must be within 2018–{PROSPECTIVE_SEASON}')
    if args.round is not None and args.round < 1:
        parser.error('Round must be positive')
    client = SnapshotClient(args.cache)
    report = {
        'schema_version': 1,
        'generated_at': datetime.now(UTC).isoformat(),
        'study': {'start': args.start, 'end': args.end, 'round': args.round},
        'events': [],
        'failures': [],
        'manifests': [],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for year in range(args.start, args.end + 1):
        try:
            schedule, manifests = fetch_races(client, f'{year}.json', offline=args.offline)
            report['manifests'].extend(manifests)
        except Exception as error:
            _fail(report, season=year, stage='schedule', error=str(error))
            continue
        selected = [race for race in schedule if args.round is None or int(race['round']) == args.round]
        if not selected:
            _fail(report, season=year, stage='selection', error='No matching events')
            continue
        sessions = {}
        for name, key in [('qualifying', 'QualifyingResults'), ('results', 'Results')]:
            endpoint = f'{year}/{args.round}/{name}.json' if args.round else f'{year}/{name}.json'
            try:
                races, manifests = fetch_races(client, endpoint, offline=args.offline)
                report['manifests'].extend(manifests)
                sessions[name] = session_rows(races, key)
            except Exception as error:
                _fail(report, season=year, stage=name, error=str(error))
                sessions[name] = {}
        for race in selected:
            number = int(race['round'])
            try:
                coverage, normalized = audit_event(
                    race, sessions['qualifying'].get(number, []), sessions['results'].get(number, [])
                )
                normalized['manifests'] = [m for m in report['manifests'] if f'/{year}' in m['source_url']]
                fetched_at = [m['fetched_at'] for m in normalized['manifests'] if '/results.json' in m['source_url']]
                for label in normalized['labels']:
                    label['fetched_at'] = max(fetched_at) if fetched_at else None
                (args.output / f'{coverage["event_id"]}.json').write_text(json.dumps(normalized, indent=2) + '\n')
                report['events'].append(coverage)
            except Exception as error:
                _fail(report, season=year, round=number, stage='normalize', error=str(error))
        logger.info('%s: audited %d scheduled events', year, len(selected))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    logger.info('report=%s events=%d failures=%d', args.report, len(report['events']), len(report['failures']))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
