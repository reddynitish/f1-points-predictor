"""Feasibility probe: bound qualifying 'Finalised' time from F1 live-timing archives via FastF1.

Evidence for the data-gate design discussion, not part of the adapter. Session status
times are stream offsets; each heartbeat pairs an offset with a UTC clock reading, so
every heartbeat yields one candidate anchor. The min/max anchors bound the estimate.
Archives with heartbeat UTC outside the event date (seen for 2018) are reported unusable.

    uv run python scripts/probe_session_timing.py --cache /tmp/ff1 2019:1 2024:21
"""

import argparse
import warnings

import fastf1
import pandas as pd
from fastf1.utils import to_timedelta

warnings.filterwarnings('ignore', message='`fastf1.api`')
from fastf1 import api  # noqa: E402


def _utc(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_convert('UTC') if stamp.tzinfo else stamp.tz_localize('UTC')


def probe(season, round_number):
    session = fastf1.get_session(season, round_number, 'Q')
    heartbeat = api.fetch_page(session.api_path, 'heartbeat')
    status = api.session_status_data(session.api_path)
    anchors = pd.Series([_utc(line[1]['Utc']) - pd.Timedelta(to_timedelta(line[0])) for line in heartbeat])
    scheduled = _utc(session.date)  # FastF1 session dates are naive UTC
    finalised = [t for t, name in zip(status['Time'], status['Status'], strict=True) if name == 'Finalised']
    usable = abs((anchors.sort_values().iloc[len(anchors) // 2] - scheduled).total_seconds()) < 86400
    row = {
        'event': f'{season}-{round_number:02d}',
        'fastf1_scheduled_start_utc': scheduled.isoformat(),
        'anchor_spread': str(anchors.max() - anchors.min()),
        'usable_anchor': bool(usable),
    }
    if finalised and usable:
        row['finalised_earliest_utc'] = (anchors.min() + finalised[0]).isoformat()
        row['finalised_latest_utc'] = (anchors.max() + finalised[0]).isoformat()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--cache', required=True, help='FastF1 cache directory (keep outside the repo)')
    parser.add_argument('events', nargs='+', help='SEASON:ROUND pairs')
    args = parser.parse_args()
    fastf1.Cache.enable_cache(args.cache)
    fastf1.set_log_level('ERROR')
    for item in args.events:
        season, round_number = (int(part) for part in item.split(':'))
        print(probe(season, round_number), flush=True)


if __name__ == '__main__':
    main()
