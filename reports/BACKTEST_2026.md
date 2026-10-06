# 2026 backtest: points probability from qualifying

> Retrospective walk-forward backtest run after the season was played. For each race the models were refit on earlier races only and given only information available at qualifying end. These are not forecasts that were published before each race.

Generated 2026-10-06 from commit `ce2e8f7` with the frozen config (`configs/final.json`, sha256 `90bb838dfa71`). Protocol pre-registered in [PREREGISTRATION_V2.md](../docs/PREREGISTRATION_V2.md) before any comparison. Per-driver predictions: [backtest-2026/predictions.csv](backtest-2026/predictions.csv). Raw numbers: [backtest-2026/summary.json](backtest-2026/summary.json).

## Headline (16 races, 347 driver predictions, rounds 1–16)

| | B0 no information | B1 qualifying rank (primary) | M1 full v1 model |
|---|---:|---:|---:|
| Race-averaged Brier (lower is better) | 0.248 | **0.158** | 0.161 |
| Log loss | 0.690 | 0.482 | 0.496 |
| ROC-AUC | 0.506 | 0.846 | 0.844 |
| Correct points scorers among top-10 picks, mean per race | — | 7.6 / 10 | 7.6 / 10 |

- B1 cuts Brier error by about 37% relative to no information.
- M1 minus B1, 95% event-bootstrap interval: [-0.0010, +0.0094]. This includes zero, so M1 is **not** better than the qualifying baseline in 2026, consistent with the 2025 sealed test. Driver/team form features remain unproven.
- When B1 gave a driver at least 80%, the driver scored 64 of 80 times (80%).
- Best race: 2026-08 (Brier 0.066, 10/10 picks correct). Worst race: 2026-06 (Brier 0.272, 6/10).
- B1's top 10 is simply the qualifying top 10, so its top-10 hit rate equals the rule "qualifying top ten scores points". The probabilities add calibrated confidence on top of that ranking.

## Per race

| Race | Drivers | Brier B1 | Brier M1 | Top-10 hits B1 | Top-10 hits M1 |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 19 | 0.198 | 0.192 | 7 | 7 |
| 2026-02 | 22 | 0.193 | 0.227 | 7 | 6 |
| 2026-03 | 22 | 0.124 | 0.120 | 7 | 8 |
| 2026-04 | 22 | 0.116 | 0.121 | 8 | 8 |
| 2026-05 | 22 | 0.261 | 0.254 | 6 | 6 |
| 2026-06 | 22 | 0.272 | 0.295 | 6 | 6 |
| 2026-07 | 22 | 0.149 | 0.143 | 7 | 8 |
| 2026-08 | 22 | 0.066 | 0.067 | 10 | 9 |
| 2026-09 | 22 | 0.187 | 0.193 | 7 | 7 |
| 2026-10 | 22 | 0.112 | 0.117 | 9 | 8 |
| 2026-11 | 22 | 0.097 | 0.101 | 9 | 9 |
| 2026-12 | 22 | 0.149 | 0.149 | 7 | 8 |
| 2026-13 | 22 | 0.129 | 0.118 | 9 | 9 |
| 2026-14 | 20 | 0.110 | 0.112 | 9 | 9 |
| 2026-15 | 22 | 0.226 | 0.241 | 6 | 6 |
| 2026-16 | 22 | 0.132 | 0.131 | 7 | 8 |

## Calibration (B1): do the percentages mean what they say?

| Predicted bin | Drivers | Mean predicted | Actually scored |
|---|---:|---:|---:|
| (-0.001, 0.1] | 59 | 0.07 | 0.03 |
| (0.1, 0.2] | 48 | 0.15 | 0.15 |
| (0.2, 0.3] | 32 | 0.26 | 0.31 |
| (0.3, 0.4] | 16 | 0.34 | 0.25 |
| (0.4, 0.5] | 32 | 0.43 | 0.47 |
| (0.5, 0.6] | 32 | 0.56 | 0.62 |
| (0.6, 0.7] | 16 | 0.66 | 0.62 |
| (0.7, 0.8] | 32 | 0.74 | 0.84 |
| (0.8, 0.9] | 48 | 0.84 | 0.73 |
| (0.9, 1.0] | 32 | 0.91 | 0.91 |

The bins have only 16–59 drivers each, so differences of about 10 points are within noise.

## Limits

- Sixteen races; the intervals are wide.
- 2026 is the first season of new regulations and has two new team identities. Training history from 2018–2025 carries over across that break.
- The model sees qualifying rank, not the final grid; penalties are applied later.
- This replay was produced in October 2026. Live forecasts begin with round 17 (Singapore), archived in `predictions/` before the race.
