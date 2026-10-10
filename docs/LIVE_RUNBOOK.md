# Live forecast operation

The workflow runs every two hours Friday–Monday UTC. GitHub scheduled runs can be delayed; the configured schedule is not a publication guarantee.

1. Fetch the target season into a new immutable cache and audit it. Collection failures return nonzero and create a health report.
2. Once the scheduled qualifying-start buffer has elapsed, require an available qualifying classification and a future scheduled race start. A buffer does not prove that a rescheduled session has ended.
3. Archive each forecast once. Future runs never replace it. Qualifying-row-only coverage is displayed; exact independent roster completeness is not claimed.
4. Join outcomes to every archived driver. Partial results are a waiting state. Only validated completion timestamps, an unchanged archive first committed before scheduled race start, and complete archived-driver outcomes enter the scorecard.
5. Persist public health on meaningful state changes. Save the complete per-run health file as a 30-day workflow artifact. `checked_at` in the public file is the last recorded state-change check, not a continuously refreshed heartbeat.

## Investigate a problem

- **Collection failed:** inspect the failed stage, upstream response and workflow logs; retry after the service recovers. Never fill unknown data with invented outcomes.
- **Qualifying unavailable:** wait for the correct classification. Inspect schedule changes and endpoint semantics. Do not force a prediction with race-result fallback entries.
- **Missed forecast:** leave the race labelled missed. A later replay cannot become a live forecast. Health starts monitoring 2026 round 17, so prior retrospective races are not counted as missed deployments.
- **Partial results:** wait for every archived-driver label. Excluded race-only drivers remain a coverage limitation.
- **Invalid archive:** inspect mode and timezone-aware timestamps. Preserve the file and its Git history; do not repair its provenance into a claim it was timely.
- **Workflow push failed:** inspect concurrent main changes and permissions. A local JSON timestamp does not prove public publication; check that its Git commit preceded scheduled race start.
- **Stale dashboard:** rebuild from the current saved artifacts. The footer gives the source-results snapshot time. The page does not fetch live data at runtime.

The `Publish dashboard` workflow deploys only the standalone HTML export through GitHub Pages. It runs on main changes and after the live workflow completes, including a failed live run so a persisted failure state can be shown. It verifies the historical artifact manifest before publishing and uploads no raw caches. GitHub Pages must be configured for Actions; no paid hosting or billing changes are required for this public repository.

No automatic model retraining or rollback threshold is introduced. A few bad races are not sufficient evidence for a new model. Operational data failures should halt publication; predictive degradation needs prospective aggregate evidence and a new untouched evaluation period.

Forecast completion is checked after fitting, immediately before archiving. Slow runs crossing scheduled race start do not create a live forecast. Scoring and dashboard export use full Git history to validate the first unchanged archive commit. Git commit time is local-history evidence, not an independently trusted timestamp of remote receipt; the site claims timely archiving/commit, not independently verified public receipt. An unverified archive remains visible as an operational issue and cannot count as live.

## Council hardening, October 7

Collection validates advertised row counts on every page (driver rows for qualifying/results/sprint endpoints), not just empty pages. A nonempty truncated page or changing pagination total fails collection instead of freezing an incomplete forecast. This does not establish a complete entered roster: qualifying-only coverage remains the policy.

New archives include canonical fingerprints of actual training features/labels and target features, the override-file hash, qualifying coverage counts, and a deduplicated source manifest inventory (URL, retrieval time, payload hash and adapter/schema versions). Raw snapshots remain local; these identities support audits, not full reconstruction without retained source data. Older archives are not backfilled with invented metadata.

If the historical bootstrap step fails before `live` runs, the workflow calls `live-failure --stage history_bootstrap` to replace public health with the failed stage and available coverage errors. Historical coverage reports are retained with health artifacts for 30 days. Environment setup failures or a cancelled/timed-out runner can still prevent this reporting step; inspect the workflow run itself.

Health is collected before the workflow commits a new archive. `unverified_archive_commit` can therefore remain until the next successful run observes that commit; it is not itself proof of a late forecast. Never edit a forecast to repair its provenance.

## Official qualifying with api-anything (October 10)

The live workflow now prefers the official F1 qualifying page for events explicitly mapped in `configs/official_sources.json`. Initial coverage is Singapore 2026 round 17. Other races continue to use Jolpica until their official IDs, circuit mapping and displayed table coverage are verified and added. Jolpica remains the schedule, historical training and race-outcome source; this is not a full replacement or a model change.

`npm ci --prefix tools/api-anything` installs api-anything from a pinned MIT-licensed upstream Git commit with a transitive lockfile. A globally installed CLI is also supported locally. The exported read-only recipe in `configs/api-anything/f1-official.json` uses direct public HTML; calls run with an isolated `API_ANYTHING_HOME` and no imported credentials. No paid API or AI subscription is required. Browser fallback is not guaranteed on CI. Schema drift, auth/rate errors and partial tables halt the pipeline and appear in health diagnostics rather than silently accepting scraped guesses.

Only due prospective events without labels or an existing archive are enriched. Driver codes and car numbers must map to earlier same-season entries; teams use explicit aliases. Unknown identities require a sourced mapping update. A nonnumeric RT/NC/DSQ/DNS position stays missing and is disclosed in the forecast. The expected row count checks the published table, not an independent entered roster. The recipe deliberately excludes lap times because missing cells are omitted by the tool's list extractor; rank-only inputs and frozen M1 inputs need no qualifying lap times.

Raw tool responses are retained under the per-run ignored `official-snapshots` directory. Archive source inventory contains response SHA-256, retrieval time, recipe/mapping hashes and transport tier. This hashes the extracted tool response, not the original HTML. Official tables can contain revisions after qualifying; retrieval time does not establish exact qualifying-end publication state. Existing overrides and archive immutability remain enforced.

Fresh `predict` and `live` collection use this configuration by default. `predict --live <dir>` replays supplied normalized files without enriching or mutating that existing snapshot. Automation still checks after qualifying and scores after Sunday's race; sprint results are excluded.
