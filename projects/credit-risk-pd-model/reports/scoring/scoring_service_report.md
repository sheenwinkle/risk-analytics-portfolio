# Governed PD Scoring Service

## Deployment Reconciliation

- Model version: `synthetic-pd-v1`.
- Selected estimator: `logistic_regression`.
- Policy decision: `retain_incumbent`.
- Data context: `synthetic_demo`.
- Active maximum-PD cutoff: 15.00%.
- Frozen OOT records replayed: 994.
- Governed scoring batches executed: 1.
- Maximum offline-versus-service PD delta at 12 decimal places: 0.00e+00.
- Replay reconciled at 1e-12: **True**.
- Artifact integrity verified: **True**.

## Score Distribution

| Risk band | Records | Share | Mean PD |
| --- | ---: | ---: | ---: |
| low | 593 | 59.66% | 6.25% |
| moderate | 248 | 24.95% | 12.07% |
| high | 136 | 13.68% | 18.02% |
| very_high | 17 | 1.71% | 28.48% |

## Input Monitoring

- Missing input cells accepted by the fitted preprocessing contract: 0.
- Unseen categorical values handled and flagged: 0.
- Records within the governed cutoff: 841.

## Governance Boundary

The API returns rule-based policy input flags for monitoring. They are not local model attribution, adverse-action reasons, or an automated credit approval. Authentication, authorization, durable logging, model registry signatures, and production infrastructure remain outside this portfolio reference implementation.

Only aggregate replay evidence is committed. Application identifiers, row-level scores, the model binary, and the artifact digest remain local.
