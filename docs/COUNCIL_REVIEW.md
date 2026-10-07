# Repeatable project council

Use a bounded council after a meaningful milestone: a completed prospective race, a reproducibility change, a new UI workflow, or a newly pre-registered experiment. No recurring job or background review is configured by this document.

## Protocol

1. Freeze the review commit and require each reviewer to read `AGENTS.md`, README, master plan and related work.
2. Obtain independent read-only reviews from ML/evaluation, software engineering, and product/design/hiring perspectives. Keep implementation separate from review. Shared-model reviewers provide perspectives, not independent model-provider consensus.
3. Require each finding to cite a real file/line, reproduce the trigger where practical, explain the impact and suggest a bounded fix. Distinguish bugs, evidence limitations and optional polish.
4. Relay the findings for a challenge round. Preserve disagreements, withdrawn concerns and evidence that changed severity. Do not force unanimity.
5. Verify before implementing. Fix concrete defects with focused commits and tests; correct reporting without silently regenerating spent-test artifacts.
6. Re-review the actual diff, run appropriate checks, save a dated report, and identify what future evidence still requires human or real-world observation.

A request for another pass:

> Run the project council on the current commit using independent ML, engineering, and product/hiring reviewers. Inspect real code and artifacts; challenge each other's findings. Preserve disagreements in a dated report. Fix verified high-value issues with focused commits and checks, then re-review the actual diff. Preserve frozen models, spent holdouts, the qualifying cutoff, no-paid-services/no-raw-data-upload constraints and separate resume approval. Avoid adding complexity just to satisfy the reviewers.

The first review is [October 7, 2026](../reports/COUNCIL_REVIEW_2026-10-07.md).
