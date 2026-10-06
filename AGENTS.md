# F1 Points Predictor — chat handoff

Read README.md, docs/MASTER_PLAN.md and docs/RELATED_WORK.md before working.

## Current state

- Local project: /Users/nitishreddy/f1-points-predictor
- GitHub: https://github.com/reddynitish/f1-points-predictor
- Planning documents are pushed. No predictive model, dataset, application or experiments exist yet.
- User wants a Formula 1 ML project for learning and software-engineering/applied-AI portfolio evidence.

## Constraints

- Local CPU-first training. No paid APIs, generation credits, cloud billing or required runtime AI subscriptions.
- Predict positive race points from information available at qualifying end. Qualifying rank is not final Sunday starting grid.
- Historical results only for driver/team form. Team history aggregates whole prior events before shifting; never use a teammate's target-race result.
- No current-race outcomes, race telemetry, race weather, classification status or actual pit strategy as pre-race features.
- Keep complete events together in chronological splits. Reserve 2025 final test; freeze choices before evaluation. Record dataset coverage and revisions honestly.
- No fabricated metrics or completed-work claims. Do not copy external code without checking license and recording attribution.
- Do not upload raw data, cache, credentials or large binaries. Preserve small synthetic fixtures for tests.

## Next work

The next milestone is A: environment, data adapter, one-weekend data audit and full availability report. Read the master plan, identify any design issues, and discuss necessary changes with Nitish before implementation. Do not begin model tuning or dashboard work until data and leakage gates pass.

The plan is a proposal, not proof that any model improves upon the baseline. Show failures and inconclusive results. Resume usage is a separate approval decision.
