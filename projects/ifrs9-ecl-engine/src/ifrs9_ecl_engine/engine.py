from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

ACCOUNT_REQUIRED_COLUMNS = {
    "account_id",
    "days_past_due",
    "sicr",
    "credit_impaired",
    "prior_stage",
    "effective_interest_rate",
    "gross_exposure",
}
TERM_REQUIRED_COLUMNS = {
    "account_id",
    "scenario",
    "month",
    "marginal_pd",
    "lgd",
    "ead",
}


@dataclass(frozen=True)
class StagingPolicy:
    stage2_dpd_backstop: int | None = 30
    stage3_dpd_backstop: int | None = 90

    def __post_init__(self) -> None:
        _validate_policy_threshold("stage2_dpd_backstop", self.stage2_dpd_backstop)
        _validate_policy_threshold("stage3_dpd_backstop", self.stage3_dpd_backstop)
        if (
            self.stage2_dpd_backstop is not None
            and self.stage3_dpd_backstop is not None
            and self.stage2_dpd_backstop >= self.stage3_dpd_backstop
        ):
            raise ValueError("stage2_dpd_backstop must be lower than stage3_dpd_backstop")


@dataclass(frozen=True)
class ECLResult:
    account_ecl: pd.DataFrame
    scenario_ecl: pd.DataFrame
    portfolio_summary: pd.DataFrame
    stage_migration: pd.DataFrame


def run_ecl_engine(
    accounts: pd.DataFrame,
    term_structures: pd.DataFrame,
    scenario_weights: dict[str, float],
    policy: StagingPolicy | None = None,
) -> ECLResult:
    normalized_weights = _validate_scenario_weights(scenario_weights)
    normalized_accounts, normalized_terms = _validate_inputs(
        accounts,
        term_structures,
        normalized_weights,
    )
    active_policy = policy or StagingPolicy()
    staged_accounts = normalized_accounts.copy()
    staged_accounts[["stage", "stage_reason"]] = staged_accounts.apply(
        lambda row: pd.Series(_assign_stage(row, active_policy)),
        axis=1,
    )
    scenario_rows = []
    for account in staged_accounts.to_dict("records"):
        account_terms = normalized_terms[
            normalized_terms["account_id"] == account["account_id"]
        ]
        eir = float(account["effective_interest_rate"])
        months_to_sum = 12 if account["stage"] == 1 else None

        for scenario, weight in normalized_weights.items():
            scenario_terms = account_terms[account_terms["scenario"] == scenario].copy()
            scenario_terms = scenario_terms.sort_values("month")
            if months_to_sum is not None:
                scenario_terms = scenario_terms[scenario_terms["month"] <= months_to_sum]
            losses = scenario_terms.apply(
                lambda row, discount_rate=eir: _discounted_expected_loss(row, discount_rate),
                axis=1,
            )
            scenario_ecl = float(losses.sum())
            scenario_rows.append(
                {
                    "account_id": account["account_id"],
                    "scenario": scenario,
                    "stage": account["stage"],
                    "stage_reason": account["stage_reason"],
                    "ecl_horizon": "12-month" if account["stage"] == 1 else "lifetime",
                    "months_included": len(scenario_terms),
                    "first_month": int(scenario_terms["month"].min()),
                    "last_month": int(scenario_terms["month"].max()),
                    "effective_interest_rate": float(eir),
                    "scenario_weight": float(weight),
                    "scenario_ecl": scenario_ecl,
                    "weighted_scenario_ecl": scenario_ecl * float(weight),
                }
            )

    scenario_ecl = pd.DataFrame(scenario_rows)
    weighted_ecl = (
        scenario_ecl.groupby("account_id", as_index=False)["weighted_scenario_ecl"]
        .sum()
        .rename(columns={"weighted_scenario_ecl": "weighted_ecl"})
    )
    account_ecl = staged_accounts.merge(weighted_ecl, on="account_id")
    account_ecl["coverage_ratio"] = account_ecl.apply(
        lambda row: _coverage_ratio(row["weighted_ecl"], row["gross_exposure"]),
        axis=1,
    )
    account_ecl["sicr"] = account_ecl["sicr"].astype(object)
    account_ecl["credit_impaired"] = account_ecl["credit_impaired"].astype(object)
    account_ecl["defaulted"] = account_ecl["defaulted"].astype(object)
    account_ecl = account_ecl[
        [
            "account_id",
            "days_past_due",
            "sicr",
            "credit_impaired",
            "defaulted",
            "effective_interest_rate",
            "stage",
            "stage_reason",
            "prior_stage",
            "gross_exposure",
            "weighted_ecl",
            "coverage_ratio",
        ]
    ].sort_values("account_id")

    portfolio_summary = _portfolio_summary(account_ecl)
    stage_migration = _stage_migration(account_ecl)
    scenario_ecl = scenario_ecl.sort_values(["account_id", "scenario"]).reset_index(drop=True)

    return ECLResult(
        account_ecl=account_ecl.reset_index(drop=True),
        scenario_ecl=scenario_ecl,
        portfolio_summary=portfolio_summary,
        stage_migration=stage_migration,
    )


