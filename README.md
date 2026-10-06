# F1 Points Predictor

An independent Formula 1 machine-learning project: estimate each driver's probability of finishing in the points after qualifying.

**Status: planning. No trained model, results, or working application yet.**

Read the [detailed master plan](docs/MASTER_PLAN.md) and [research audit](docs/RELATED_WORK.md).

Planned workflow: cached historical results → information available after qualifying → chronological backtesting → calibrated probabilities → dashboard showing predictions and errors.

Local CPU-first training with Python, pandas, FastF1 and scikit-learn. No paid AI APIs are part of the planned runtime. Data access remains subject to upstream availability and terms.

Not affiliated with Formula 1, the FIA, teams, or drivers. Educational forecasting; no guaranteed outcomes.
