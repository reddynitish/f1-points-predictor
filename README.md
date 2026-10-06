# F1 Points Predictor

An independent Formula 1 machine-learning project: estimate each driver's probability of finishing in the points after qualifying.

**Status: milestone A collection and availability audit implemented. Data cutoff gate remains open; no trained model or application yet.**

Read the [detailed master plan](docs/MASTER_PLAN.md) and [research audit](docs/RELATED_WORK.md).

Planned workflow: cached historical results → information available after qualifying → chronological backtesting → calibrated probabilities → dashboard showing predictions and errors.

Local CPU-first training with Python, pandas, FastF1 and scikit-learn. No paid AI APIs are part of the planned runtime. Data access remains subject to upstream availability and terms.

Not affiliated with Formula 1, the FIA, teams, or drivers. Educational forecasting; no guaranteed outcomes.

## Local data audit

```sh
uv sync --locked
uv run pytest -q
uv run python -m f1_points.cli collect
uv run python -m f1_points.cli collect --offline --report data/offline-coverage.json
```

Python 3.12 is pinned. Downloads and normalized records stay under ignored `data/`; cached downloads support offline replay. Read [the data audit](reports/DATA_AUDIT.md) and [per-event coverage](reports/coverage.json) for observed coverage and unresolved timing, roster and qualifying-rank limitations. No training commands exist yet.