def _validate_scenario_weights(scenario_weights: dict[str, float]) -> dict[str, float]:
    if not scenario_weights:
        raise ValueError("Scenario weights must be provided")

    normalized_weights = {}
    total_weight = 0.0
    for scenario, weight in scenario_weights.items():
        if not isinstance(scenario, str) or not scenario.strip():
            raise ValueError("Scenario weights must use non-empty scenario names")
        if scenario != scenario.strip():
            raise ValueError("Scenario names must not contain surrounding whitespace")
        if isinstance(weight, bool):
            raise TypeError(f"Scenario weight for {scenario} must be numeric")
        try:
            numeric_weight = float(weight)
        except TypeError as error:
            raise TypeError(f"Scenario weight for {scenario} must be numeric") from error
        except ValueError as error:
            raise ValueError(f"Scenario weight for {scenario} must be numeric") from error
        if not math.isfinite(numeric_weight):
            raise ValueError(f"Scenario weight for {scenario} must be finite")
        if numeric_weight < 0:
            raise ValueError(f"Scenario weight for {scenario} must be nonnegative")
        normalized_weights[scenario] = numeric_weight
        total_weight += numeric_weight

    if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Scenario weights must sum to 1")
    return normalized_weights


def _validate_policy_threshold(label: str, threshold: int | None) -> None:
    if threshold is None:
        return
    if isinstance(threshold, bool) or not isinstance(threshold, int):
        raise TypeError(f"{label} must be an integer when set")
    if threshold <= 0:
        raise ValueError(f"{label} must be positive when set")


