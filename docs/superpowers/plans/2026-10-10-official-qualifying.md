# Official qualifying implementation plan

Execute inline in an isolated checkout.

1. Write synthetic validation tests in tests/test_official.py and confirm import failure before implementation.
2. Implement src/f1_points/official.py: checked subprocess invocation, isolated exported recipe, immutable response cache, strict table normalization, same-season identity mapping, due-event enrichment.
3. Add --official-sources to live and fresh predict collection; preserve archived forecasts. Add verified Singapore source mapping and explicit constructor aliases.
4. Pin api-anything by Git commit in tools/api-anything/package.json and lock transitive dependencies. Install Node runtime in live workflow, then run collection through the adapter.
5. Run synthetic tests, make check, live adapter call, and an actual Singapore forecast before race start. Record provenance and limitations in LIVE_RUNBOOK and RELATED_WORK.
6. Commit only code, recipes, docs and forecast metadata; push a branch and create a reviewable pull request. Keep raw data and node_modules ignored. Verify CI and archive commitment before race start.
