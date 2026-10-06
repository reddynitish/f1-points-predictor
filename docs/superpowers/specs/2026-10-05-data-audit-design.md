# Milestone A design

Approved in chat October 5, 2026. Build a local CPU-first Python package with a locked environment, a resumable historical-results adapter, synthetic tests, one-weekend inspection and 2018–2025 coverage report. No models or dashboard.

Jolpica JSON snapshots are immutable local files with retrieval UTC, URL, schema and adapter versions and SHA256. Cache reuse verifies integrity; offline mode refuses network. Three attempts with backoff respect Retry-After. Separate normalization from transport.

Entries are the union of qualifying and race-result driver IDs, explicitly marked as a retrospective roster approximation, not proof of the qualifying-end entry list. Race-only drivers retain missing qualifying. Outcome fields remain in a separate label table. Constructor values retain upstream IDs; aliases are deferred until audited.

Scheduled qualifying start is never qualifying end. Actual end remains null unless independently evidenced; unavailable timing blocks the cutoff gate. Sprint-era qualifying semantics require explicit review. Coverage audits may inspect 2025 schema/counts but must not publish its outcome values or metrics. Raw snapshots and normalized tables remain ignored.

Tests cover missing sessions/segments, duplicate keys, invalid ranks/durations, result-only drivers, cache corruption, offline behavior and retry limits. Availability is descriptive; failures remain visible. Commit meaningful verified increments and push them as requested.
