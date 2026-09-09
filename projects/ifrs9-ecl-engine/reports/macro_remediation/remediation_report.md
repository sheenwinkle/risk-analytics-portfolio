# Australian Macro Satellite Remediation

## Developer Decision

- Recommendation: **RETAIN RESTRICTED USE** (`sensitivity_only`).
- Reused-OOT retest result: **mixed_benchmark_evidence**.
- This developer remediation does not close MSV-001.

## Controlled Selection

- Pre-registered candidates: 4; candidate-alpha evaluations: 28.
- Selected candidate: `dynamic_ratio_change_lagged_macro`.
- Selected Ridge alpha: 1000.
- Selection period: 2016Q1-2018Q4.
- OOT was not used for candidate or hyperparameter selection; the 2019Q1-2021Q4 window was revealed only after the specification was frozen.
- Every eligible macro input is lagged to the forecast origin.

## Validation Selection Evidence

- Validation MAE: 0.000202.
- Validation persistence MAE: 0.000192.
- Composite MAE/RMSE ratio: 1.0431.

## Reused OOT Evidence

- OOT observations: 12.
- Challenger MAE: 0.000512.
- Persistence MAE: 0.000511.
- MAE improvement versus persistence: -0.35%.
- RMSE improvement versus persistence: 1.57%.
- MAE reduction versus the incumbent satellite: 14.73%.
- RMSE reduction versus the incumbent satellite: 24.61%.
- Active lagged macro drivers: 2.

## Governance Boundary

The error reductions are historical model-performance deltas, not a realised loss saving or accounting benefit. The OOT period has already been observed during remediation, so it is supporting evidence rather than fresh closure evidence.
Closure blocker: Fresh post-selection OOT outcomes and real-time macro vintages are not available.

Educational portfolio case study; not a production model-change approval.
