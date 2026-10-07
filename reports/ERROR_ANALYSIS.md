# What the model gets wrong

October 7, 2026. Post-hoc description of saved predictions for **spent** 2026 rounds 1–16. No retraining, tuning or new holdout evaluation. Calculations use four-decimal committed probabilities, so they can differ slightly from the original full-precision summary. Full counts and event-bootstrap intervals: [errors.json](diagnostics/errors.json).

## Confident predictions still fail

Of 80 predictions at or above 80%, **16 did not score**. Nine drivers given at most 20% did score. Aggregate calibration and proper scoring rules matter more than whether one favorite finishes.

The worst races were 2026-06 (Brier 0.272), 2026-05 (0.260), 2026-15 (0.226), 2026-01 (0.198) and 2026-02 (0.193). The best race was 2026-08 (0.066). These are descriptions, not evidence that circuit identity explains errors. Retirements or incidents may explain individual outcomes, but probability errors alone do not identify their causes.

## Midfield probabilities deserve attention

| Qualifying band | Rows | Races | Mean probability | Scored | Race-averaged Brier |
|---|---:|---:|---:|---:|---:|
| 1–5 | 80 | 16 | 87.2% | 80.0% | 0.161 |
| 6–10 | 80 | 16 | 65.3% | 71.2% | 0.199 |
| 11–15 | 80 | 16 | 34.5% | 36.3% | 0.223 |
| 16+ | 107 | 16 | 10.8% | 8.4% | 0.071 |

The 11–15 group has the largest descriptive error. Much of that is consistent with uncertain outcomes near the points boundary; it does not establish a correctable bias. The front-five probabilities look optimistic in aggregate, but these 80 rows are clustered in only 16 races. Do not tune a calibration correction on these spent observations.

Only one row is marked rookie by the historical feature contract (no earlier race appearance). That is insufficient for a rookie-performance conclusion. There are no missing qualifying ranks in this particular saved 2026 sample. Team, sprint and history counts are provided in the JSON; small groups remain descriptive.

## Why history features were reasonable, yet did not generalize

Fixed-setting, **development-only** ablations were run after holdout results were known to explain feature groups, not select a replacement. Every fit uses seasons before its validation year (2021–2024); 2025 and 2026 rows are excluded. All variants use standardized logistic regression, C=0.1 and raw probabilities. The standardized rank diagnostic differs from frozen B1's preprocessing and regularization.

| Diagnostic | Development race Brier |
|---|---:|
| Standardized rank | 0.1590 |
| + driver history | 0.1486 |
| + team history/identity (without driver history) | 0.1475 |
| + driver and team | 0.1466 |
| + circuit | 0.1467 |
| Full v1 (also field size/percentile) | 0.1467 |

History helped on development seasons, while circuit added little under these fixed settings. That developmental advantage did not translate into demonstrated improvement on the sealed 2025 test or 2026 backtest. Regulation changes, redundant signals and limited sample size are possible explanations, **not proven causes**. Keeping B1 is an evidence-based complexity decision.

[ablations.json](diagnostics/ablations.json) records complete event split lists, features, settings and a hash of development rows. Reproduce with local data using `uv run python -m f1_points.analysis --ablations --output /tmp/diagnostics`. This command does not update any frozen config.

## What would justify a change?

A future candidate needs a new pre-registration and genuinely untouched later races. Monitor coverage and proper scores without turning every bad race into a tuning decision. Small live samples are reported as uncertain; no automatic retraining, causal tyre claims or ten-scorer normalization is introduced.
