# Model card: F1 points probability at qualifying end

**Date:** October 6, 2026. **Config:** [configs/final.json](../configs/final.json), frozen and committed before the 2025 test was opened.

## Task

For each driver with a qualifying classification, estimate P(race points > 0) using information available at qualifying end. Sprint points are excluded. The labels are final published race points as retrieved; the exact historical revision timing of results isn't reconstructed. Qualifying rank is **not** the Sunday starting grid. Per-driver probabilities are independent and don't have to sum to ten.

## Data

Jolpica (Ergast-compatible) results and qualifying data for 2018–2025, with 2026 rounds 1–16 used only as history for live forecasts. That's 3802 qualifying rows across 189 events; one qualifying row has no race label and is dropped, never set to zero. See [DATA_AUDIT.md](DATA_AUDIT.md), [dataset.json](dataset.json) and [coverage-2026.json](coverage-2026.json).

Provisional data-gate decisions, the recommended options in [DATA_GATE_PROPOSAL.md](../docs/DATA_GATE_PROPOSAL.md), adopted October 6, 2026:
- **Cutoff:** the window from scheduled qualifying start to race start. All history comes from earlier events, and a guard rejects any history that doesn't precede the cutoff.
- **Roster:** drivers with a qualifying row. Four race-only rows are excluded from 2018–2025 and five from 2026.
- **Revisions:** five qualifying disqualifications are set to rank-missing through the sourced [overrides/qualifying.csv](../overrides/qualifying.csv). Bearman 2025-07, a deleted lap rather than a disqualification, keeps the upstream rank.
- **Sprint:** current-weekend sprint results are never used. The qualifying endpoint hasn't been independently checked against sprint-qualifying results.

## Features

Qualifying rank and percentile, missing-rank flag, field size. Driver form over the last 5 prior appearances: points rate, mean finishing position, non-finish rate, plus a history count. Team points rate over the last 5 prior events, pooling all teammates, following an explicit rename lineage (e.g. sauber → alfa → audi). Rookie and new-team flags, and circuit and constructor IDs. Leakage tests are in [tests/test_leakage.py](../tests/test_leakage.py).

## Selection (development only, 2021–2024 expanding blocks, 90 races)

| Model | Race-averaged Brier |
|---|---:|
| M1 logistic, C=0.1 (selected) | 0.1467 |
| Best M2 gradient boosting | 0.1508 |
| B1 qualifying rank only | 0.1589 |
| B0 constant prevalence | 0.2500 |

C=0.1 is the edge of the pre-set grid, and the grid wasn't extended after seeing results. Chronological sigmoid calibration improved Brier by 0.0004, which is within the tie tolerance, so probabilities are raw. Full results: [development.json](experiments/development.json).

## Sealed 2025 test (run once)

| Protocol | Selected (M1) | B1 | B0 | M1 − B1, 95% event bootstrap |
|---|---:|---:|---:|---|
| Fixed season (fit 2018–2024) | 0.1654 | 0.1657 | 0.2500 | [−0.0081, +0.0076] |
| Walk-forward (refit before each race) | 0.1651 | 0.1657 | — | [−0.0087, +0.0073] |

24 races, 478 rows. **No improvement over the qualifying-rank baseline is demonstrated.** Driver history, team history and circuit features didn't add measurable out-of-sample value beyond qualifying position. Following the rule written before the test, **B1 is the primary live forecast** and M1 is reported alongside it. The worst 2025 races by Brier were 2025-15, 2025-22, 2025-02, 2025-12 and 2025-11. Full results: [test_2025.json](experiments/test_2025.json).

## Live use

`python -m f1_points.cli predict --season 2026 --round N` refuses until qualifying is published, fits on every earlier race using the frozen settings, and archives the output under [predictions/](../predictions/). Archives labelled `retrospective_replay` are not forecasts.

## Limitations

- 2026 brought a major regulation change and two new team identities (Audi via lineage, Cadillac with no history). Team and driver history carry over across that break, and 2026 performance is reported separately, never pooled with 2025.
- 189 events and strong cross-season dependence make the intervals wide; small subgroups are descriptive only.
- Qualifying rank comes from the retrieved final classification, so later penalties are reflected only through the override file.
- Grid penalties, weather, practice pace and sprint results are excluded by design.
- There are no betting, strategy or causal claims.
