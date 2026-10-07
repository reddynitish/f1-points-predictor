# Council review — October 7, 2026

## Decision

Keep B1 as the primary forecast. The project provides credible educational software-engineering and applied-ML evidence, especially its baseline decision and leakage checks. It has not established a richer model's predictive advantage or a prospective forecasting track record. Improve auditability, operational failure handling and clarity before adding model complexity.

Review baseline: `2849034`. Fixes: `912afab`, `f87394c`, `1662325`, `aea221c`. The original frozen configs and saved evaluation predictions were preserved; no held-out model evaluation was rerun.

## Review process and limits

Three separate agent reviewers inspected the repository independently: ML methodology; software engineering; product/design with a hiring-manager perspective. The parent relayed findings between reviewers for a challenge round, verified concrete issues, and implemented bounded fixes. Agents shared a model family; this is not cross-provider consensus or independent human validation.

Reviewers read the actual code, reports and committed screenshots. The product reviewer could not access Pages through its web tool, so browser verification was performed by the parent. Initial post-fix agent re-review attempts were interrupted by a usage limit; a fresh final reviewer was dispatched after continuation. The fresh final reviewer reported scoped approval: no blocking regression in the four-commit diff or case-study addition. It passed 45 targeted tests, verified 23 pinned artifacts and three comparisons, checked page counts against all 97 cached Jolpica pages, and confirmed configurations/saved predictions were unchanged. It did not perform browser accessibility testing or future-race operation. No claimed hiring outcome, personal competence rating, or synthetic performance score is inferred from agent agreement.

## Accepted findings and changes

| Priority | Verified finding | Change and evidence |
|---|---|---|
| P2 | 2025 walk-forward M1 was compared against fixed-season B1 (`experiments.py`, replay/bootstrap) | Model card now names the asymmetric diagnostic. The fixed-season comparison remains the matched evidence; original files retained. |
| P2 | Headline qualifying-end certainty exceeded the historical timing/revision evidence | README and backtest opening now disclose retrieved classifications and interval timing next to metrics. No demonstrated result leakage was established by this finding. |
| P2 | 2026 B0 uses 10/N after outcome/coverage merging, rather than training prevalence | Labelled a uniform ten-place prior over scored covered rows, with denominator and 37% comparison limits. Original metrics unchanged. |
| P2 | Nonempty truncated source pages passed collection | Collector checks nested driver-row counts on qualifying/results/sprint endpoints, race counts on schedules, and stable pagination totals. Synthetic truncated-page regression tests first failed, then passed. |
| P2 | Historical bootstrap failed before the live health wrapper | Workflow fallback records the failed stage and available coverage errors; history coverage is retained with per-run diagnostics. Regression test confirms stale success is replaced while previous success time is preserved. |
| P2 | Future forecast archives lacked exact input identities | Actual training/target row fingerprints, override hash, qualifying coverage and deduplicated source inventory are wired into future archives. Target-outcome mutation and input-shuffle tests preserve fingerprints; earlier-label mutation changes the training fingerprint. |
| P2 | Mobile ledger hid comparison/outcomes with no scrolling guidance; comparison header was ambiguous | Labelled keyboard-focusable table region, mobile scroll hint, dynamic B1/M1 heading, concise Brier definition, event status announcement, wider mobile selector and compact hero. |
| P3 | Integrity scope omitted central sealed/development/source evidence | Manifest now pins 23 artifacts, including original 2025 predictions/report, development studies and source coverage. These added files are hash-checked, not scientifically re-evaluated. Dashboard auxiliary inputs are also fingerprinted. |

## Challenges and disagreements

- Product initially rated cutoff overclaim P1; ML and engineering found no demonstrated leakage. Product agreed to P2 after challenge. The prominent claim was still corrected.
- A suspected Sepang calendar inconsistency was withdrawn after checking the [official F1 calendar update](https://corp.formula1.com/formula-1-and-fia-confirm-that-malaysia-will-join-the-2026-calendar-as-host-venue-for-the-bahrain-grand-prix/). Circuit IDs alone were not evidence of invented inputs.
- Engineering reproduced a three-driver forecast from a four-driver fixture. Qualifying-row-only coverage is an explicitly accepted policy, so the council rejected an arbitrary 22-driver gate. Advertised API truncation was the concrete transport defect; independent full-roster completeness remains unproven.
- Source fingerprints were accepted as bounded audit evidence. They do not enable full reproduction without the raw cache; the no-raw-data-upload constraint remains in force.
- New controls, elaborate tracking infrastructure, animations and another model were not justified by these findings.

## Evidence checked

The ML reviewer checked 97 local historical/2026 Jolpica snapshot body hashes, matched the 86 historical and nine 2026 report manifests to that cache, and checked all 347 saved 2026 labels against source race points > 0. The parent independently repeated the 97-body hash check. These checks establish local consistency, not remote authenticity or exact historical availability.

Post-fix `make check`: 104 tests passed; formatting, ruff and mypy passed. Four existing scikit-learn warnings arise from all-missing early-history columns in the tiny synthetic backtest fixture. `make verify-portfolio`: 23 artifacts and three saved 2026 comparisons verified. `make demo`: deterministic prediction hash remained `c030feae884123677b940ef51781a3b6ae6c38151c3a7f8ecbf099dc56fdf54c`. `node --check web/app.js` and standalone dashboard export passed.

Browser checks: model switching changes the comparison heading and status correctly; at a 390×844 viewport the actual page was 375 px wide with 375 px scroll width, while the intentionally scrollable ledger was 666 px inside a 317 px region. Keyboard focus and horizontal movement were observed. This is a focused usability check, not a complete WCAG audit.

## Remaining evidence and next review

1. Observe a real qualifying-before-race archive and post-race score, starting with an eligible untouched future race. Inspect input identities, coverage, commitment time and failure recovery.
2. Reconstruct exact historical qualifying publication/revision timing only if better source evidence becomes available; keep current limitations visible.
3. Independent full entered-roster coverage remains unavailable. Never interpret completed archived-driver outcomes as proof of complete event coverage.
4. Runner setup failures or cancellation can prevent even failure-reporting steps. Workflow run status remains authoritative; public health is a saved snapshot. Newly created archives may show `unverified_archive_commit` until the next successful run sees their first commit.
5. Any future model change needs a newly pre-registered untouched period. The asymmetric 2025 diagnostic is not repaired by reopening that test.
6. Personal interview understanding must be demonstrated by the owner. Resume wording remains a separate decision.

Use [the repeatable review protocol](../docs/COUNCIL_REVIEW.md) after a material milestone. A council opinion is a source of testable findings, not a requirement to keep adding features.
