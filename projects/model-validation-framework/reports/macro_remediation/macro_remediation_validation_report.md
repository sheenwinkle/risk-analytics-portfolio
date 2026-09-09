# Independent Macro Satellite Remediation Validation

## Opinion: RESTRICTED

The challenger remains restricted to sensitivity evidence and is not approved for point forecasting or accounting calibration.

## Selection Reperformance

- Developer candidate: `dynamic_ratio_change_lagged_macro`.
- Independently selected candidate: `dynamic_ratio_change_lagged_macro`.
- Developer and reperformed alpha: 1000.
- Maximum selection arithmetic gap: 6.35e-13.
- Selection reconciled: **True**.
- The selected row uses validation metrics only; OOT evidence is reused.

## Independent OOT Reperformance

- OOT period: 2019-03-31 to 2021-12-31.
- Challenger MAE: 0.000512.
- Persistence MAE: 0.000511.
- MAE improvement versus persistence: -0.35%.
- RMSE improvement versus persistence: 1.57%.
- MAE reduction versus incumbent: 14.73%.
- RMSE reduction versus incumbent: 24.61%.

## Control Results

- Passed controls: 10.
- Failed controls: 2.
- Warnings: 1.

## Finding Lifecycle

- MSV-001 remains open: Only one reused-OOT error benchmark passed and the evidence is not fresh.
- MSV-002 is pending_fresh_oot: Both macro factors are active, but stability requires fresh OOT evidence.
- MSV-003 remains open: Lags address timing, but real-time data revisions remain unevidenced.
- No finding is closed by reused OOT evidence.

## Required Next Evidence

Collect a genuinely post-selection outcome window under a comparable target definition, preserve release-date macro vintages, and repeat the benchmark and coefficient-stability tests before requesting closure.

Educational portfolio case study; not a production validation approval.
