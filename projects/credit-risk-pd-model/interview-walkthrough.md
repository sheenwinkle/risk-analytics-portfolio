# Credit Risk PD Interview Walkthrough

## 5-minute walkthrough

Use this when an interviewer says: "Tell me about one project on your GitHub."

### 30-second pitch

I built a credit risk PD modelling project that goes beyond a notebook. It covers
time-aware data preparation, baseline and challenger model development, calibration,
OOT validation, champion-challenger strategy backtesting, governed batch scoring, and
privacy-safe aggregate reports.

The point is to show that I can connect Economics + CS + FRM knowledge: not just train
a classifier, but turn it into a risk analytics workflow that a credit or model-risk
team can review.

### Live demo path

Open these files in order:

1. `case-study.md`
   - Start with the business framing and quantified impact.
2. `reports/public_lendingclub/model_report.md`
   - Show model selection, calibration, OOT metrics, and strategy decision.
3. `reports/public_lendingclub/scoring_service_report.md`
   - Show governed scoring replay across 225,639 public OOT applications and
     226 batches.
4. `src/credit_risk_pd/serving.py`
   - Show the governed scoring contract, artifact integrity checks, batch validation,
     derived features, risk bands, and audit outputs.
5. `tests/test_serving.py` and `tests/test_case_study.py`
   - Show that the service and interview evidence are self-tested.

### What I personally built

I personally built the end-to-end workflow:

- Data checks, temporal split, origination-time features, and leakage controls.
- Logistic regression baseline and random-forest challenger comparison.
- Recalibration using a pre-OOT holdout.
- OOT metrics covering ROC-AUC, Gini, KS, Brier score, calibration, PSI, WOE/IV, and
  feature importance.
- A retrospective champion-challenger backtest for lending cutoff strategy.
- A governed scoring contract with artifact integrity checks and deterministic replay.
- Publication controls that keep only privacy-safe aggregate reports in GitHub.

### How I quantified impact

I quantified impact by comparing a frozen incumbent cutoff with a controlled challenger
cutoff on the same OOT accepted-loan sample.

The public LendingClub evidence shows:

| Metric | Result |
| --- | ---: |
| OOT scoring sample | 225,639 public OOT applications |
| Governed scoring replay | 226 batches |
| Incremental approvals | 35,876 incremental approvals |
| Realised contribution proxy | USD 17.0m |

The strongest technical proof is that the project does not stop at AUC. It connects
model quality, calibration, policy cutoff impact, uncertainty, scoring controls, and
publication governance.

### What I would say if challenged

If asked whether this proves a real business uplift:

> No. This is not a randomized A/B test. It is a retrospective champion-challenger
> backtest on an accepted-loan sample. The result quantifies historical marginal-cohort
> impact under simplified assumptions, but it does not prove causal production uplift.

If asked how I would turn it into a real test:

> I would run a controlled challenger rollout on eligible applications, randomize
> treatment assignment, freeze guardrails before launch, monitor approval rate,
> delinquency, expected loss, realised loss, complaints, and adverse-action outcomes,
> then stop or roll back if guardrails breach.

If asked why I used a random forest:

> I used logistic regression as the interpretable baseline and random forest as a
> non-linear challenger. The final decision is not "random forest is always better";
> the model is selected, recalibrated, validated out of time, and wrapped in governance
> controls.

If asked about explainability:

> The service-level flags are deliberately named
> `policy_input_flags_not_model_attribution`. They are input risk indicators for
> operational review, not SHAP values, adverse-action reasons, or legal decline
> explanations.

### Known limitation

The key known limitation is that LendingClub contains accepted loans, not all original
applications. That means rejected-application behavior is unobserved. The project treats
the result as a public-data risk analytics case study, not a production underwriting
model.

Other limitations:

- The target is a terminal outcome proxy, not a formal Basel or IFRS 9 fixed-horizon PD.
- The contribution proxy excludes funding cost, operating cost, prepayment, collections
  timing, and capital usage.
- The scoring service is a local reference service, not a full production platform with
  authentication, authorization, rate limits, signed registry, durable audit storage, or
  PII controls.

### Closing line

The project is useful because it is evidence-backed. A reviewer can see the modelling
logic, the governed scoring contract, the privacy-safe aggregate reports, and the tests
that keep the numbers and claims aligned.
