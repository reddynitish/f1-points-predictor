# F1 Points Predictor — chat handoff

Read README.md, docs/MASTER_PLAN.md and docs/RELATED_WORK.md before working.

## Current state

- Local project: /Users/nitishreddy/f1-points-predictor
- GitHub: https://github.com/reddynitish/f1-points-predictor
- Milestones A–E (provisional data-gate decisions, cutoff-safe features, baselines, selection, one sealed 2025 evaluation) are implemented; see reports/MODEL_CARD.md. M1 did not beat the B1 rank-only baseline on 2025 (inconclusive), so B1 is the primary forecast. The 2025 test is now spent: any further model change needs a new untouched period (2026 shadow results).
- GitHub repo is private at Nitish's request until there is enough work to publish.
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

Run `predict --season 2026 --round 17` after Singapore qualifying (2026-10-10 13:00 UTC) and archive it before the race; evaluate prospective forecasts against published results as 2026 shadow evaluation. Nitish has not yet confirmed the provisional data-gate decisions in docs/DATA_GATE_PROPOSAL.md. Dashboard (milestone F) not started.

The plan is a proposal, not proof that any model improves upon the baseline. Show failures and inconclusive results. Resume usage is a separate approval decision.
