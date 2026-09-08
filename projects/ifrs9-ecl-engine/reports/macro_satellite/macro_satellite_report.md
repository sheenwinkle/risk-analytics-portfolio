# Australian Macro Satellite and ECL Challenger Report

A frozen, directionally constrained model maps public Australian macro conditions to an aggregate bank NPL proxy.

## Data and Design

- Target: APRA impaired plus past-due facilities divided by gross loans.
- Macro drivers: ABS unemployment and real GDP series distributed by the RBA.
- Development ends 2015 Q4, tuning ends 2018 Q4, and OOT ends 2021 Q4.
- The APS 220 definition change from 2022 Q1 is excluded rather than spliced.
- The 2026 macro snapshot contains revised historical observations; release-date vintages are not reconstructed.
- Coefficients are constrained nonnegative after GDP is expressed as a stress factor.

## Frozen Backtest

- OOT observations: 12
- Satellite MAE: 0.000601
- Persistence MAE: 0.000511
- MAE improvement versus persistence: -17.7%
- Unemployment coefficient: 0.000000 (the constrained fit did not retain incremental level sensitivity)

## Scenario Translation

- Downside shock: unemployment +3.0pp and real GDP growth -6.0pp; estimated NPL multiplier 1.152.
- Scenario multipliers are diagnostic proxies, not accounting-approved PD calibrations.

## A/B ECL Impact

- Incumbent manual-multiplier ECL: 27,996.92
- Empirical challenger ECL: 25,233.66
- Challenger change: -2,763.26 (-9.9%)
- The A/B comparison changes only scenario PD multipliers; accounts, LGD, EAD, and weights are held fixed.

## Use Restriction

The challenger is not approved for point forecasting because it does not beat the persistence benchmark on the frozen OOT period. It may be used only as transparent sensitivity evidence pending remediation and revalidation.

## Reconciliation

- Incumbent engine total: 27,996.92
- Challenger engine total: 25,233.66
