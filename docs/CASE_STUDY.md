# F1 forecasting: engineering decisions and evidence

## Problem and result

Estimate a qualifying driver's probability of positive Grand Prix points, using qualifying rank and earlier race history. Qualifying rank is not the Sunday grid, and sprint points are excluded. This is a probabilistic fan-facing forecast, not a race strategy or betting tool.

The richer v1 model improved development scores but did not demonstrate improvement over the qualifying-only B1 baseline on the sealed 2025 test or 2026 replay. Practice, qualifying-gap, weather and grid experiments also did not beat their respective baselines. B1 stays primary. The useful outcome is a reproducible forecasting system with a documented model-selection decision, not an invented accuracy claim.

## Decisions a reviewer can inspect

| Decision | Reason | Evidence |
|---|---|---|
| Aggregate whole prior team events before shifting | Prevent one teammate's target outcome leaking into another's features | `tests/test_leakage.py` mutation and teammate tests |
| Expanding whole-season validation | Preserve chronology and keep all drivers in a race together | `modeling.make_splits`, split lists in diagnostics |
| Keep rank-only B1 | Complexity needs demonstrated out-of-sample benefit | Model card and event-bootstrap comparisons |
| Immutable prospective archives | Prevent quietly replacing failed forecasts | Refusal/archive tests and Git timestamps |
| Wait for all archived-driver outcomes | Avoid publishing a biased partial score | `test_partial_results_wait_for_every_archived_driver` |
| Static dashboard from saved artifacts | Free hosting, no runtime AI/API subscription, inspectable output | `make dashboard`; exporter validation/escaping tests |
| Small JSON manifests instead of a tracking server | Sufficient traceability for this bounded CPU study | `make verify-portfolio`; hash tamper rejection test |

## Reproduce the visible evidence

From a clean clone with Python 3.12 and uv:

```sh
make install
make check
make verify-portfolio
make demo
make dashboard
```

The first command installs locked dependencies and may use the network. The remaining demo/verification/export operations use only committed artifacts and invented fixtures. Open `docs/dashboard/index.html` directly in a browser. Full historical collection/training requires separately downloaded data and is not pretended to be an offline clean-clone operation.

The integrity command checks frozen configuration hashes, artifact hashes, identical evaluation row sets and Brier agreement within 0.0001 for rounded saved probabilities. It recomputes metrics from saved predictions; it does not fit a new model or run the sealed test again. Integrity hashes establish consistency, not independent scientific replication or authorship.

`make demo` fits the frozen B1/M1 settings on three invented events. It saves explicitly synthetic probabilities and measured runtime/process peak RSS to `/tmp/f1-points-demo/`. This is a smoke demonstration, not evidence of F1 predictive performance. A local October 7 run took 0.032235 seconds for feature construction and two tiny fits, with 180.69 MiB process-lifetime peak RSS (including imported libraries). These measurements are machine-specific and not a production throughput claim. The performance report identifies Python/platform, configuration and fixture hashes, and explains the memory/timing scope. Peak RSS is measured on macOS/Linux; it is explicitly unavailable on platforms without the resource module. Verification and the synthetic demo remain usable without that module.

## Limits and next evidence

The roster is qualifying-row-only. Historical results use retrieved final classifications and exact revision-time reconstruction is unavailable. The interval cutoff is weaker than a verified flag-time snapshot. Sprint endpoint separation was audited on 24 events, with starting grids serving only as a proxy. There are only 16 events in the 2026 backtest, and live prospective results are not yet available.

After qualifying, the live workflow should commit a forecast before the race, record health diagnostics, then score only after all archived-driver results exist. Real operation must be demonstrated by those future records. Further model changes need a newly pre-registered untouched future period.

## Authorship and assistance

This project was developed with AI coding assistance, including Codex-assisted implementation, tests, documentation and portfolio UI. Data libraries and methodological references are attributed in `docs/RELATED_WORK.md`; no external predictor's code or reported performance is presented as this project's own. The repository demonstrates inspectable engineering work, but a commit history alone does not establish unaided authorship or personal understanding.

For interviews, review the actual code and be prepared to explain the leakage mutation test, whole-event split, probability calibration, baseline decision and partial-result scoring fix. Describe your own contribution and learning accurately; this document does not invent them. Resume wording remains a separate review decision.

## Council review, October 7

Three independent agent reviewers examined ML methodology, engineering, and product/hiring presentation, then challenged each other's findings. The [review record](../reports/COUNCIL_REVIEW_2026-10-07.md) preserves disagreements and verified fixes. These reviewers use the same model family and are not independent human validators.

The review corrected an asymmetric comparison label: the original 2025 walk-forward diagnostic refits M1 against a fixed-season B1. It also distinguished 2026's uniform ten-place heuristic (10 divided by covered drivers) from the original prevalence B0. Original configurations and evaluation outputs remain unchanged; no spent test was rerun.

Integrity coverage now pins development, sealed-2025 and source coverage artifacts as well as the 2026 comparisons. Live input identities and workflow-stage failure reporting improve auditability; neither hashes nor Git dates establish independent source authenticity or historical publication timing.
