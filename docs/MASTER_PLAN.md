# F1 Points Predictor — Master Implementation Plan

**Date:** October 5, 2026. **Status:** proposed implementation plan; no experiments performed.

**Goal:** predict the probability that each entered driver scores strictly positive race points, using information available after qualifying and before the race.

**Architecture:** immutable cached source snapshots feed normalized event/driver tables. A cutoff-aware feature builder joins prior-event history with qualifying information. Race-grouped chronological evaluation compares frozen models; a read-only dashboard displays saved predictions, outcomes, and failure analysis.

**Stack:** Python 3.11+, pandas, NumPy, FastF1, scikit-learn, PyArrow, joblib, pytest; Streamlit/Plotly for the final display. Resolve mutually compatible versions during environment setup and commit a lockfile. Optional XGBoost only after the first benchmark.

## 1. Scope and boundaries

- Local CPU-first development; no paid APIs, cloud training, LLM calls or subscriptions required by the pipeline. Existing coding assistants may help development but are not the predictive model.
- One driver-event row; race results as labels, not individual laps as independent training examples.
- First prediction cutoff: official qualifying session end. Current-event sprint outcomes, practice telemetry, weather forecasts, grid penalties and final Sunday starting grid are excluded from v1 because historical availability timestamps need separate verification.
- Current qualifying rank is not necessarily the final starting grid. Label it honestly throughout the UI.
- Predict `scored_points = race_points > 0`, not exactly ten finishing places. Historical fastest-lap points, shortened-race scoring and disqualifications can change the number of positive labels. Sprint points excluded.
- Labels use final published race points as retrieved. Record retrieval time and revisions; earlier form uses prior finalized results as a historical approximation. State that exact historical publication/revision timing is not reconstructed.
- DNF, DNS, DSQ and classified non-finishers remain included if entered and qualifying data is available, using actual awarded race points. Don't remove difficult outcomes to improve scores. Drivers absent from qualifying need an explicit missing-rank row and missingness flag; report coverage.
- Full race ranking, pit strategy, betting, real-time telemetry and neural networks are later research, not MVP features.

## 2. Data collection and audit

Initial study: 2018–2025 completed seasons, subject to actual coverage. Do not invent missing telemetry or qualifying. Before training, generate a per-event availability report. If a year cannot be supported, record exclusions and revise split dates before looking at holdout outcomes. 2026 completed races become prospective/shadow evaluation, not a source for tuning the 2025 holdout.

Sources: FastF1 results/qualifying and its supported historical-results source. Choose one adapter interface so upstream migration does not change feature definitions. Identify races by `(season, round)` and drivers by stable upstream driver ID. Circuit ID and constructor ID have explicit aliases for renamed entities; retain original values.

Save fetched payloads/snapshots with source URL or session identifier, retrieval UTC, library version, schema version, SHA256 and event/session timestamps. Cache retries: three attempts with exponential backoff, honour rate limits, fail with a coverage entry rather than fabricate data. Race cache is resumable. Do not commit upstream bulk data, caches, credentials or large model files.

Normalized tables:

| Table | Required fields |
|---|---|
| events | season, round, event_id, circuit_id, qualifying_end_utc, race_start_utc, sprint_weekend |
| entries | event_id, driver_id, constructor_id, qualifying_rank, q1/q2/q3_seconds, qualifying_available |
| race_labels | event_id, driver_id, race_points, final_position, result_status, fetched_at |
| manifests | source, event_id, fetched_at, sha256, schema_version, exclusions |

All timestamps UTC; unique key `(event_id, driver_id)` validated. Missing qualifying times are not zero. Disqualified session times and unusual qualifying formats need explicit adapter logic and provenance. Reject duplicate keys, negative durations and impossible ranks; preserve legitimate ties/format variations in audit notes.

## 3. Features and leakage contract

All historical features select events with `race_start_utc < qualifying_end_utc` of the target. Current target race labels are never accessible to feature construction. Group drivers by event before joining team aggregates.

| Feature | Construction |
|---|---|
| qualifying_rank | target qualifying result; missing flag if absent |
| field_size | number of entered drivers in event snapshot |
| qualifying_percentile | rank normalized to field size |
| driver_points_rate_last5 | positive race-label mean from last five prior appearances |
| driver_finish_mean_last5 | prior classified position mean; preserve missing status separately |
| driver_dnf_rate_last5 | prior clearly documented non-finish status rate |
| driver_history_count | number of prior observations; capped count available to model |
| constructor_points_rate_last5_events | positive-label rate across teammates in last five complete prior events |
| circuit_id / constructor_id | categorical IDs; unseen categories allowed |
| rookie / missing-history flags | distinguish unknown history from poor performance |

No driver name one-hot in first experiment; evaluate whether identity improves future-race generalization later. Do not use last-five *rows* for constructor form: five events, all teammates. Rookie history missing; impute using training-fold medians and flags, not full-dataset averages.

