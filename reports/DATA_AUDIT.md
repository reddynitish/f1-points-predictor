# Milestone A: historical data availability

Audited October 5, 2026 (America/New_York). Source retrieval times are UTC in `coverage.json`. No model has been trained or evaluated. 2025 was inspected for availability and schema only; no outcome values or model metrics are included in this report.

## Reproduction

Install uv, then run:

```sh
uv sync --locked
uv run pytest -q
uv run python -m f1_points.cli collect --start 2024 --end 2024 --round 1 --report data/one-weekend-coverage.json
uv run python -m f1_points.cli collect
uv run python -m f1_points.cli collect --offline --report data/offline-coverage.json
```

The first download is resumable. The offline command verifies every cached payload hash and requires all pages already present. Raw UTF-8 JSON snapshots and normalized event records are ignored under `data/`. Reports contain derived counts, source URLs, retrieval dates and SHA256 hashes only. To refresh sources, select a new `--cache` directory; do not overwrite the old snapshots. Separate `--output` and `--report` paths preserve previous normalized/report revisions.

## Observed coverage

| Season | Events | Union roster rows | Qualifying rows | Race label rows | Scheduled qualifying start present |
|---|---:|---:|---:|---:|---:|
| 2018 | 21 | 420 | 420 | 420 | 0 |
| 2019 | 21 | 420 | 418 | 420 | 0 |
| 2020 | 17 | 340 | 340 | 340 | 0 |
| 2021 | 22 | 440 | 439 | 440 | 0 |
| 2022 | 22 | 440 | 440 | 440 | 22 |
| 2023 | 22 | 440 | 440 | 440 | 22 |
| 2024 | 24 | 479 | 479 | 479 | 24 |
| 2025 | 24 | 480 | 479 | 479 | 24 |

173 events, 86 paginated source snapshots, zero transport/normalization failures in the final offline audit. Actual qualifying end is unavailable in all 173 normalized records; `cutoff_ready` is false throughout. These are observed source rows, not proof of a complete qualifying-end entry roster.

Qualifying rows are absent for two union-roster drivers in 2019 round 3, one in 2021 round 5, and one in 2025 round 21. One union-roster row has no race label in 2025; it remains unlabeled, never assigned zero points. The 479-row 2024 season is retained as observed, not silently padded to 480. Drivers absent from both source sessions cannot be recovered by the roster union.

Five events contain repeated upstream qualifying ranks: 2023-10, 2024-08, 2024-15, 2024-17 and 2025-07. The values are preserved and flagged; no invented order resolves these anomalies. Their cause and relationship to revisions/disqualifications are unverified. Missing segment values include absent keys and empty strings; Sakhir 2020 uses sub-minute time strings. Both formats have synthetic regression tests.

## One-weekend inspection

Bahrain 2024 round 1: 20 unique entries and 20 labels, matching driver-ID sets. Qualifying rank and Q1/Q2/Q3 durations remain in entries; points, position and race status remain in labels. Scheduled qualifying start is 2024-03-01 16:00 UTC and scheduled race start is 2024-03-02 15:00 UTC. Neither is asserted to be an observed session end/start. Absent Q3 values remain null. Offline replay reproduced the same source snapshot manifests.

## Gates and limitations

Environment, cache, pagination, normalization, weekend inspection and full availability reporting are implemented. The data gate remains open:

1. Actual qualifying end needs separately evidenced timing and provenance. Scheduled qualifying timestamps are absent for 2018–2021 and never substitute for end time.
2. The roster union and constructor fallback from results are retrospective approximations. Race-only entries cannot be approved as pre-race features until independent roster/team evidence is available.
3. Qualifying ranks are retrieved published results, not reconstructed snapshots at qualifying end. Later disqualifications/corrections may affect them. Repeated ranks require review.
4. Sprint weekends (24 across this study) need format-specific verification: identify the qualifying session relevant to the intended cutoff without treating sprint results as qualifying.
5. Constructor/circuit aliases are not applied; original upstream IDs are preserved. Result-status taxonomy and DNF feature logic remain unimplemented.
6. Race time is upstream scheduled time, not independently observed start. Label `fetched_at` is the completion time of the season's result-page retrieval batch, while individual snapshot retrieval timestamps remain in manifests. Historical revision/publication times are not reconstructed.
7. This is a retrospective adapter, not a pre-race inference interface. Normalized audit JSON contains separate entries/labels arrays; milestone B must produce physically separate feature/label files and enforce lineage/allowlists before training.

No splits, predictive features, model selection, final-test evaluation or dashboard have been implemented. Failures from the initial parser were reproduced from cache and corrected with tests; the final report is a new normalization of the same immutable source snapshots.

## Sources and usage

- [Jolpica documentation](https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md): JSON endpoints, pagination and custom user agent.
- [Qualifying schema](https://github.com/jolpica/jolpica-f1/blob/main/docs/endpoints/qualifying.md): optional rank and segment fields; qualifying is separate from grid.
- [Rate limits](https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md): cache and paginated seasonal queries; client waits between requests and honors Retry-After on failures.
- [FastF1](https://github.com/theOehrly/Fast-F1): installed and locked for a subsequent timing audit, not used to download telemetry in this milestone.

Adapter code is original; no external implementation was copied. Upstream software licenses do not establish unrestricted data redistribution rights. Only derived audit evidence is committed; bulk upstream payloads remain local. Dependencies and their transitive versions are pinned in `uv.lock`.
