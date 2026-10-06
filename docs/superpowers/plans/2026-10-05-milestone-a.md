# Milestone A Implementation Plan

**Goal:** auditable historical collection without training.
**Architecture:** cached HTTP JSON → validated normalization → coverage-only reports.
**Tech stack:** Python 3.12, uv, requests, FastF1, pandas, PyArrow, pytest.

## Constraints
Local/free data access; no telemetry or modeling. 2025 outcomes remain outside development reports. Never equate qualifying rank to grid or scheduled start to actual end. Keep all source payloads ignored.

## Tasks
- [ ] Environment: create pyproject.toml, Python pin and uv.lock; verify `uv sync --locked`; commit.
- [ ] Cache contract: `SnapshotClient.get(path, offline=False)` returns payload and manifest. Write synthetic transport tests for cache reuse, integrity, offline miss and three-attempt retries; run red, implement, run green; commit.
- [ ] Normalization: `normalize_event(schedule, qualifying, results)` returns event, entries, labels. Synthetic tests assert union roster, missing Q3/session, duplicate rejection, valid rank/duration and label separation; run red, implement, run green; commit.
- [ ] Collection CLI: `collect --start 2018 --end 2025` writes ignored normalized JSON and report with per-event counts, hashes and limitations. Failures produce coverage entries. Check one weekend before bulk run; verify offline replay; commit.
- [ ] Audit: summarize coverage, timestamp and sprint-format limitations; update README/handoff and milestone checkboxes only for completed work; run complete tests, inspect staged files and push.

Verification commands: `uv run pytest -q`, `uv run python -m f1_points.cli collect --start 2018 --end 2018 --round 1`, then full study and offline replay. No final test metrics.