V2 candidate: normalized qualifying time gap measured within a comparable qualifying segment. Q1/Q2/Q3 times are not blindly comparable across conditions. Add only after missing/format audits and an ablation.

Forbidden inputs: current race points, finishing position/status, race-sector averages, race laps completed, actual race tyre strategy, actual weather, post-race pit stops and engineered proxies derived from those. Enforce an explicit allowlist, never automatically train on every numerical column.

Tests include: changing target-race outcomes changes labels but not features; changing a future event changes no earlier features; teammate rows share the same prior-event team aggregate; shuffled input order gives identical features; all source-event dates precede cutoff.

## 4. Training and temporal splits

Freeze split manifest before model selection:

1. Development training begins 2018–2020.
2. Expanding validation blocks: fit through 2020, score 2021; fit through 2021, score 2022; fit through 2022, score 2023; fit through 2023, score 2024.
3. Tune hyperparameters using development blocks only. Each race belongs wholly to a block; no driver-row random splitting.
4. Keep 2025 sealed as final test. Freeze selected feature list, model family, hyperparameters, threshold and calibration protocol before scoring it.

Two explicit evaluation modes: fixed-season model fit through 2024 scores all 2025 races; walk-forward replay refits before each 2025 race using only earlier races with previously frozen settings. Earlier 2025 outcomes may update later predictions under the replay protocol, but never change settings. Report modes separately.

Pipeline: numeric median imputer + missing indicators; standardization for logistic regression; categorical imputation + one-hot with unknown handling. Every transformer fitted within each training fold. Prevent feature-selection or calibration access to test data.

Models:
- B0: training positive prevalence constant probability.
- B1: qualifying-rank-only logistic regression; fair probabilistic baseline.
- Diagnostic rule: qualifying top ten predicts points; binary reporting only, not a substitute for probability baseline.
- M1: regularized logistic regression on full v1 features, C in `[0.1, 1, 10]`.
- M2: HistGradientBoostingClassifier, learning rate `[0.05, 0.1]`, max leaf nodes `[7, 15]`, L2 `[0, 1]`, fixed max iterations 200 and no random internal validation. Dense encoded data is acceptable at this scale.

Seed 42, record CPU, RAM, dependency versions, duration and peak memory. Keep tuning budget small; no neural model just to increase algorithm count. Select on race-averaged validation Brier score; log loss as secondary, runtime/complexity breaks near ties.

## 5. Probability calibration and uncertainty

Compare raw probabilities with sigmoid calibration fitted to chronological out-of-fold development predictions. For each validation block, calibration uses only earlier out-of-fold predictions; initial fold is raw when no prior calibration data exists. Never use shuffled default cross-validation calibration. Freeze calibration selection before final test; final calibrator uses development-only out-of-fold predictions.

Reliability diagrams with bin counts, Brier score and log loss. Clip only for numerical log-loss stability, record epsilon. Select binary threshold on development predictions, or use 0.5 default; never optimize test threshold.

Independent per-driver probabilities need not sum to exactly ten: the target can have more or fewer positive labels. Do not renormalize without validating a separate joint model. Bootstrap whole race events with fixed seed to estimate metric intervals; acknowledge limited event count and cross-season dependence. Probability is not certainty or a causal strategy recommendation.

## 6. Evaluation and success criteria

Primary: race-averaged Brier score. Secondary: driver-weighted Brier, log loss, PR-AUC, ROC-AUC, precision/recall/F1 at the frozen threshold, reliability plots and coverage. Event-level AUC undefined for single-class events: omit from that metric with counts, retain Brier/log loss with explicit class labels. Compare models on identical covered rows.

Break down errors by circuit, season, qualifying band, history availability, driver/team, sprint weekend, DNF/DSQ and missing qualifying. Small groups are descriptive, not decisive. Report worst races and confident failures. Ablations: rank only; +driver history; +team history; +circuit. Permutation importance on development validation, interpreted as predictive association, not causation.

Success is reproducible, leakage-tested forecasting and an honest baseline comparison. A publishable improvement claim needs lower holdout Brier than B1 and race-level uncertainty reported; if improvement is inconclusive, keep the baseline and document that finding. No target score invented in advance, no headline 'accuracy' without target/split/baseline context.

## 7. Planned repository layout and interfaces

`src/f1_points/data.py`: fetch/cache adapters. `schema.py`: normalized table validation. `features.py`: cutoff-aware construction. `splits.py`: event-grouped split manifests. `baselines.py`: B0/B1. `train.py`: fold-local pipelines and search. `calibration.py`: chronological calibration. `evaluate.py`: metrics, race bootstrap and breakdowns. `predict.py`: frozen artifact scoring. `cli.py`: commands. `app.py`: saved-artifact dashboard. `tests/`: small synthetic fixtures and leakage tests. `configs/study.yaml`: years/features/search/seed. `reports/`: methodology and model card. Raw data and model binaries stay ignored locally.