def _validate_inputs(
    accounts: pd.DataFrame,
    term_structures: pd.DataFrame,
    scenario_weights: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _validate_required_columns(accounts, ACCOUNT_REQUIRED_COLUMNS, "accounts")
    _validate_required_columns(term_structures, TERM_REQUIRED_COLUMNS, "term_structures")
    if accounts.empty:
        raise ValueError("accounts must contain at least one row")
    if term_structures.empty:
        raise ValueError("term_structures must contain at least one row")
    _validate_account_columns(accounts)
    _validate_term_columns(term_structures)
    normalized_accounts = _normalize_accounts(accounts)
    normalized_terms = _normalize_term_structures(term_structures)
    _validate_term_coverage(normalized_accounts, normalized_terms, set(scenario_weights))
    return normalized_accounts, normalized_terms


def _validate_required_columns(
    frame: pd.DataFrame,
    required_columns: set[str],
    frame_name: str,
) -> None:
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {', '.join(missing)}")


def _validate_account_columns(accounts: pd.DataFrame) -> None:
    _validate_non_empty_text(accounts["account_id"], "accounts.account_id")

    if accounts["account_id"].duplicated().any():
        raise ValueError("Account IDs must be unique")

    boolean_columns = ["sicr", "credit_impaired"]
    if "defaulted" in accounts.columns:
        boolean_columns.append("defaulted")
    for column in boolean_columns:
        _validate_boolean_column(accounts[column], f"accounts.{column}")

    numeric_columns = [
        "days_past_due",
        "prior_stage",
        "effective_interest_rate",
        "gross_exposure",
    ]
    for column in numeric_columns:
        _validate_finite_numeric(accounts[column], f"accounts.{column}")

    days_past_due = pd.to_numeric(accounts["days_past_due"])
    if ((days_past_due < 0) | (days_past_due % 1 != 0)).any():
        raise ValueError("accounts.days_past_due must be a nonnegative integer")
    prior_stage = pd.to_numeric(accounts["prior_stage"])
    if ((prior_stage % 1 != 0) | (~prior_stage.isin([1, 2, 3]))).any():
        raise ValueError("accounts.prior_stage must be one of 1, 2, or 3")
    if (pd.to_numeric(accounts["effective_interest_rate"]) <= -1).any():
        raise ValueError("accounts.effective_interest_rate must be greater than -1")
    if (pd.to_numeric(accounts["gross_exposure"]) < 0).any():
        raise ValueError("accounts.gross_exposure must be nonnegative")


def _validate_term_columns(term_structures: pd.DataFrame) -> None:
    _validate_non_empty_text(term_structures["account_id"], "term_structures.account_id")
    _validate_non_empty_text(term_structures["scenario"], "term_structures.scenario")

    for column in ["month", "marginal_pd", "lgd", "ead"]:
        _validate_finite_numeric(term_structures[column], f"term_structures.{column}")

    months = pd.to_numeric(term_structures["month"])
    if ((months <= 0) | (months % 1 != 0)).any():
        raise ValueError("term_structures.month must be a positive integer")

    normalized_keys = term_structures[["account_id", "scenario"]].copy()
    normalized_keys["month"] = months
    if normalized_keys.duplicated().any():
        raise ValueError("term_structures must contain one row per account/scenario/month")

    for column in ["marginal_pd", "lgd"]:
        values = pd.to_numeric(term_structures[column])
        if ((values < 0) | (values > 1)).any():
            raise ValueError(f"term_structures.{column} must be between 0 and 1")

    if (pd.to_numeric(term_structures["ead"]) < 0).any():
        raise ValueError("term_structures.ead must be nonnegative")

    cumulative_pd = (
        term_structures.assign(marginal_pd=pd.to_numeric(term_structures["marginal_pd"]))
        .groupby(["account_id", "scenario"])["marginal_pd"]
        .sum()
    )
    if (cumulative_pd > 1).any():
        raise ValueError("Cumulative marginal PD must be less than or equal to 1")


def _validate_finite_numeric(values: pd.Series, label: str) -> None:
    numeric_values = pd.to_numeric(values, errors="coerce")
    if not numeric_values.map(math.isfinite).all():
        raise ValueError(f"{label} must contain finite numeric values")


def _validate_non_empty_text(values: pd.Series, label: str) -> None:
    if (
        values.isna().any()
        or not values.map(lambda value: isinstance(value, str)).all()
        or values.astype(str).str.strip().eq("").any()
    ):
        raise ValueError(f"{label} must contain non-empty values")


def _validate_boolean_column(values: pd.Series, label: str) -> None:
    if not values.map(lambda value: isinstance(value, bool)).all():
        raise ValueError(f"{label} must contain only boolean values")


def _validate_term_coverage(
    accounts: pd.DataFrame,
    term_structures: pd.DataFrame,
    weighted_scenarios: set[str],
) -> None:
    account_ids = set(accounts["account_id"])
    term_account_ids = set(term_structures["account_id"])
    if account_ids - term_account_ids:
        raise ValueError("Term structures must cover every account")
    if term_account_ids - account_ids:
        raise ValueError("Term structures contain account IDs not present in accounts")

    term_scenarios = set(term_structures["scenario"])
    if weighted_scenarios - term_scenarios:
        raise ValueError("Term structures must cover every scenario weight")
    if term_scenarios - weighted_scenarios:
        raise ValueError("Term structures contain scenarios without weights")

    expected_pairs = pd.MultiIndex.from_product(
        [sorted(account_ids), sorted(weighted_scenarios)],
        names=["account_id", "scenario"],
    )
    actual_pairs = pd.MultiIndex.from_frame(term_structures[["account_id", "scenario"]])
    missing_pairs = expected_pairs.difference(actual_pairs)
    if len(missing_pairs) > 0:
        raise ValueError("Term structures must cover every account/scenario pair")

    horizon_counts = term_structures.groupby(["account_id", "scenario"])["month"].max()
    for _, account_horizons in horizon_counts.groupby(level="account_id"):
        if len(set(account_horizons)) > 1:
            raise ValueError("Term structures must have coherent scenario horizons")

    for _, group in term_structures.groupby(["account_id", "scenario"]):
        months = sorted(int(month) for month in group["month"])
        if months != list(range(1, max(months) + 1)):
            raise ValueError("Term structures must contain contiguous monthly terms")


def _assign_stage(account: pd.Series, policy: StagingPolicy) -> tuple[int, str]:
    days_past_due = int(account["days_past_due"])
    if bool(account["credit_impaired"]):
        return 3, "credit_impaired"
    if bool(account["defaulted"]):
        return 3, "defaulted"
    if policy.stage3_dpd_backstop is not None and days_past_due >= policy.stage3_dpd_backstop:
        return 3, f"{policy.stage3_dpd_backstop}_dpd_backstop"
    if bool(account["sicr"]):
        return 2, "sicr_indicator"
    if policy.stage2_dpd_backstop is not None and days_past_due >= policy.stage2_dpd_backstop:
        return 2, f"{policy.stage2_dpd_backstop}_dpd_backstop"
    return 1, "performing"


def _normalize_accounts(accounts: pd.DataFrame) -> pd.DataFrame:
    normalized = accounts.copy()
    normalized["days_past_due"] = pd.to_numeric(normalized["days_past_due"]).astype(int)
    normalized["prior_stage"] = pd.to_numeric(normalized["prior_stage"]).astype(int)
    for column in ["effective_interest_rate", "gross_exposure"]:
        normalized[column] = pd.to_numeric(normalized[column]).astype(float)
    if "defaulted" not in normalized.columns:
        normalized["defaulted"] = False
    return normalized


def _normalize_term_structures(term_structures: pd.DataFrame) -> pd.DataFrame:
    normalized = term_structures.copy()
    normalized["month"] = pd.to_numeric(normalized["month"]).astype(int)
    for column in ["marginal_pd", "lgd", "ead"]:
        normalized[column] = pd.to_numeric(normalized[column]).astype(float)
    return normalized


def _discounted_expected_loss(term: pd.Series, effective_interest_rate: float) -> float:
    return float(
        term["marginal_pd"]
        * term["lgd"]
        * term["ead"]
        / ((1 + effective_interest_rate) ** (term["month"] / 12))
    )


def _portfolio_summary(account_ecl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stage, group in account_ecl.groupby("stage"):
        gross_exposure = float(group["gross_exposure"].sum())
        weighted_ecl = float(group["weighted_ecl"].sum())
        rows.append(
            {
                "stage": int(stage),
                "account_count": len(group),
                "gross_exposure": gross_exposure,
                "weighted_ecl": weighted_ecl,
                "coverage_ratio": _coverage_ratio(weighted_ecl, gross_exposure),
            }
        )
    total_exposure = float(account_ecl["gross_exposure"].sum())
    total_ecl = float(account_ecl["weighted_ecl"].sum())
    rows.append(
        {
            "stage": "Total",
            "account_count": len(account_ecl),
            "gross_exposure": total_exposure,
            "weighted_ecl": total_ecl,
            "coverage_ratio": _coverage_ratio(total_ecl, total_exposure),
        }
    )
    return pd.DataFrame(rows)


def _coverage_ratio(weighted_ecl: float, gross_exposure: float) -> float:
    if gross_exposure == 0:
        return 0.0
    return float(weighted_ecl) / float(gross_exposure)


def _stage_migration(account_ecl: pd.DataFrame) -> pd.DataFrame:
    return (
        account_ecl.groupby(["prior_stage", "stage"], as_index=False)
        .agg(
            account_count=("account_id", "count"),
            gross_exposure=("gross_exposure", "sum"),
            weighted_ecl=("weighted_ecl", "sum"),
        )
        .sort_values(["prior_stage", "stage"])
        .reset_index(drop=True)
    )
