# Official qualifying through api-anything

Authorized October 10: use the installed api-anything tool to avoid waiting for Jolpica qualifying publication. Prefer an official qualifying table for explicitly configured prospective events; retain Jolpica for historical features, schedule and outcomes. Models, features and thresholds stay frozen.

A credential-free learned HTML operation reads the official Grand Prix qualifying page. Validate title/year/session, configured circuit, table row count, equal column lengths, unique driver codes/car numbers/ranks, canonical driver identities from earlier same-season entries, and explicit team aliases. RT/NC/DSQ retain missing rank. Reject unknown identities, drift, partial data and errors. No race outcomes, grid, or sprint qualifying enter the operation.

Only due events before race start without labels or existing archives are eligible. Cache the complete tool response locally with retrieval time and SHA-256; add that manifest and the recipe hash to archive input identities. Do not overwrite forecasts or historical caches. Use an isolated runtime home seeded from the committed exported recipe; do not import browser credentials. Scheduled Linux runners use a pinned Node dependency. The direct HTTP tier is verified locally; browser fallback availability is not guaranteed in CI.

Initially configure Singapore 2026 round 17 only, with a verified official page and 22 displayed qualifying rows. This is a table coverage check, not independently verified entered-roster completeness. Further event mappings require a verified official URL and circuit. Source revisions may differ from qualifying-end classification; disclose retrieval timing and retain existing overrides.
