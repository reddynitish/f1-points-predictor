# Milestone A: historical data availability

Audited October 5, 2026 (America/New_York); sprint and repeated-rank sections added October 6, 2026. Source retrieval times are UTC in `coverage.json`. No model has been trained or evaluated. 2025 was inspected for availability and schema only; no outcome values or model metrics are included in this report.

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

Five events contain repeated upstream qualifying ranks: 2023-10, 2024-08, 2024-15, 2024-17 and 2025-07. The values are preserved and flagged per entry (`qualifying_rank_repeated`); `coverage.json` lists the affected drivers and unused ranks. See [repeated ranks](#repeated-qualifying-ranks) for the observed pattern. Missing segment values include absent keys and empty strings; Sakhir 2020 uses sub-minute time strings. Both formats have synthetic regression tests.

## Repeated qualifying ranks

Audited October 6, 2026. Every repeated rank coincides with a publicly reported classification change for one driver in the pair, and every event has a matching number of unused ranks at the back of the field:

| Event | Drivers sharing a rank | Unused ranks | Publicly reported change |
|---|---|---|---|
| 2023-10 | bottas, perez (15) | 20 | Bottas disqualified from qualifying; fuel sample could not be extracted |
| 2024-08 | hulkenberg, alonso (14); kevin_magnussen, sargeant (15) | 19, 20 | Both Haas cars disqualified from qualifying; DRS opening exceeded limit |
| 2024-15 | albon, sainz (10) | 19 | Albon disqualified from qualifying; floor outside regulatory volume |
| 2024-17 | gasly, ricciardo (15) | 20 | Gasly disqualified from qualifying; fuel-flow limit exceeded in Q2 |
| 2025-07 | bearman, lawson (16) | 19 | Bearman's final Q1 lap deleted after red flag |

Observed pattern: the affected driver keeps a rank that another driver also holds, rather than moving to the unused rank. Albon and Gasly also lack a Q1 duration despite later segment times. Bearman's case is a lap deletion, not a disqualification. The source therefore mixes performance-ordered and post-decision positions, and neither is guaranteed to equal what was known at qualifying end. This report verifies only the coincidence with public reports; it does not establish the upstream mechanism. Resolution (keep upstream rank, use the post-decision classification, or mark disqualified ranks missing) is an open design decision; no order is invented.

## Sprint weekend semantics

`weekend_format` is derived from upstream schedule session keys, never from session results:

| Format | Seasons | Events | Qualifying sets | Sprint scheduled before qualifying |
|---|---|---:|---|---|
| `sprint_grid_from_qualifying` | 2021–2022 | 6 | sprint grid; sprint result sets race grid | no (2022); unknown (2021, no session times) |
| `sprint_shootout` | 2023 | 6 | race grid | no |
| `sprint_qualifying` | 2024–2025 | 12 | race grid | yes |

Consequences for the cutoff: in all 12 2024–2025 sprint weekends a current-weekend sprint result is scheduled to exist before qualifying ends, so the feature builder must exclude it explicitly (v1 excludes current-event sprint outcomes). In 2021–2022, qualifying rank is further from the Sunday grid than usual because the sprint set the race grid. The qualifying endpoint was not independently checked against sprint-qualifying/shootout results; that check needs a sprint-session source and is part of the open data gate.

Scheduled times are not observed times. In 2024-21 (São Paulo), upstream lists qualifying at 2024-11-02 18:00 UTC and the race at 2024-11-03 17:00 UTC. Qualifying was actually postponed by rain to Sunday 10:30 GMT and the race was brought forward to 15:30 GMT. Using the scheduled qualifying start as a cutoff proxy would have placed the cutoff about 16.5 hours before the session ran.

## One-weekend inspection

Bahrain 2024 round 1: 20 unique entries and 20 labels, matching driver-ID sets. Qualifying rank and Q1/Q2/Q3 durations remain in entries; points, position and race status remain in labels. Scheduled qualifying start is 2024-03-01 16:00 UTC and scheduled race start is 2024-03-02 15:00 UTC. Neither is asserted to be an observed session end/start. Absent Q3 values remain null. Offline replay reproduced the same source snapshot manifests.

## Gates and limitations

Environment, cache, pagination, normalization, weekend inspection and full availability reporting are implemented. The data gate remains open:

1. Actual qualifying end needs separately evidenced timing and provenance. Scheduled qualifying timestamps are absent for 2018–2021 and never substitute for end time.
2. The roster union and constructor fallback from results are retrospective approximations. Race-only entries cannot be approved as pre-race features until independent roster/team evidence is available.
3. Qualifying ranks are retrieved published results, not reconstructed snapshots at qualifying end. Later disqualifications/corrections may affect them. Repeated ranks require review.
4. Sprint weekends (24 across this study) are classified by format and scheduled order. Still open: independent confirmation that the qualifying endpoint never returns sprint-qualifying/shootout results, and observed (not scheduled) session order.
5. Constructor/circuit aliases are not applied; original upstream IDs are preserved. Result-status taxonomy and DNF feature logic remain unimplemented.
6. Race time is upstream scheduled time, not independently observed start. Label `fetched_at` is the completion time of the season's result-page retrieval batch, while individual snapshot retrieval timestamps remain in manifests. Historical revision/publication times are not reconstructed.
7. This is a retrospective adapter, not a pre-race inference interface. Normalized audit JSON contains separate entries/labels arrays; milestone B must produce physically separate feature/label files and enforce lineage/allowlists before training.

No splits, predictive features, model selection, final-test evaluation or dashboard have been implemented. Failures from the initial parser were reproduced from cache and corrected with tests; the final report is a new normalization of the same immutable source snapshots.

## Sources and usage

Repeated-rank and schedule-change checks (retrieved October 6, 2026):
[F1: Bottas DSQ grid](https://www.formula1.com/en/latest/article/official-grid-who-starts-where-for-sundays-british-grand-prix-after-bottas.1tbZuiA3V7SEYpaJGRH8nU),
[F1: Haas Monaco DSQ](https://www.formula1.com/en/latest/article/haas-drivers-magnussen-and-hulkenberg-disqualified-from-monaco.2CkXFmcYpX6SOqZmkWeUCR),
[The Race: Albon DSQ](https://www.the-race.com/formula-1/alex-albon-williams-dutch-gp-qualifying-investigation/),
[F1: Gasly DSQ](https://www.formula1.com/en/latest/article/breaking-gasly-disqualified-from-qualifying-at-azerbaijan-grand-prix-over.6ks7FOpUxuLLpmKwmX1xwh),
[PlanetF1: Imola 2025 qualifying](https://www.planetf1.com/news/f1-results-2025-emilia-romagna-grand-prix-imola-qualifying-timesheet),
[GrandPrix247: São Paulo qualifying postponed](https://www.grandprix247.com/2024/11/02/sao-paulo-grand-prix-qualifying-postponed-to-race-day/).


- [Jolpica documentation](https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md): JSON endpoints, pagination and custom user agent.
- [Qualifying schema](https://github.com/jolpica/jolpica-f1/blob/main/docs/endpoints/qualifying.md): optional rank and segment fields; qualifying is separate from grid.
- [Rate limits](https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md): cache and paginated seasonal queries; client waits between requests and honors Retry-After on failures.
- [FastF1](https://github.com/theOehrly/Fast-F1): installed and locked for a subsequent timing audit, not used to download telemetry in this milestone.

Adapter code is original; no external implementation was copied. Upstream software licenses do not establish unrestricted data redistribution rights. Only derived audit evidence is committed; bulk upstream payloads remain local. Dependencies and their transitive versions are pinned in `uv.lock`.