Contract: `build_features(entries, events, historical_labels)` returns one keyed feature row per entry plus lineage; `make_splits(events)` returns ordered event-ID sets; `fit_model(train_rows, config)` returns serialized preprocessing/model and metadata; `predict_event(artifact, rows)` returns driver_id, p_points, cutoff_utc, model_version, missingness warnings. Labels passed separately during fitting/scoring; inference cannot request target-race results.

Prediction artifact metadata: git commit, config hash, data-manifest hashes, max training event/date, feature list, calibration version, dependency versions. Save per-driver predictions before outcome evaluation; do not silently replace predictions after a result arrives.

## 8. Implementation milestones and acceptance gates

### A. Data adapter and coverage
- [x] Create project environment/lockfile and adapters in `data.py`, fixtures in `tests/test_data.py`.
- [x] Test duplicate IDs, absent Q3, absent qualifying, retries and cache reuse on synthetic inputs; then implement adapter.
- [x] Fetch one historical weekend; inspect normalized entries/results manually before bulk collection.
- [x] Generate 2018–2025 coverage manifest, exclusions and hashes; commit code/report, not caches.
Gate status: keys and offline replay verified; sprint formats classified and repeated ranks traced; timestamp/roster/revision decisions proposed in [DATA_GATE_PROPOSAL.md](DATA_GATE_PROPOSAL.md). See [DATA_AUDIT.md](../reports/DATA_AUDIT.md). Historical audit records preserve the original gate state. Modelling subsequently used the disclosed interval-cutoff policy; see reports/MODEL_CARD.md and docs/DATA_GATE_PROPOSAL.md.

### B. Cutoff-safe dataset
- [x] Implement feature specification and tests in `tests/test_leakage.py`, then feature builder.
- [x] Use a three-race/two-teammate fixture to assert prior-event-only aggregates.
- [x] Separate feature and label files; generate lineage and missingness audit.
Gate: mutation/shuffle/rookie tests pass and forbidden-column allowlist enforced.

### C. Baselines and split manifest
- [x] Implement event splits with `tests/test_splits.py`; assert train/validation event sets disjoint and ordered.
- [x] Implement constant and rank-only classifiers in `baselines.py`.
- [x] Save development fold predictions and baseline report without opening final test metrics.
Gate: all drivers of each race remain together and metrics match small hand-calculated fixtures.

### D. Model comparison and calibration
- [x] Implement M1/M2 searches, training-fold transformations and bounded configuration in `train.py`.
- [ ] Compare ablations and earlier-fold-only calibration (calibration done; ablations not run); retain all experiment records.
- [x] Freeze `configs/final.json` (JSON instead of YAML) with feature list, parameters, threshold and protocol, commit before test run.
Gate: every calibration source predates its validation block; train metadata proves no 2025 rows used for fixed-season model.

### E. Final evaluation
- [x] Run sealed 2025 evaluation once with frozen choices; save predictions/metrics and race bootstrap intervals.
- [x] Run separately identified walk-forward replay with frozen settings.
- [x] Write `reports/MODEL_CARD.md` with data coverage, target, cutoff, baselines, uncertainty, revisions and failures.
Gate: report all results even if stronger model loses; any later test-informed changes create a new experiment requiring a new untouched test period.

### F. Product and prospective predictions
- [ ] Build dashboard reading saved artifacts: select event, see qualifying rank/probability/actual result, baseline comparisons and missingness.
- [x] Add frozen-model CLI inference with refusal when inputs are unavailable; missing history supported with warnings.
- [ ] Archive prospective predictions for a future supported race before start, then evaluate after published results.
Gate: prediction page displays timestamp/model version and never downloads future labels during inference. UI makes retrospective replay distinct from genuine forecast.

Planned commands after implementation: `python -m f1_points.cli collect`, `build-dataset`, `backtest`, `train`, `evaluate`, `predict --season YEAR --round ROUND`; `pytest`; `streamlit run app.py`. These are implemented CLI commands except `train` (use `select`) and the originally proposed Streamlit app (replaced by a static artifact dashboard). Each milestone ends with tested code, a report and a focused commit.

## 9. Risks and practical decisions

Small event count, changing regulations, rookie history and team changes limit generalization. 2026 regulation changes are a distribution-shift case; report 2026 separately. Weather excluded unless historical forecasts with issue timestamps become available. Upstream data corrections require manifests and rerun disclosure. Review upstream usage terms before redistributing any dataset. The first dashboard can be entirely local; deployment is optional and has no free-tier assumption.

Estimate 2–3 focused weeks for MVP, dependent on data audit and available learning time, not a delivery guarantee. Sequence data/validation first, dashboard last. See [RELATED_WORK.md](RELATED_WORK.md) for attributed design lessons. No existing predictor's metrics or authorship are presented as our results.
