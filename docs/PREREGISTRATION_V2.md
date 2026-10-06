# Pre-registration: 2026 backtest and v2 features

**Committed:** October 6, 2026, before any 2026 race outcome has been compared with a model prediction.

## 1. 2026 backtest of the frozen v1 model

- **Scope:** 2026 rounds 1–16 (every completed race).
- **Protocol:** walk-forward. Before each race, refit on every earlier race (2018 through the previous 2026 round) using the settings frozen in `configs/final.json`. Inputs are only what's known at qualifying end; the race being predicted contributes nothing.
- **Models:** B1 (qualifying rank only, primary per the 2025 result) and M1 (frozen logistic). B0 (constant base rate) is the floor.
- **Reported:** race-averaged Brier, log loss, ROC-AUC, the per-race count of correct points-scorers among each model's top 10, the M1 − B1 event-bootstrap interval, and reliability by probability bin.
- **Framing:** this is a retrospective backtest run in October 2026. It is not a set of forecasts published before each race and must never be presented as one.

## 2. v2 features (specified before the 2026 backtest is examined)

Qualifying-end cutoff:
- `qualifying_gap_pct`: the driver's best qualifying lap (any segment) relative to the session's fastest lap, in percent.
- `practice_gap_pct`: best lap across practice sessions held before qualifying, relative to the fastest such lap, in percent.
- `practice_sessions`: number of those sessions in which the driver set a lap.
- `qualifying_rain`, `qualifying_track_temp`: weather observed during qualifying.

Pre-race cutoff (a separate model, used only once the official starting grid is known):
- all qualifying-end features, plus `grid_position` (pit-lane starts placed at the back), `grid_pitlane` and `grid_change` (grid minus qualifying rank).
- Baseline for this cutoff: grid-position-only logistic regression.

Not included: race-day weather. A free, leakage-safe archive of genuine pre-race forecasts doesn't exist for 2018–2023.

## 3. v2 selection and test

- **Development:** expanding seasonal blocks validating 2021–2025. The 2025 test is spent and becomes development data.
- **Candidates:** the same B1/M1/M2 grid. Same selection rule (lowest race-averaged Brier, simplest within 0.0005), same calibration comparison.
- **Freeze:** the configuration is committed before scoring 2026.
- **Test:** 2026 rounds 1–16, walk-forward, reported against B1 (qualifying cutoff) or the grid-only baseline (pre-race cutoff), including inconclusive or negative results.
- **Caveat:** the v1 backtest numbers for the same races will already be known when v2 is scored. The v2 feature list and selection procedure are fixed here to limit that influence. Sixteen races give wide intervals.

## Amendment 1 (October 6, 2026, before any v2 model was fit or scored)

Made from data-quality checks on the downloaded session data, without looking at any v2 prediction or 2026 v2 outcome:

- **Qualifying rain:** a yes/no flag set by *any* rain reading. Replaced by `qualifying_rain` = the share of weather readings showing rain (0–1). The weather stream also covers minutes around the session, and single drizzle readings made the flag fire for 10 of 21 qualifying sessions in 2018. With the share, at most a handful of sessions per season have at least 25% wet readings.
- **2022 session data:** the live-timing archive refuses every 2022 request, including its season index (HTTP 403, checked on October 6, 2026; other seasons answer normally). 2022 practice and weather features are therefore missing. They're imputed with fold-local medians plus missing-value indicators, like any other missing feature. 2022 stays a development validation season, and its rows are noted as feature-incomplete in the report.
- **Cache fix:** a missing page is only cached as permanently absent once its session is more than two days in the past. Otherwise upcoming 2026 sessions would have stayed "missing" forever.
