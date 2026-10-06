"""Milestone A commands. No training or final-test evaluation."""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .backtest import run_backtest, summarize, write_outputs
from .collection import audit_event, fetch_races, session_rows
from .data import SnapshotClient
from .experiments import run_sealed_evaluation, run_selection
from .features import (
    FEATURE_COLUMNS,
    GRID_FEATURES,
    SESSION_FEATURES,
    V2_PRE_RACE_FEATURES,
    V2_QUALIFYING_FEATURES,
    add_session_features,
    apply_qualifying_overrides,
    build_features,
    build_labels,
    load_normalized,
)
from .livetiming import BASE_URL as livetiming_base
from .livetiming import LiveTimingClient, event_sessions, match_meeting, season_meetings
from .predict import QualifyingUnavailable, archive, load_combined, predict_event

logger = logging.getLogger('f1_points')
# 2018–2025 is the study period; 2026 is prospective history/shadow evaluation, never used for tuning.
PROSPECTIVE_SEASON = 2026
V2_EXTRA = SESSION_FEATURES + GRID_FEATURES
# Pre-registered in docs/PREREGISTRATION_V2.md: v2 selects on 2021-2025 and is tested once on 2026.
FEATURE_SETS = {
    'v1': {},
    'v2': {'numeric': V2_QUALIFYING_FEATURES, 'seasons': (2021, 2022, 2023, 2024, 2025), 'test_season': 2026},
    'pre-race': {
        'numeric': V2_PRE_RACE_FEATURES,
        'seasons': (2021, 2022, 2023, 2024, 2025),
        'test_season': 2026,
        'baseline': 'grid_logistic',
        'cutoff': 'pre_race_grid',
    },
}


def _fail(report, **entry):
    """Record a coverage failure and surface it immediately instead of only in the report."""
    report['failures'].append(entry)
    logger.warning('collection failure: %s', entry)


def collect(client, start, end, round_number, offline, output):
    """Fetch (or replay) seasons, write normalized event records and return the coverage report."""
    report = {
        'schema_version': 1,
        'generated_at': datetime.now(UTC).isoformat(),
        'study': {'start': start, 'end': end, 'round': round_number},
        'events': [],
        'failures': [],
        'manifests': [],
    }
    output.mkdir(parents=True, exist_ok=True)
    for year in range(start, end + 1):
        try:
            schedule, manifests = fetch_races(client, f'{year}.json', offline=offline)
            report['manifests'].extend(manifests)
        except Exception as error:
            _fail(report, season=year, stage='schedule', error=str(error))
            continue
        selected = [race for race in schedule if round_number is None or int(race['round']) == round_number]
        if not selected:
            _fail(report, season=year, stage='selection', error='No matching events')
            continue
        sessions = {}
        for name, key in [('qualifying', 'QualifyingResults'), ('results', 'Results')]:
            endpoint = f'{year}/{round_number}/{name}.json' if round_number else f'{year}/{name}.json'
            try:
                races, manifests = fetch_races(client, endpoint, offline=offline)
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
                (output / f'{coverage["event_id"]}.json').write_text(json.dumps(normalized, indent=2) + '\n')
                report['events'].append(coverage)
            except Exception as error:
                _fail(report, season=year, round=number, stage='normalize', error=str(error))
        logger.info('%s: audited %d scheduled events', year, len(selected))
    return report


def build_dataset(args):
    """Write physically separate feature and label files plus a committed missingness/lineage report."""
    events, entries, labels = load_normalized(args.input)
    entries = apply_qualifying_overrides(entries, args.overrides)
    features = build_features(events, entries, labels)
    if args.sessions:
        features = add_session_features(features, entries, args.sessions)
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
        'missing_by_feature': {
            c: int(features[c].isna().sum()) for c in FEATURE_COLUMNS + (V2_EXTRA if args.sessions else [])
        },
        'overrides_applied': sum(1 for _ in open(args.overrides)) - 1,
        'lineage': 'history features use labels of strictly earlier events only; see tests/test_leakage.py',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    logger.info('dataset rows=%d labeled=%d report=%s', len(features), len(target), args.report)
    return 0


