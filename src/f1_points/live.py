"""Unattended race-weekend loop: forecast after qualifying, score after the race, keep a public scorecard."""

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from .backtest import top10_hits
from .features import KEY
from .predict import QualifyingUnavailable, archive, predict_event

# Scheduling buffer only; a delay or reschedule still requires a published qualifying classification.
QUALIFYING_SETTLE = timedelta(hours=1)
CONFIDENT = 0.8
README_START, README_END = '<!-- live-scorecard:start -->', '<!-- live-scorecard:end -->'


def should_forecast(event, has_labels, has_archive, now):
    """Scheduling gate; published qualifying is checked separately by the predictor."""
    if has_labels or has_archive or not event.get('race_start_utc'):
        return False
    race_start = datetime.fromisoformat(event['race_start_utc'])
    qualifying = event.get('qualifying_scheduled_start_utc')
    settled = qualifying is not None and now >= datetime.fromisoformat(qualifying) + QUALIFYING_SETTLE
    return settled and now < race_start


def forecast_due(
    events, entries, labels, config, archive_dir, config_path, season, now, overrides=None, *, clock=None, sources=None
):
    """Archive a prospective forecast for every due event; returns written paths."""
    written = []
    labeled = set(labels['event_id'])
    for event in events[events['season'] == season].sort_values('round').to_dict('records'):
        path = Path(archive_dir) / f'{event["event_id"]}-prospective.json'
        if not should_forecast(event, event['event_id'] in labeled, path.exists(), now):
            continue
        try:
            predictions, metadata = predict_event(
                events, entries, labels, event['event_id'], config, now=now, overrides=overrides
            )
        except QualifyingUnavailable:
            continue  # qualifying not published yet; the next scheduled run will retry
        completed_at = clock() if clock else datetime.now(UTC)
        if metadata['mode'] == 'prospective' and completed_at < datetime.fromisoformat(event['race_start_utc']):
            metadata['created_at'] = completed_at.isoformat()
            if sources is not None:
                metadata['source_inventory'] = sources
            written.append(archive(predictions, metadata, config_path, archive_dir))
    return written


def archive_commit_time(path):
    """First commit adding this exact archive. Git time proves a local commit, not independent remote receipt."""
    path = Path(path).resolve()
    try:
        root = subprocess.check_output(
            ['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'], stderr=subprocess.DEVNULL, text=True
        ).strip()
        relative = str(path.relative_to(root))
        commits = subprocess.check_output(
            ['git', '-C', root, 'log', '--diff-filter=A', '--format=%H %cI', '--', relative],
            stderr=subprocess.DEVNULL,
            text=True,
        ).splitlines()
        if not commits:
            return None
        commit, stamp = commits[-1].split(' ', 1)
        original = subprocess.check_output(
            ['git', '-C', root, 'show', f'{commit}:{relative}'], stderr=subprocess.DEVNULL
        )
        return datetime.fromisoformat(stamp).isoformat() if original == path.read_bytes() else None
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def score_archives(archive_dir, labels, *, publication_lookup=archive_commit_time):
    """Grade every prospective forecast whose race result is published. Recomputed from scratch each run."""
    outcome = labels.assign(scored_points=(labels['race_points'] > 0).astype(int))[[*KEY, 'scored_points']]
    races = []
    for path in sorted(Path(archive_dir).glob('*-prospective.json')):
        record = json.loads(path.read_text())
        if not valid_prospective(record):
            continue
        committed_at = publication_lookup(path)
        if not pre_start_commit(record, committed_at):
            continue
        predictions = pd.DataFrame(record['predictions'])
        frame = predictions.merge(outcome, on=KEY, how='left', validate='one_to_one')
        if frame.empty or frame['scored_points'].isna().any():
            continue  # Wait for every archived driver's result; never score a favorable partial subset.
        confident = frame[frame['p_B1'] >= CONFIDENT]
        races.append(
            {
                'event_id': record['event_id'],
                'circuit_id': record['circuit_id'],
                'forecast_created_at': record['created_at'],
                'archive_committed_at': committed_at,
                'git_commit': record.get('git_commit'),
                'drivers': len(frame),
                'brier_B1': float(((frame['p_B1'] - frame['scored_points']) ** 2).mean()),
                'brier_M1': float(((frame['p_M1'] - frame['scored_points']) ** 2).mean()),
                'top10_hits_B1': int(top10_hits(frame, 'p_B1').iloc[0]),
                'confident_predictions': len(confident),
                'confident_scored': int(confident['scored_points'].sum()),
                'archive': path.name,
                'outcomes': frame[['driver_id', 'scored_points']].to_dict('records'),
            }
        )
    return races


def pre_start_commit(record, stamp):
    if not stamp or not valid_prospective(record):
        return False
    committed = datetime.fromisoformat(stamp)
    # Git commit dates have second precision; forecast completion records may have microseconds.
    return committed.tzinfo is not None and datetime.fromisoformat(record['created_at']).replace(
        microsecond=0
    ) <= committed < datetime.fromisoformat(record['race_start_utc'])


