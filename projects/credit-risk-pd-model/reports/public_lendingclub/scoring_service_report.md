# Governed PD Scoring Service

## Deployment Reconciliation

- Model version: `lendingclub-public-pd-v1`.
- Selected estimator: `random_forest`.
- Policy decision: `advance_challenger`.
- Data context: `public_lendingclub`.
- Active maximum-PD cutoff: 20.00%.
- Frozen OOT records replayed: 225,639.
- Governed scoring batches executed: 226.
- Maximum offline-versus-service PD delta at 12 decimal places: 0.00e+00.
- Replay reconciled at 1e-12: **True**.
- Artifact integrity verified: **True**.

## Score Distribution

| Risk band | Records | Share | Mean PD |
| --- | ---: | ---: | ---: |
| low | 31344 | 13.89% | 6.91% |
| moderate | 34476 | 15.28% | 12.58% |
| high | 66755 | 29.58% | 19.76% |
| very_high | 93064 | 41.24% | 36.84% |

## Input Monitoring

- Missing input cells accepted by the fitted preprocessing contract: 243,257.
- Unseen categorical values handled and flagged: 0.
- Records within the governed cutoff: 101,696.

## Governance Boundary

The API returns rule-based policy input flags for monitoring. They are not local model attribution, adverse-action reasons, or an automated credit approval. Authentication, authorization, durable logging, model registry signatures, and production infrastructure remain outside this portfolio reference implementation.

Only aggregate replay evidence is committed. Application identifiers, row-level scores, the model binary, and the artifact digest remain local.
