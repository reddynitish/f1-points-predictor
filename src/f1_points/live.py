"""Unattended race-weekend loop: forecast after qualifying, score after the race, keep a public scorecard."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .backtest import top10_hits
from .features import KEY
from .predict import QualifyingUnavailable, archive, predict_event

# Wait this long after the scheduled qualifying start so a sprint-qualifying result can never be mistaken for it.
QUALIFYING_SETTLE = timedelta(hours=1)
CONFIDENT = 0.8
README_START, README_END = '<!-- live-scorecard:start -->', '<!-- live-scorecard:end -->'


def should_forecast(event, has_labels, has_archive, now):
    """Forecast only once qualifying has surely finished, before the race starts, and only once per event."""
    if has_labels or has_archive or not event.get('race_start_utc'):
        return False
    race_start = datetime.fromisoformat(event['race_start_utc'])
    qualifying = event.get('qualifying_scheduled_start_utc')
    settled = qualifying is not None and now >= datetime.fromisoformat(qualifying) + QUALIFYING_SETTLE
    return settled and now < race_start


def forecast_due(events, entries, labels, config, archive_dir, config_path, season, now, overrides=None):
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
        if metadata['mode'] == 'prospective':
            written.append(archive(predictions, metadata, config_path, archive_dir))
    return written


def score_archives(archive_dir, labels):
    """Grade every prospective forecast whose race result is published. Recomputed from scratch each run."""
    outcome = labels.assign(scored_points=(labels['race_points'] > 0).astype(int))[[*KEY, 'scored_points']]
    races = []
    for path in sorted(Path(archive_dir).glob('*-prospective.json')):
        record = json.loads(path.read_text())
        frame = pd.DataFrame(record['predictions']).merge(outcome, on=KEY, how='inner')
        if frame.empty:
            continue  # race not run or results not published yet
        confident = frame[frame['p_B1'] >= CONFIDENT]
        races.append(
            {
                'event_id': record['event_id'],
                'circuit_id': record['circuit_id'],
                'forecast_created_at': record['created_at'],
                'git_commit': record.get('git_commit'),
                'drivers': len(frame),
                'brier_B1': float(((frame['p_B1'] - frame['scored_points']) ** 2).mean()),
                'brier_M1': float(((frame['p_M1'] - frame['scored_points']) ** 2).mean()),
                'top10_hits_B1': int(top10_hits(frame, 'p_B1').iloc[0]),
                'confident_predictions': len(confident),
                'confident_scored': int(confident['scored_points'].sum()),
                'archive': path.name,
            }
        )
    return races


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