def valid_prospective(record):
    """A filename alone cannot establish that a forecast preceded the scheduled race start."""
    try:
        created = datetime.fromisoformat(record['created_at'])
        start = datetime.fromisoformat(record['race_start_utc'])
        qualifying = datetime.fromisoformat(record['qualifying_scheduled_start_utc'])
        return (
            record['mode'] == 'prospective'
            and created.tzinfo is not None
            and start.tzinfo is not None
            and qualifying.tzinfo is not None
            and qualifying + QUALIFYING_SETTLE <= created < start
        )
    except (KeyError, TypeError, ValueError):
        return False


def operational_health(events, entries, labels, archive_dir, season, now, first_round=None):
    """Observed collection/forecast state, not a promise that a schedule will execute."""
    first_round = first_round if first_round is not None else (17 if season == 2026 else 1)
    rows = []
    for event in (
        events[(events['season'] == season) & (events['round'] >= first_round)].sort_values('round').to_dict('records')
    ):
        event_id = event['event_id']
        q = entries[(entries['event_id'] == event_id) & entries['qualifying_available']]
        outcome = set(labels.loc[labels['event_id'] == event_id, 'driver_id'])
        path = Path(archive_dir) / f'{event_id}-prospective.json'
        warnings = []
        state = 'waiting_for_qualifying'
        archived_count = 0
        if path.exists():
            record = json.loads(path.read_text())
            drivers = {p['driver_id'] for p in record['predictions']}
            archived_count = len(drivers)
            if not valid_prospective(record):
                state = 'invalid_archive'
            elif not pre_start_commit(record, archive_commit_time(path)):
                state = 'unverified_archive_commit'
            elif drivers and drivers <= outcome:
                state = 'scored'
            else:
                state = 'partial_results' if drivers & outcome else 'forecast_saved'
                warnings = list(record.get('warnings', []))
        elif event.get('race_start_utc') and now >= datetime.fromisoformat(event['race_start_utc']):
            state = 'missed_forecast'
        elif should_forecast(event, bool(outcome), False, now):
            state = 'qualifying_unavailable' if q.empty else 'forecast_due'
        rows.append(
            {
                'event_id': event_id,
                'state': state,
                'qualifying_drivers': len(q),
                'archived_drivers': archived_count,
                'result_drivers': len(outcome),
                'warnings': warnings,
            }
        )
    return {'events': rows, 'first_round': first_round}


def write_health(directory, payload):
    """Public status changes only when meaningful state changes; full per-run status stays in workflow artifacts."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'health.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    payload = {'last_success_at': previous.get('last_success_at'), **payload}
    transient = {'checked_at', 'last_success_at', 'source_fetched_at', 'duration_seconds'}

    def stable(p):
        return {k: v for k, v in p.items() if k not in transient}

    if stable(previous) != stable(payload):
        path.write_text(json.dumps(payload, indent=2) + '\n')
    return path


def scorecard_markdown(races):
    if not races:
        return (
            '_No live forecast has been scored yet. Forecasts are saved after qualifying and committed before '
            'each race; the first is the 2026 Singapore Grand Prix._'
        )
    rows = '\n'.join(
        f'| {r["event_id"]} | {r["circuit_id"]} | {r["top10_hits_B1"]} / 10 | {r["brier_B1"]:.3f} | '
        f'{r["confident_scored"]} / {r["confident_predictions"]} | [{r["forecast_created_at"][:16]} UTC]'
        f'(predictions/{r["archive"]}) |'
        for r in races
    )
    total_conf = sum(r['confident_predictions'] for r in races)
    mean_hits = sum(r['top10_hits_B1'] for r in races) / len(races)
    summary = (
        f'**{len(races)} live race(s): {mean_hits:.1f} / 10 correct top-10 picks on average; '
        f'{sum(r["confident_scored"] for r in races)} of {total_conf} drivers given 80%+ scored.**'
    )
    return (
        f'{summary}\n\n| Race | Circuit | Top-10 picks correct | Brier | 80%+ picks that scored | Forecast saved |\n'
        f'|---|---|---:|---:|---:|---|\n{rows}'
    )


def update_readme(readme_path, markdown):
    text = Path(readme_path).read_text()
    pattern = re.compile(re.escape(README_START) + '.*?' + re.escape(README_END), re.S)
    if not pattern.search(text):
        raise ValueError('README is missing the live scorecard markers')
    updated = pattern.sub(lambda _: f'{README_START}\n{markdown}\n{README_END}', text)
    Path(readme_path).write_text(updated)
    return updated != text


def write_scorecard(races, directory, generated_at):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {'generated_at': generated_at, 'races': races}
    path = directory / 'scorecard.json'
    previous = json.loads(path.read_text())['races'] if path.exists() else None
    if previous != races:  # avoid timestamp-only commits
        path.write_text(json.dumps(payload, indent=2) + '\n')
    return path
