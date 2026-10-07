# Sprint endpoint audit

Collected October 7, 2026. This is a source-semantics audit, not a new model evaluation. No frozen configuration or prediction was changed.

The read-only audit fetches qualifying and sprint endpoints for each season 2021–2025, joins drivers by ID, and compares qualifying positions with the sprint result's starting-grid column. Immutable snapshots remain ignored under `data/sprint-audit/`; source URLs, retrieval times and SHA-256 hashes are in [sprint-audit.json](sprint-audit.json).

| Season | Sprint events checked | Events with different orders | Interpretation |
|---|---:|---:|---|
| 2021 | 3 | 1 | Qualifying sets the sprint grid; penalties can change it |
| 2022 | 3 | 1 | Qualifying sets the sprint grid; penalties can change it |
| 2023 | 6 | 6 | Separate race qualifying and sprint shootout |
| 2024 | 6 | 6 | Separate race qualifying and sprint qualifying |
| 2025 | 6 | 6 | Separate race qualifying and sprint qualifying |

All 24 comparisons have shared drivers. On every checked 2023–2025 sprint weekend the orders differ. For example, 2024-05 lists Verstappen on race-qualifying pole and Norris on sprint-grid pole; 2024-21 lists Norris and Piastri respectively. This supports the endpoint separation on the checked events. It does **not** prove that all historical classifications exactly match what was published at the qualifying flag.

Sprint starting grid is only a proxy for sprint qualifying: penalties, disqualifications and non-starters may change it. The 2021-19 Hamilton/Verstappen discrepancy illustrates that limitation. Current-weekend sprint results remain forbidden as model features.

Reproduce without network after the initial fetch:

```sh
uv run python -m f1_points.audit --offline --output /tmp/sprint-audit.json
```

The cutoff policy remains an interval, the roster remains qualifying-row-only, and later qualifying revisions remain a disclosed approximation. No exact historical publication-time reconstruction is claimed.