def collect_session_season(client, events, year, output, offline, schedule_cache=Path('data/fastf1')):
    """Write one live-timing record per normalized event of a season; returns coverage rows and failures."""
    rows, failures = [], []
    try:
        meetings = season_meetings(year, schedule_cache)
    except Exception as error:
        return rows, [{'season': year, 'stage': 'index', 'error': str(error)}]
    output.mkdir(parents=True, exist_ok=True)
    for event in events[events['season'] == year].sort_values('round').to_dict('records'):
        meeting = match_meeting(meetings, event['race_start_utc']) if event['race_start_utc'] else None
        if meeting is None:
            failures.append({'event_id': event['event_id'], 'stage': 'match', 'error': 'no archive meeting'})
            continue
        try:
            record = event_sessions(client, meeting, offline=offline)
        except Exception as error:
            failures.append({'event_id': event['event_id'], 'stage': 'sessions', 'error': str(error)})
            continue
        record['event_id'] = event['event_id']
        (output / f'{event["event_id"]}.json').write_text(json.dumps(record, indent=2, default=str) + '\n')
        weather = record['qualifying_weather']
        rows.append(
            {
                'event_id': event['event_id'],
                'meeting': record['meeting'],
                'practice_sessions': [p['session'] for p in record['practice']],
                'practice_drivers_with_lap': max(
                    (sum(v is not None for v in p['best_laps'].values()) for p in record['practice']), default=0
                ),
                'qualifying_weather_available': weather is not None,
                'qualifying_rain': weather['rain'] if weather else None,
            }
        )
    return rows, failures


def collect_sessions(args):
    events, _, _ = load_normalized(args.normalized)
    client = LiveTimingClient(args.cache)
    report = {'generated_at': datetime.now(UTC).isoformat(), 'source': livetiming_base, 'events': [], 'failures': []}
    for year in range(args.start, args.end + 1):
        rows, failures = collect_session_season(client, events, year, args.output, args.offline)
        report['events'] += rows
        for failure in failures:
            _fail(report, **failure)
        logger.info('%s: %d events with session data', year, len(rows))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    logger.info('report=%s events=%d failures=%d', args.report, len(report['events']), len(report['failures']))
    return 1 if report['failures'] else 0


