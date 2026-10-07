# Portfolio implementation plan

**Goal:** Make the forecasting project usable, verifiable and credible to portfolio reviewers.

**Architecture:** Export committed artifacts to a standalone HTML dashboard. Keep monitoring, diagnostics and verification in focused Python modules; preserve existing inference and experiment contracts.

**Constraints:** CPU only; no paid services; no raw data uploads; no new holdout evaluation; no fabricated forecasts or ownership claims.

## Tasks

- [ ] Audit and consistency: add `audit.py` and synthetic sprint tests; collect sprint snapshots locally; write `reports/SPRINT_AUDIT.md`; reconcile rounded metrics and stale planning text. Verify with audit tests and `make check`, then commit.
- [ ] Live health: extend `live.py` and CLI with complete-result scoring and run health; test partial outcomes, invalid prospective timestamps, collection failure and missed forecast. Persist health as a workflow artifact, then commit after `make check`.
- [ ] Diagnostics: add `analysis.py`, segment/count/uncertainty tests and descriptive saved-output report; run fixed development-only ablations with explicit split manifest and hashes. Verify math on synthetic rows, then commit.
- [ ] Dashboard: add `dashboard.py`, `web/` template assets and exporter tests for escaping, missing data and probability bounds. Build `docs/dashboard/index.html` from saved artifacts; review desktop/mobile and event selection, then commit after `make check`.
- [ ] Verification/demo: add `portfolio.py` with hash and metric validation plus a deterministic synthetic forecast demo; test tamper rejection. Add Make targets, case study, runbook and dashboard screenshots; run clean-checkout offline commands and `make check`, then commit and push the branch.

No dependencies are added for the static UI. Output reports disclose rounded CSV precision and descriptive-only analysis. The real live scorecard remains empty until races are forecast prospectively and scored.
