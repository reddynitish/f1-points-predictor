# F1 Points Predictor

An independent Formula 1 machine-learning project: estimate each driver's probability of finishing in the points after qualifying.

**Status: data audit, cutoff-safe dataset, baselines, model selection and one sealed 2025 evaluation done. The full model did not beat the qualifying-rank baseline on 2025, so the baseline is the primary forecast. Live per-race forecasts are available from the CLI; there is no dashboard yet.** See the [model card](reports/MODEL_CARD.md).

Read the [detailed master plan](docs/MASTER_PLAN.md) and [research audit](docs/RELATED_WORK.md).

Planned workflow: cached historical results → information available after qualifying → chronological backtesting → calibrated probabilities → dashboard showing predictions and errors.

Local CPU-first training with Python, pandas, FastF1 and scikit-learn. No paid AI APIs are part of the planned runtime. Data access remains subject to upstream availability and terms.

Not affiliated with Formula 1, the FIA, teams, or drivers. Educational forecasting; no guaranteed outcomes.

## Forecast the next race

After qualifying results are published:

```sh
uv run python -m f1_points.cli predict --season 2026 --round 17
```

The command refuses to run before qualifying exists and archives every forecast under `predictions/`.

## Local data audit

```sh
make install
make check        # ruff format/lint, mypy, pytest; same gate as CI
uv run python -m f1_points.cli collect
uv run python -m f1_points.cli collect --offline --report data/offline-coverage.json
```

Python 3.12 is pinned. Downloads and normalized records stay under ignored `data/`; cached downloads support offline replay. Open data-gate decisions are in [the proposal](docs/DATA_GATE_PROPOSAL.md). Read [the data audit](reports/DATA_AUDIT.md) and [per-event coverage](reports/coverage.json) for observed coverage and unresolved timing, roster and qualifying-rank limitations. Rebuild the modelling pipeline with `build-dataset`, `select` and `evaluate`; `evaluate` is the one-time sealed test and refuses to run unless the frozen config is committed.
