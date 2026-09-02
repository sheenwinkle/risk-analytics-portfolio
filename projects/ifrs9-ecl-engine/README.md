# IFRS 9 ECL Engine

Status: planned.

This project will extend the PD model into an expected credit loss engine.

## Planned Scope

- Stage 1, Stage 2, and Stage 3 classification
- 12-month ECL and lifetime ECL
- PD, LGD, and EAD inputs
- Base, upside, and downside macroeconomic scenarios
- Scenario-weighted portfolio ECL
- Stage migration and sensitivity reports

## Suggested Formula

```text
ECL = PD x LGD x EAD x Discount Factor
```

For lifetime ECL, calculate the formula across future periods and sum discounted losses.

## Link to Project 1

Use the PD outputs from `credit-risk-pd-model` as inputs for Stage 1 and Stage 2 accounts.

