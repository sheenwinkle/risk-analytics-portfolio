# APRA Alignment Matrix

This repository is an APRA-aligned portfolio artifact, not an APRA-compliant production framework.
It is also not APRA-approved, not an IRB capital model, not a production underwriting platform,
and not an audited IFRS 9 provisioning system.

The purpose of this matrix is to keep the job-search framing accurate: the tools,
frameworks, controls, and evidence are organised around APRA-style risk management
expectations, while the compliance boundary remains explicit.

## resume-safe wording

Use this wording in a resume, cover letter, or interview:

> Built an APRA-aligned credit risk analytics portfolio demonstrating PD model
> development, IFRS 9-style ECL, independent model validation, governance evidence,
> monitoring, and controlled challenger evaluation using public and synthetic data;
> designed as an educational portfolio framework rather than an APRA-approved
> production, regulatory capital, or underwriting system.

Avoid:

- "APRA-compliant model"
- "APRA-approved IRB framework"
- "Production-ready APRA credit risk system"
- "Regulatory capital model"
- "Causal A/B uplift"

## Alignment legend

| Status | Meaning |
| --- | --- |
| Implemented | The portfolio contains a runnable artifact, report, test, or evidence file that demonstrates the control concept. |
| Partially aligned | The portfolio demonstrates the idea but lacks institutional scope, production controls, formal approvals, or real bank data. |
| Not in scope | The requirement needs an APRA-regulated entity, board/senior-management process, production platform, internal data, audit function, or APRA approval. |

## Standards map

| APRA source | Portfolio interpretation | Status | Evidence |
| --- | --- | --- | --- |
| APS 220 Credit Risk Management | Credit risk appetite and strategy, credit policies, origination controls, monitoring, reporting, problem-exposure awareness, provisions, and internal controls. | Partially aligned | Project 1 includes PD modelling, temporal validation, risk bands, cutoff strategy, monitoring, PSI, WOE/IV, governed scoring, and public aggregate evidence. Project 2 links PD outputs into ECL-style provisioning analytics. |
| APG 220 Credit Risk Management | Good-practice framing for credit risk lifecycle management, portfolio risk limits, monitoring, stress awareness, and independent review. | Partially aligned | The portfolio has lifecycle documentation, public-data limitations, strategy guardrails, macro sensitivity, and validation reports, but no ADI risk appetite statement or board-approved policy framework. |
| APS 113 Internal Ratings-based Approach | Rating-system development, validation, and monitoring, including meaningful risk differentiation, quantitative estimates, governance, change logs, issue registers, and independent review. | Partially aligned | Project 1 develops and recalibrates PD estimates; Project 3 independently reperforms validation, records findings, and keeps a finding lifecycle. It is not an APRA-approved IRB system and does not calculate regulatory capital. |
| CPS 220 Risk Management | Enterprise risk management framework, risk appetite, material risk identification, controls, monitoring, management information, and review. | Partially aligned | The repository connects PD, ECL, validation, remediation, monitoring, and PostgreSQL evidence across projects. It lacks board governance, formal risk appetite, senior-management ownership, and institution-wide risk coverage. |
| CPS 230 Operational Risk Management | Operational resilience and business continuity, critical operations, tolerance levels, service provider management, incident response, and operational risk reporting. | Not in scope | The local scoring API demonstrates a governed scoring contract and deterministic replay, but it does not implement production BCP, critical-operation tolerances, service provider controls, incident reporting, or operational resilience testing. |
| CPS 234 Information Security | Information security and PII controls, information asset classification, access restriction, control testing, incident response, and independent assurance. | Not in scope | Public reports are privacy-safe aggregate reports and borrower-level files are excluded from GitHub. The local service does not implement authentication, authorisation, key management, data-loss prevention, formal asset classification, incident notification, or independent security assurance. |

## Implemented controls in this portfolio

- Time-aware credit risk model development with development, calibration, and OOT
  samples.
- Model comparison covering interpretable baseline and non-linear challenger.
- Calibration testing and recalibration before untouched OOT assessment.
- Champion-challenger cutoff strategy with pre-OOT selection and frozen OOT
  measurement.
- Explicit non-causal A/B boundary for retrospective accepted-loan backtests.
- PSI, WOE/IV, feature importance, vintage maturity, and public-data limitation
  reporting.
- IFRS 9-style ECL engine with staging, PD/LGD/EAD term structures, scenario
  weights, SICR rebuttal, overlays, and cash-flow sensitivity.
- APRA/RBA macro-credit satellite with an explicit APS 220 reporting-basis break
  boundary.
- Independent validation framework with validation summaries, findings, benchmark
  comparisons, remediation retests, and lifecycle evidence.
- PostgreSQL-backed governance evidence for model runs, validation outputs,
  findings, limitations, benchmarks, and remediation events.
- Governed scoring API with schema validation, model artifact integrity checking,
  contract hashing, risk bands, cutoff outcomes, and batch data-quality audit.
- Privacy-safe aggregate publication controls that exclude borrower-level
  predictions and application identifiers from public GitHub evidence.

## Partially aligned areas

- Credit risk appetite is represented through project-level cutoff constraints and
  strategy checks, not a board-approved institutional risk appetite statement.
- Model governance is represented through manifests, validation reports, tests, and
  issue lifecycle evidence, not a formal model risk policy or model committee.
- ECL is represented as an educational IFRS 9-style analytical engine, not an
  audited provisioning process under Australian Accounting Standards.
- Macro stress and overlay logic are illustrative and restricted-use where evidence
  is weak; they are not approved forecasting models.
- Independent validation is simulated through a separate validation project and
  reproducible tests, not an internal audit or APRA-appointed independent review.

## Not in scope for this GitHub portfolio

- APRA approval to use internal ratings for regulatory capital.
- Board or senior-management approval of risk appetite, policy, model use, or
  remediation plans.
- Full ADI credit lifecycle coverage across all products, geographies, limits,
  exceptions, collections, hardship, collateral, provisioning, and capital.
- Real rejected-application data, internal bank defaults, collections, recoveries,
  LGD, EAD, collateral, or customer-level servicing history.
- Regulatory capital calculation, risk-weighted assets, expected loss under APS 113,
  or formal IRB use-test evidence.
- Production authentication, authorisation, encryption, key management, monitoring,
  incident response, disaster recovery, service provider risk management, and
  business continuity testing.

## Interview boundary

If asked whether the project follows APRA:

> I would not describe it as APRA-compliant because this is a public GitHub
> portfolio, not an APRA-regulated institution. I would describe it as APRA-aligned:
> the project uses APRA-style control concepts such as risk appetite constraints,
> lifecycle monitoring, independent validation, finding tracking, model governance,
> stress/sensitivity analysis, and privacy-safe evidence, while clearly labelling
> production, capital, security, and board-governance requirements as out of scope.

## Official APRA references

- [APS 220 Credit Risk Management](https://www.apra.gov.au/standards/aps-220)
- [APG 220 Credit Risk Management](https://www.apra.gov.au/practice-guides/apg-220)
- [APS 113 Capital Adequacy: Internal Ratings-based Approach to Credit Risk](https://www.apra.gov.au/standards/aps-113)
- [CPS 220 Risk Management](https://www.apra.gov.au/standards/cps-220)
- [CPS 230 Operational Risk Management](https://www.apra.gov.au/standards/cps-230)
- [CPS 234 Information Security](https://www.apra.gov.au/standards/cps-234)