def run_predict(args):
    live = args.live
    if live is None:
        # Fresh immutable cache per run: the audited snapshots are never overwritten with newer upstream data.
        run_dir = args.live_root / datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
        report = collect(
            SnapshotClient(run_dir / 'snapshots'), args.season, args.season, None, False, run_dir / 'normalized'
        )
        if report['failures']:
            logger.error('target season collection failed: %s', report['failures'])
            return 1
        live = run_dir / 'normalized'
    events, entries, labels = load_combined(args.base, live, args.season)
    event_id = f'{args.season}-{args.round:02d}'
    config = json.loads(args.config.read_text())
    try:
        predictions, metadata = predict_event(events, entries, labels, event_id, config, overrides=args.overrides)
    except QualifyingUnavailable as error:
        logger.error('%s', error)
        return 2
    path = archive(predictions, metadata, args.config, args.archive)
    print(f'{event_id} {metadata["circuit_id"]} [{metadata["mode"]}] trained through {metadata["training_last_event"]}')
    print(predictions.to_string(index=False, float_format=lambda v: f'{v:.3f}'))
    for warning in metadata['warnings']:
        print('warning:', warning)
    print(metadata['primary_rule'])
    logger.info('archived %s', path)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    collect_parser = commands.add_parser('collect')
    collect_parser.add_argument('--start', type=int, default=2018)
    collect_parser.add_argument('--end', type=int, default=2025)
    collect_parser.add_argument('--round', type=int)
    collect_parser.add_argument('--offline', action='store_true')
    collect_parser.add_argument('--cache', type=Path, default=Path('data/snapshots'))
    collect_parser.add_argument('--output', type=Path, default=Path('data/normalized'))
    collect_parser.add_argument('--report', type=Path, default=Path('reports/coverage.json'))
    dataset = commands.add_parser('build-dataset')
    dataset.add_argument('--input', type=Path, default=Path('data/normalized'))
    dataset.add_argument('--overrides', type=Path, default=Path('overrides/qualifying.csv'))
    dataset.add_argument('--output', type=Path, default=Path('data/dataset'))
    dataset.add_argument('--report', type=Path, default=Path('reports/dataset.json'))
    dataset.add_argument('--sessions', type=Path, help='live-timing records; adds v2 session and grid columns')
    selection = commands.add_parser('select', help='development model selection; never reads the test season')
    selection.add_argument('--dataset', type=Path, default=Path('data/dataset'))
    selection.add_argument('--report', type=Path, default=Path('reports/experiments/development.json'))
    selection.add_argument('--config', type=Path, default=Path('configs/final.json'))
    selection.add_argument('--feature-set', choices=sorted(FEATURE_SETS), default='v1')
    sealed = commands.add_parser('evaluate', help='one-time sealed test evaluation with the committed frozen config')
    sealed.add_argument('--dataset', type=Path, default=Path('data/dataset'))
    sealed.add_argument('--config', type=Path, default=Path('configs/final.json'))
    sealed.add_argument('--report', type=Path, default=Path('reports/experiments/test_2025.json'))
    sealed.add_argument('--predictions', type=Path, default=Path('reports/experiments/test_2025_predictions.csv'))
    forecast = commands.add_parser('predict', help='frozen-model forecast for one event after qualifying')
    forecast.add_argument('--season', type=int, required=True)
    forecast.add_argument('--round', type=int, required=True)
    forecast.add_argument('--base', type=Path, default=Path('data/normalized'))
    forecast.add_argument('--live-root', type=Path, default=Path('data/live'))
    forecast.add_argument('--live', type=Path, help='reuse an already fetched normalized target season')
    forecast.add_argument('--config', type=Path, default=Path('configs/final.json'))
    forecast.add_argument('--overrides', type=Path, default=Path('overrides/qualifying.csv'))
    forecast.add_argument('--archive', type=Path, default=Path('predictions'))
    sessions = commands.add_parser('collect-sessions', help='pre-qualifying practice laps and qualifying weather')
    sessions.add_argument('--start', type=int, default=2018)
    sessions.add_argument('--end', type=int, default=PROSPECTIVE_SEASON)
    sessions.add_argument('--offline', action='store_true')
    sessions.add_argument('--normalized', type=Path, default=Path('data/normalized'))
    sessions.add_argument('--cache', type=Path, default=Path('data/livetiming-snapshots'))
    sessions.add_argument('--output', type=Path, default=Path('data/livetiming'))
    sessions.add_argument('--report', type=Path, default=Path('reports/session-coverage.json'))
    replay = commands.add_parser('backtest', help='retrospective walk-forward replay of a completed season')
    replay.add_argument('--season', type=int, default=PROSPECTIVE_SEASON)
    replay.add_argument('--normalized', type=Path, default=Path('data/normalized'))
    replay.add_argument('--config', type=Path, default=Path('configs/final.json'))
    replay.add_argument('--overrides', type=Path, default=Path('overrides/qualifying.csv'))
    replay.add_argument('--output', type=Path, default=Path('reports/backtest-2026'))
    replay.add_argument('--sessions', type=Path, default=Path('data/livetiming'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    if args.command == 'build-dataset':
        return build_dataset(args)
    if args.command == 'collect-sessions':
        return collect_sessions(args)
    if args.command == 'backtest':
        events, entries, labels = load_normalized(args.normalized)
        config = json.loads(args.config.read_text())
        frame = run_backtest(events, entries, labels, args.season, config, args.overrides, args.sessions)
        summary = summarize(frame, args.season, args.config)
        write_outputs(frame, summary, args.output)
        logger.info('backtest races=%d rows=%d output=%s', summary['races'], summary['rows'], args.output)
        return 0
    if args.command == 'predict':
        return run_predict(args)
    if args.command == 'select':
        spec = FEATURE_SETS[args.feature_set]
        report = run_selection(args.dataset, args.report, args.config, **spec)
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
    report = collect(SnapshotClient(args.cache), args.start, args.end, args.round, args.offline, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    logger.info('report=%s events=%d failures=%d', args.report, len(report['events']), len(report['failures']))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
