"""Milestone A commands. No training or final-test evaluation."""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .collection import audit_event, fetch_races, session_rows
from .data import SnapshotClient

logger = logging.getLogger('f1_points')
# 2018–2025 is the study period; 2026 is prospective history/shadow evaluation, never used for tuning.
PROSPECTIVE_SEASON = 2026


def _fail(report, **entry):
    """Record a coverage failure and surface it immediately instead of only in the report."""
    report['failures'].append(entry)
    logger.warning('collection failure: %s', entry)


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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
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
