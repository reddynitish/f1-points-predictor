# Related work and source audit

Reviewed October 5, 2026. These are design references, not verified performance endorsements. No source code has been copied.

## FastF1

https://github.com/theOehrly/Fast-F1

Primary data library: results, qualifying/timing data, pandas integration, request caching and jolpica support. Adopt caching and canonical identifiers. Start with results/qualifying; downloading all telemetry is unnecessary for the first target. Its MIT software license is separate from rights and terms for upstream data.

## SilverSouls226/f1-race-predictor

https://github.com/SilverSouls226/f1-race-predictor

Inspected README and `src/modeling.py` through GitHub API. Valuable: separate collection, preparation, modelling and dashboard; chronological season holdout; shifted historical driver form; comparison of simple and stronger models.

Do not copy its feature matrix: inspected code selects current-race sector averages, classification status and main tyre compound. Those are unavailable at a post-qualifying cutoff. Its team expanding mean shifts individual driver rows; a teammate's same-race outcome can enter another row. Aggregate both teammates by event first, then shift whole events. Row-level TimeSeriesSplit also needs race grouping. No reported metric is adopted.

## Dineshsathiya/2026_f1_predictions

https://github.com/Dineshsathiya/2026_f1_predictions

Inspected README and beginning of `chinesegp.py`. Valuable: FastF1 cache, explicit past-race list, qualifying loader, transparent pace/stint features. A tyre-degradation proxy subtracts first-three-lap mean from last-three-lap mean. That confounds fuel burn, traffic and track changes; do not present it as causal degradation. One prior race is insufficient for our intended evaluation. Use multiple historical seasons and exclude current-race outcomes.

## frankndungu/f1-jeddah-prediction-2025

https://github.com/frankndungu/f1-jeddah-prediction-2025

README-level review only. Useful inspiration: explainable scores and visible fan-facing presentation. Implementation and benchmark claims not audited; not a code dependency.

## A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing

https://arxiv.org/abs/2512.00640

Research direction for a later tyre/pace module, not a requirement for version 1. Separating latent degradation from observed timing is more rigorous than assuming any pace change is tyre wear.

## Egor Howell — Production-Grade ML Project Tutorial (video)

https://www.youtube.com/watch?v=2BvLAJwvfgo — reviewed October 6, 2026 from auto-generated captions (full 87 minutes); code repository not inspected or copied.

Stock-price forecaster with portfolio optimisation, used here only as an engineering-workflow reference. Adopted: a Makefile with one `make check` gate (format, lint, type check, tests), ruff and mypy, CI that runs the same gate on every pull request, logging instead of prints, secrets kept out of code, and a protected main branch that only accepts merges through pull requests after CI passes. CircleCI is replaced by GitHub Actions to avoid another account.

Not adopted: paid VPS hosting and a hosted database (conflict with the no-paid-services constraint; the plan keeps a local dashboard reading saved artifacts), and scheduled daily predictions (deferred to milestone F, after data and leakage gates). The video's model is refit and scored without a chronological backtest or baseline comparison; our evaluation protocol (frozen splits, B0/B1 baselines, sealed 2025 test) stays as planned. The suggestion that test code should outweigh source code is treated as a heuristic, not a target.

## Evaluation references

- https://scikit-learn.org/stable/modules/cross_validation.html — chronological and grouped splitting.
- https://scikit-learn.org/stable/common_pitfalls.html — train-only transformations and leakage prevention.
- https://scikit-learn.org/stable/modules/calibration.html — reliability diagrams and probability calibration.

## Excluded reference

https://github.com/manasscodes/f1-race-intelligence had only README and gitignore in the inspected tree while claiming a full pipeline and specific scores. Excluded as a runnable example and benchmark evidence.

## Learning resources

- https://www.youtube.com/watch?v=7v9puRHfelw — Simplilearn F1 Python data analysis; captions inspected, not a full ML course.
- https://www.youtube.com/watch?v=eWJBRvveJBo — Bayesian-network podium project presentation; metadata inspected, code/evaluation not audited.
- https://www.youtube.com/watch?v=3CC4N4z3GJc — StatQuest gradient-boost regression concepts.
- https://www.youtube.com/watch?v=TiQEElXyY2w — Tom Shaw race replay project; presentation inspiration, not ML training.
