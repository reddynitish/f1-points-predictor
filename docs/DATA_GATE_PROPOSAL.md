# Milestone A data gate: design proposal

**Date:** October 6, 2026. **Status:** recommended options A, qualifying-row roster and R3 adopted provisionally on October 6, 2026 so modelling could proceed (see reports/MODEL_CARD.md); The October 7 portfolio-improvement authorization continues the recommended implementation defaults; it is not a claim that Nitish separately selected each alternative. The sprint-endpoint comparison is now recorded in [SPRINT_AUDIT.md](../reports/SPRINT_AUDIT.md). Evidence comes from the cached Jolpica snapshots ([DATA_AUDIT.md](../reports/DATA_AUDIT.md)) and a small FastF1 live-timing probe ([scripts/probe_session_timing.py](../scripts/probe_session_timing.py)) run on 10 qualifying sessions.

## 1. Actual qualifying end

### Evidence

- Jolpica provides only *scheduled* qualifying start for 2022–2025. Scheduled times are wrong for rescheduled events: in 2024-21 the qualifying session ran about 16.5 hours after its listed time.
- F1 live-timing `SessionInfo` also kept the original Saturday slot for 2024-21. It is not an observed time either.
- FastF1's event schedule shows the rescheduled 2024-21 start (2024-11-03 10:30 UTC). This is better than Jolpica's time but is still a schedule.
- Live-timing `SessionStatus` records `Started/Finished/Finalised/Ends` as offsets into the stream. Each `Heartbeat` message pairs a stream offset with a UTC clock reading, which turns those offsets into UTC.
- In the sampled 2019–2025 sessions (2019-01, 2020-01, 2021-01, 2021-10, 2022-01, 2023-01, 2024-05, 2024-21, 2025-01), anchors drift by 13–20 minutes within a session. `Finalised` can be bounded but not pinned exactly. Example: 2024-21 lands between 12:15 and 12:28 UTC.
- Both sampled 2018 archives (2018-01, 2018-12) have heartbeat clocks from August 2018, and their stream offsets don't match wall-clock time. No anchor can be taken from them.

### Why minute precision matters less than it looks

Under the master plan, every historical feature comes from **prior events**, whose races finished days before the target qualifying. The only things whose availability depends on minutes around qualifying end are:

1. the target qualifying result itself, which is provisional at the flag and can be revised later (section 3);
2. a current-weekend sprint in 2024–2025, which is scheduled *before* qualifying and excluded by rule in v1;
3. grid penalties and starting-grid changes, which are already excluded from v1.

### Options

| Option | Definition | 2018 | Cost |
|---|---|---|---|
| A. Interval cutoff | `cutoff_lower = FastF1 scheduled qualifying start`, `cutoff_upper = upstream race start`; history features must predate `cutoff_lower`; current-weekend data other than qualifying is forbidden by allowlist | works | no new source |
| B. Bounded observed end | A plus `qualifying_end_utc_latest` from the heartbeat probe where the anchor is usable; `cutoff_ready` requires a usable bound | 2018 not ready, or kept on A with a flag | new FastF1 adapter, about 170 archive downloads |
| C. Exact observed end | requires a source with absolute session-end timestamps | unknown | no free source identified |

**Recommendation: A for v1. Record B's bounds as audit evidence where available, but don't let them gate training.** Under A, an event is `cutoff_ready` when the target-event sources are explicitly enumerated and every history source predates the scheduled qualifying start. If B is chosen instead, 2018 must either be dropped or kept with a weaker flag, and the choice made before any model work.

## 2. Independent entry and team provenance

Today the roster is the union of Jolpica qualifying and race-result rows, and race-result-only drivers get their constructor from the race result. That is retrospective.

Candidate independent source: live-timing `DriverList` for the qualifying session, which lists car number, abbreviation and team name as broadcast during the session. Probing it would need the same FastF1 adapter as option B. It also brings a new mapping problem: live-timing team names and abbreviations need explicit aliases to Jolpica `constructorId`/`driverId`, and those aliases must be audited and versioned.

**Recommendation:** for v1, define the entry roster as "drivers with a qualifying row", and report race-only drivers (4 rows across 2018–2025) as excluded from prediction rows with a coverage entry. Their race labels stay unused rather than being given a guessed constructor. If you want those drivers covered, `DriverList` is the source to add.

## 3. Qualifying revisions and repeated ranks

All five repeated-rank events coincide with a post-session disqualification or a deleted lap. The upstream rank mixes pre- and post-decision positions (see DATA_AUDIT.md).

| Option | Target qualifying input | Trade-off |
|---|---|---|
| R1. Keep upstream rank, flag | as published | collisions break the "rank is a permutation" assumption; small |
| R2. Post-decision classification | disqualified drivers moved to the back, others re-ranked | reflects the official order, but disqualifications can be decided hours after the flag, so this is arguably post-cutoff |
| R3. Disqualified rank missing | `qualifying_rank = null` plus a `qualifying_disqualified` flag for the 5 DSQ rows; the deleted-lap case keeps its rank | honest about cutoff ambiguity; the rank-missing path already exists |

**Recommendation: R3**, with the affected rows listed in a committed, sourced override file (`overrides/qualifying.csv`: event_id, driver_id, kind, source URL). Hand overrides are auditable and small (5 rows). Inferring disqualifications automatically from a ranking gap would be fragile.

## 4. Sprint semantics

Implemented: `weekend_format`, `qualifying_determines` and `sprint_scheduled_before_qualifying` from schedule keys. Still open: confirming that the qualifying endpoint never returns sprint-qualifying or shootout results. That check needs either Jolpica `sprint.json` (its `grid` column approximates sprint-qualifying order) or live-timing sessions. **Recommendation:** one Jolpica `sprint.json` fetch per season (2021–2025). Same cache and adapter, no new dependency. Then assert the two orders differ for at least the events where public sources report different pole-sitters.

## Implemented policy and remaining limitations

1. Cutoff: A (interval) remains the implemented default; exact observed-end reconstruction is unavailable.
2. Roster: qualifying-row-only remains the implemented default; race-only drivers are excluded and counted.
3. Revisions: sourced rank-missing overrides remain the implemented default; they do not establish exact flag-time ranks.
4. Sprint: the five-season endpoint comparison is complete, with 24 events recorded in the audit report.

Original coverage files retain their historical `cutoff_ready=false` audit state. They are not silently rewritten to claim exact timestamp readiness. The feature builder enforces the disclosed interval/history contract instead.

October 7 implementation update: A, qualifying-row roster and R3 remain the implemented policies. The five-season sprint comparison is complete (24 events); see the audit report. Exact qualifying-end timestamps and historical revision-time reconstruction remain unavailable. This update does not re-open any spent evaluation period.
