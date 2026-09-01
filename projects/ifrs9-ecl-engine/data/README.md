# Project 2 Data

No raw, private, borrower-level, or institution data is committed for this project.

The runnable demo uses deterministic synthetic account snapshots and synthetic monthly
PD/LGD/EAD term structures generated in `src/ifrs9_ecl_engine/demo.py`.

Reporting-date gross exposure is stored in the synthetic account snapshot. Forward EAD
paths are generated separately for each scenario and month.

Synthetic account identifiers must begin with `SYN-ECL-`.

Any real or public-data experiment should remain local unless it has been reviewed and
intentionally anonymised, aggregated, and documented before being added to Git.
