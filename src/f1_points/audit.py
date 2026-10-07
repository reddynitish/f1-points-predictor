"""Read-only comparison of qualifying classifications and sprint starting grids."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .collection import fetch_races, session_rows
from .data import SnapshotClient


def compare_sprint_sessions(qualifying, sprint, season):
    q = session_rows(qualifying, 'QualifyingResults')
    s = session_rows(sprint, 'SprintResults')
    comparisons = []
    for number, rows in sorted(s.items()):
        qranks = {r['Driver']['driverId']: int(r['position']) for r in q.get(number, [])}
        sranks = {r['Driver']['driverId']: int(r['grid']) for r in rows}
        common = sorted(qranks.keys() & sranks.keys())
        comparisons.append(
            {
                'event_id': f'{season}-{number:02d}',
                'status': 'compared' if common else 'missing comparison',
                'common_drivers': len(common),
                'different_ranks': sum(qranks[d] != sranks[d] for d in common),
                'qualifying_pole': next((d for d, r in qranks.items() if r == 1), None),
                'sprint_grid_pole': next((d for d, r in sranks.items() if r == 1), None),
                'interpretation': 'qualifying sets sprint grid; penalties may change ranks'
                if season <= 2022
                else 'separate qualifying sessions',
            }
        )
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('data/sprint-audit'))
    parser.add_argument('--output', type=Path, default=Path('reports/sprint-audit.json'))
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    client = SnapshotClient(args.cache)
    rows, manifests = [], []
    for year in range(2021, 2026):
        qualifying, qm = fetch_races(client, f'{year}/qualifying.json', offline=args.offline)
        sprint, sm = fetch_races(client, f'{year}/sprint.json', offline=args.offline)
        rows.extend(compare_sprint_sessions(qualifying, sprint, year))
        manifests.extend(qm + sm)
    record = {
        'generated_at': datetime.now(UTC).isoformat(),
        'scope': '2021–2025 sprint events; sprint grid is a proxy, not an exact sprint-qualifying classification',
        'comparisons': rows,
        'manifests': manifests,
        'limitation': 'Different orders establish distinct endpoints on those events, not exact cutoff availability.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(f'Compared {len(rows)} sprint events; report: {args.output}')
    return int(any(r['status'] != 'compared' for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
