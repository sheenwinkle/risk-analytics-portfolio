from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ifrs9_ecl_engine.engine import ECLResult, run_ecl_engine

PD_REQUIRED_COLUMNS = {"customer_id", "observation_date", "recalibrated_pd"}
ASSUMPTION_REQUIRED_COLUMNS = {
    "customer_id",
    "account_id",
    "gross_exposure",
    "lgd",
    "remaining_maturity_months",
    "effective_interest_rate",
    "days_past_due",
    "sicr",
    "credit_impaired",
    "defaulted",
    "prior_stage",
}
ACCOUNT_COLUMNS = [
    "account_id",
    "days_past_due",
    "sicr",
    "credit_impaired",
    "defaulted",
    "prior_stage",
    "effective_interest_rate",
    "gross_exposure",
]


@dataclass(frozen=True)
class PDScenarioAssumption:
    name: str
    weight: float
    hazard_multiplier: float
    lgd_addon: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Scenario names must be non-empty strings")
        if self.name != self.name.strip():
            raise ValueError(f"Scenario name {self.name!r} must not contain surrounding whitespace")
        weight = _validate_finite_number(self.weight, f"Scenario weight for {self.name}")
        hazard_multiplier = _validate_finite_number(
            self.hazard_multiplier,
            f"Scenario hazard multiplier for {self.name}",
        )
        lgd_addon = _validate_finite_number(self.lgd_addon, f"Scenario LGD add-on for {self.name}")
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "hazard_multiplier", hazard_multiplier)
        object.__setattr__(self, "lgd_addon", lgd_addon)
        if self.weight < 0:
            raise ValueError(f"Scenario weight for {self.name} must be nonnegative")
        if self.hazard_multiplier <= 0:
            raise ValueError(f"Scenario hazard multiplier for {self.name} must be positive")


@dataclass(frozen=True)
class PDIntegrationConfig:
    scenarios: tuple[PDScenarioAssumption, ...] = field(
        default_factory=lambda: (
            PDScenarioAssumption("upside", 0.15, 0.75, -0.03),
            PDScenarioAssumption("base", 0.60, 1.00, 0.00),
            PDScenarioAssumption("downside", 0.25, 1.65, 0.08),
        )
    )
    ead_method: str = "fully_amortising_straight_line"

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
        if not self.scenarios:
            raise ValueError("At least one PD integration scenario must be configured")
        if not all(isinstance(scenario, PDScenarioAssumption) for scenario in self.scenarios):
            raise TypeError("scenarios must contain only PDScenarioAssumption values")
        scenario_names = [scenario.name for scenario in self.scenarios]
        duplicate_names = _duplicates(scenario_names)
        if duplicate_names:
            raise ValueError(f"Scenario names must be unique: {', '.join(duplicate_names)}")
        total_weight = sum(float(scenario.weight) for scenario in self.scenarios)
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("Scenario weights must sum to 1")
        _validate_scenario_ordering(self.scenarios)
        if self.ead_method != "fully_amortising_straight_line":
            raise ValueError("ead_method must be fully_amortising_straight_line")


@dataclass(frozen=True)
class PDBridgeInputs:
    accounts: pd.DataFrame
    term_structures: pd.DataFrame
    scenario_weights: dict[str, float]
    scenario_assumptions: pd.DataFrame
    input_audit: pd.DataFrame
    reporting_date: str


@dataclass(frozen=True)
class PDIntegrationPipelineOutput:
    bridge_inputs: PDBridgeInputs
    result: ECLResult
    report_paths: dict[str, Path]


def read_pd_predictions(path: str | Path) -> pd.DataFrame:
    prediction_path = Path(path)
    if not prediction_path.is_file():
        raise FileNotFoundError(
            f"PD prediction file not found or is not a file: {prediction_path}"
        )
    return pd.read_csv(prediction_path)


def select_pd_reporting_cohort(
    predictions: pd.DataFrame,
    reporting_date: str | None = None,
) -> pd.DataFrame:
    _validate_required_columns(predictions, PD_REQUIRED_COLUMNS, "predictions")
    _validate_not_empty(predictions, "predictions")
    normalized = predictions.loc[:, ["customer_id", "observation_date", "recalibrated_pd"]].copy()
    _validate_non_empty_text(normalized["customer_id"], "predictions.customer_id")
    normalized["observation_date"] = _parse_dates(
        normalized["observation_date"],
        "predictions.observation_date",
    )
    _validate_pd_values(normalized["recalibrated_pd"], "predictions.recalibrated_pd")
    normalized["recalibrated_pd"] = pd.to_numeric(normalized["recalibrated_pd"]).astype(float)

    if reporting_date is None:
        selected_date = normalized["observation_date"].max()
    else:
        try:
            selected_date = pd.Timestamp(reporting_date)
        except (TypeError, ValueError) as error:
            raise ValueError(f"reporting_date must be a valid date: {reporting_date}") from error
        if pd.isna(selected_date):
            raise ValueError(f"reporting_date must be a valid date: {reporting_date}")
        selected_date = selected_date.normalize()

    cohort = normalized[normalized["observation_date"] == selected_date].copy()
    if cohort.empty:
        available = sorted(date.strftime("%Y-%m-%d") for date in normalized["observation_date"].unique())
        raise ValueError(
            f"Reporting date {selected_date.strftime('%Y-%m-%d')} is absent from PD predictions; "
            f"available dates: {', '.join(available)}"
        )
    if cohort["customer_id"].duplicated().any():
        duplicate_ids = _duplicates(cohort["customer_id"])
        raise ValueError(
            "PD reporting cohort must contain one row per customer_id; duplicates: "
            + ", ".join(duplicate_ids)
        )

    cohort["observation_date"] = cohort["observation_date"].dt.strftime("%Y-%m-%d")
    return cohort.sort_values("customer_id").reset_index(drop=True)


def build_ecl_inputs_from_pd_snapshot(
    pd_snapshot: pd.DataFrame,
    account_assumptions: pd.DataFrame,
    config: PDIntegrationConfig | None = None,
) -> PDBridgeInputs:
    active_config = config or PDIntegrationConfig()
    snapshot = _normalize_pd_snapshot(pd_snapshot)
    assumptions = _normalize_account_assumptions(account_assumptions)
    _validate_one_to_one_bridge(snapshot, assumptions)
    joined = snapshot.merge(assumptions, on="customer_id", how="inner", validate="one_to_one")
    joined = joined.sort_values("account_id").reset_index(drop=True)
    _validate_scenario_lgd(joined, active_config.scenarios)

    accounts = joined.loc[:, ACCOUNT_COLUMNS].copy()
    term_structures = _build_term_structures(joined, active_config.scenarios)
    scenario_weights = {scenario.name: float(scenario.weight) for scenario in active_config.scenarios}
    scenario_assumptions = pd.DataFrame(
        [
            {
                "scenario": scenario.name,
                "scenario_weight": scenario.weight,
                "hazard_multiplier": scenario.hazard_multiplier,
                "lgd_addon": scenario.lgd_addon,
            }
            for scenario in active_config.scenarios
        ]
    ).sort_values("scenario").reset_index(drop=True)
    input_audit = _build_input_audit(joined, active_config)

    return PDBridgeInputs(
        accounts=accounts.reset_index(drop=True),
        term_structures=term_structures,
        scenario_weights=scenario_weights,
        scenario_assumptions=scenario_assumptions,
        input_audit=input_audit,
        reporting_date=str(joined["observation_date"].iloc[0]),
    )


def run_pd_ecl_integration(
    pd_snapshot: pd.DataFrame,
    account_assumptions: pd.DataFrame,
    config: PDIntegrationConfig | None = None,
) -> tuple[PDBridgeInputs, ECLResult]:
    bridge_inputs = build_ecl_inputs_from_pd_snapshot(pd_snapshot, account_assumptions, config)
    result = run_ecl_engine(
        bridge_inputs.accounts,
        bridge_inputs.term_structures,
        bridge_inputs.scenario_weights,
    )
    return bridge_inputs, result


def run_pd_integration_pipeline(
    prediction_path: str | Path,
    reporting_date: str | None = None,
    sample_size: int = 8,
    output_dir: str | Path = "reports/pd_integration",
    config: PDIntegrationConfig | None = None,
) -> PDIntegrationPipelineOutput:
    predictions = read_pd_predictions(prediction_path)
    cohort = select_pd_reporting_cohort(predictions, reporting_date=reporting_date)
    sampled_cohort = select_evenly_spaced_pd_sample(cohort, sample_size)
    assumptions = build_synthetic_account_assumptions(sampled_cohort)
    bridge_inputs, result = run_pd_ecl_integration(sampled_cohort, assumptions, config=config)
    report_paths = write_pd_integration_reports(bridge_inputs, result, Path(output_dir))
    return PDIntegrationPipelineOutput(
        bridge_inputs=bridge_inputs,
        result=result,
        report_paths=report_paths,
    )


def select_evenly_spaced_pd_sample(cohort: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    if isinstance(sample_size, bool) or not isinstance(sample_size, int):
        raise TypeError("sample_size must be an integer")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    normalized = _normalize_pd_snapshot(cohort)
    if sample_size > len(normalized):
        raise ValueError(
            f"sample_size {sample_size} exceeds selected cohort size {len(normalized)}"
        )
    sorted_cohort = normalized.sort_values(["recalibrated_pd", "customer_id"]).reset_index(drop=True)
    if sample_size == 1:
        positions = [len(sorted_cohort) // 2]
    else:
        positions = [
            round(index * (len(sorted_cohort) - 1) / (sample_size - 1))
            for index in range(sample_size)
        ]
    return sorted_cohort.iloc[positions].reset_index(drop=True)


def build_synthetic_account_assumptions(pd_sample: pd.DataFrame) -> pd.DataFrame:
    normalized = _normalize_pd_snapshot(pd_sample)
    rows = []
    dpd_pattern = [0, 12, 28, 35, 61, 95, 5, 45]
    sicr_pattern = [False, False, False, True, True, True, False, True]
    credit_impaired_pattern = [False, False, False, False, False, True, False, False]
    defaulted_pattern = [False, False, False, False, False, True, False, False]
    prior_stage_pattern = [1, 1, 1, 1, 2, 2, 1, 2]
    maturity_pattern = [18, 24, 30, 36, 42, 48, 54, 60]
    for index, row in enumerate(normalized.sort_values(["recalibrated_pd", "customer_id"]).to_dict("records")):
        pattern_index = index % len(dpd_pattern)
        rows.append(
            {
                "customer_id": row["customer_id"],
                "account_id": f"SYN-PD-ECL-{index + 1:03d}",
                "gross_exposure": float(45_000 + index * 12_500),
                "lgd": min(0.62, 0.32 + index * 0.025),
                "remaining_maturity_months": maturity_pattern[pattern_index],
                "effective_interest_rate": 0.075 + index * 0.004,
                "days_past_due": dpd_pattern[pattern_index],
                "sicr": sicr_pattern[pattern_index],
                "credit_impaired": credit_impaired_pattern[pattern_index],
                "defaulted": defaulted_pattern[pattern_index],
                "prior_stage": prior_stage_pattern[pattern_index],
            }
        )
    return pd.DataFrame(rows)


def write_pd_integration_reports(
    bridge_inputs: PDBridgeInputs,
    result: ECLResult,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    account_ecl = result.account_ecl.merge(
        bridge_inputs.input_audit[
            [
                "customer_id",
                "account_id",
                "observation_date",
                "recalibrated_pd",
                "annual_hazard",
                "lgd",
                "remaining_maturity_months",
                "ead_method",
                "assumption_basis",
            ]
        ],
        on="account_id",
        how="left",
        validate="one_to_one",
    )
    ordered_account_columns = [
        "customer_id",
        "account_id",
        "observation_date",
        "recalibrated_pd",
        "annual_hazard",
        "days_past_due",
        "sicr",
        "credit_impaired",
        "defaulted",
        "effective_interest_rate",
        "lgd",
        "remaining_maturity_months",
        "stage",
        "stage_reason",
        "prior_stage",
        "gross_exposure",
        "weighted_ecl",
        "coverage_ratio",
        "ead_method",
        "assumption_basis",
    ]
    account_ecl = account_ecl.loc[:, ordered_account_columns].sort_values("account_id")
    scenario_ecl = result.scenario_ecl.merge(
        bridge_inputs.input_audit[["account_id", "customer_id", "recalibrated_pd"]],
        on="account_id",
        how="left",
        validate="many_to_one",
    )
    scenario_ecl = scenario_ecl.merge(
        bridge_inputs.scenario_assumptions[
            ["scenario", "hazard_multiplier", "lgd_addon"]
        ],
        on="scenario",
        how="left",
        validate="many_to_one",
    )
    scenario_columns = [
        "customer_id",
        "account_id",
        "recalibrated_pd",
        "scenario",
        "stage",
        "stage_reason",
        "ecl_horizon",
        "months_included",
        "first_month",
        "last_month",
        "effective_interest_rate",
        "scenario_weight",
        "hazard_multiplier",
        "lgd_addon",
        "scenario_ecl",
        "weighted_scenario_ecl",
    ]
    scenario_ecl = scenario_ecl.loc[:, scenario_columns].sort_values(["account_id", "scenario"])
    outputs = {
        "input_audit": output_dir / "input_audit.csv",
        "account_ecl": output_dir / "account_ecl.csv",
        "scenario_ecl": output_dir / "scenario_ecl.csv",
        "portfolio_summary": output_dir / "portfolio_summary.csv",
        "stage_migration": output_dir / "stage_migration.csv",
    }
    bridge_inputs.input_audit.to_csv(
        outputs["input_audit"],
        index=False,
        float_format="%.10f",
        lineterminator="\n",
    )
    account_ecl.to_csv(
        outputs["account_ecl"],
        index=False,
        float_format="%.10f",
        lineterminator="\n",
    )
    scenario_ecl.to_csv(
        outputs["scenario_ecl"],
        index=False,
        float_format="%.10f",
        lineterminator="\n",
    )
    result.portfolio_summary.to_csv(
        outputs["portfolio_summary"],
        index=False,
        float_format="%.10f",
        lineterminator="\n",
    )
    result.stage_migration.to_csv(
        outputs["stage_migration"],
        index=False,
        float_format="%.10f",
        lineterminator="\n",
    )
    report_path = output_dir / "pd_integration_report.md"
    report_path.write_text(
        _pd_integration_markdown_report(bridge_inputs, result, scenario_ecl),
        encoding="utf-8",
        newline="\n",
    )
    return {**outputs, "pd_integration_report": report_path}


def _normalize_pd_snapshot(pd_snapshot: pd.DataFrame) -> pd.DataFrame:
    _validate_required_columns(pd_snapshot, PD_REQUIRED_COLUMNS, "pd_snapshot")
    _validate_not_empty(pd_snapshot, "pd_snapshot")
    normalized = pd_snapshot.loc[:, ["customer_id", "observation_date", "recalibrated_pd"]].copy()
    _validate_non_empty_text(normalized["customer_id"], "pd_snapshot.customer_id")
    normalized["observation_date"] = _parse_dates(
        normalized["observation_date"],
        "pd_snapshot.observation_date",
    )
    if normalized["observation_date"].nunique() != 1:
        raise ValueError("pd_snapshot must contain exactly one observation_date cohort")
    _validate_pd_values(normalized["recalibrated_pd"], "pd_snapshot.recalibrated_pd")
    normalized["recalibrated_pd"] = pd.to_numeric(normalized["recalibrated_pd"]).astype(float)
    if normalized["customer_id"].duplicated().any():
        duplicate_ids = _duplicates(normalized["customer_id"])
        raise ValueError(
            "pd_snapshot must contain one row per customer_id; duplicates: "
            + ", ".join(duplicate_ids)
        )
    normalized["observation_date"] = normalized["observation_date"].dt.strftime("%Y-%m-%d")
    return normalized


def _pd_integration_markdown_report(
    bridge_inputs: PDBridgeInputs,
    result: ECLResult,
    scenario_ecl: pd.DataFrame,
) -> str:
    total = result.portfolio_summary[result.portfolio_summary["stage"] == "Total"].iloc[0]
    scenario_summary = (
        scenario_ecl.groupby("scenario", as_index=False)
        .agg(
            scenario_weight=("scenario_weight", "first"),
            hazard_multiplier=("hazard_multiplier", "first"),
            lgd_addon=("lgd_addon", "first"),
            scenario_ecl=("scenario_ecl", "sum"),
            weighted_scenario_ecl=("weighted_scenario_ecl", "sum"),
        )
        .sort_values("scenario")
    )
    min_pd = bridge_inputs.input_audit["recalibrated_pd"].min()
    max_pd = bridge_inputs.input_audit["recalibrated_pd"].max()
    return "\n".join(
        [
            "# Project 1 PD to Project 2 ECL Bridge",
            "",
            (
                "This deterministic report connects committed Project 1 synthetic out-of-time "
                "recalibrated PD outputs to the Project 2 educational ECL engine."
            ),
            "",
            "## Lineage",
            "",
            f"- Reporting date: {bridge_inputs.reporting_date}",
            f"- Account count: {len(bridge_inputs.accounts)}",
            f"- Recalibrated 12-month PD range: {min_pd:.4%} to {max_pd:.4%}",
            (
                "- Source columns used by the bridge: `customer_id`, `observation_date`, "
                "and `recalibrated_pd` only."
            ),
            (
                "- `actual_default` and other future outcome fields are not used in ECL input "
                "construction."
            ),
            "",
            "## Methodology",
            "",
            (
                "Project 1's synthetic target is a terminal-outcome proxy. The bridge treats "
                "`recalibrated_pd` as a 12-month cumulative PD, converts it to a constant "
                "annual hazard `h = -log(1 - p)`, applies explicit scenario hazard "
                "multipliers, and derives monthly marginal PD from conditional monthly "
                "`q = 1 - exp(-h_scenario / 12)` and survival to the previous month."
            ),
            "",
            (
                "The lifetime extrapolation uses that constant-hazard assumption for "
                "education and interview discussion. It is not an IFRS 9 compliance claim."
            ),
            "",
            "## Account Assumptions",
            "",
            (
                "EAD, LGD, remaining maturity, EIR, DPD, SICR, credit-impaired/defaulted "
                "flags, and prior stage are explicit synthetic assumptions. They are "
                "illustrative and independent of Project 1 outcomes."
            ),
            "",
            (
                "Reporting-date gross exposure is kept independent from forward EAD paths. "
                "The forward EAD path is a transparent straight-line fully amortising proxy: "
                "month 1 starts at reporting-date gross exposure and declines to one final "
                "monthly instalment by maturity. No detailed contractual cash-flow model is "
                "claimed."
            ),
            "",
            "## Portfolio Summary",
            "",
            f"- Gross exposure: {total['gross_exposure']:,.2f}",
            f"- Probability-weighted ECL: {total['weighted_ecl']:,.2f}",
            f"- Coverage ratio: {total['coverage_ratio']:.4%}",
            "",
            "## Stage Summary",
            "",
            _format_markdown_table(result.portfolio_summary),
            "",
            "## Scenario Contribution",
            "",
            _format_markdown_table(scenario_summary),
            "",
            "## Stage Migration",
            "",
            _format_markdown_table(result.stage_migration),
            "",
            "## Limitation",
            "",
            (
                "This is a synthetic educational bridge between portfolio projects, not a "
                "production ECL model, not accounting advice, and not evidence of IFRS 9 "
                "compliance."
            ),
            "",
        ]
    )


def _format_markdown_table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    rows = ["| " + " | ".join(headers) + " |"]
    rows.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in frame.to_dict("records"):
        rows.append("| " + " | ".join(_format_cell(row[column]) for column in headers) + " |")
    return "\n".join(rows)


def _format_cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _normalize_account_assumptions(account_assumptions: pd.DataFrame) -> pd.DataFrame:
    _validate_required_columns(account_assumptions, ASSUMPTION_REQUIRED_COLUMNS, "account_assumptions")
    _validate_not_empty(account_assumptions, "account_assumptions")
    normalized = account_assumptions.loc[:, sorted(ASSUMPTION_REQUIRED_COLUMNS)].copy()
    _validate_non_empty_text(normalized["customer_id"], "account_assumptions.customer_id")
    _validate_non_empty_text(normalized["account_id"], "account_assumptions.account_id")
    if normalized["customer_id"].duplicated().any():
        duplicate_ids = _duplicates(normalized["customer_id"])
        raise ValueError(
            "account_assumptions must contain one row per customer_id; duplicates: "
            + ", ".join(duplicate_ids)
        )
    if normalized["account_id"].duplicated().any():
        duplicate_ids = _duplicates(normalized["account_id"])
        raise ValueError(
            "account_assumptions.account_id must be unique; duplicates: " + ", ".join(duplicate_ids)
        )

    for column in ["sicr", "credit_impaired", "defaulted"]:
        _validate_boolean_column(normalized[column], f"account_assumptions.{column}")
    for column in [
        "gross_exposure",
        "lgd",
        "remaining_maturity_months",
        "effective_interest_rate",
        "days_past_due",
        "prior_stage",
    ]:
        _validate_finite_numeric(normalized[column], f"account_assumptions.{column}")

    normalized["gross_exposure"] = pd.to_numeric(normalized["gross_exposure"]).astype(float)
    normalized["lgd"] = pd.to_numeric(normalized["lgd"]).astype(float)
    normalized["remaining_maturity_months"] = pd.to_numeric(
        normalized["remaining_maturity_months"]
    ).astype(float)
    normalized["effective_interest_rate"] = pd.to_numeric(
        normalized["effective_interest_rate"]
    ).astype(float)
    normalized["days_past_due"] = pd.to_numeric(normalized["days_past_due"]).astype(float)
    normalized["prior_stage"] = pd.to_numeric(normalized["prior_stage"]).astype(float)

    if (normalized["gross_exposure"] < 0).any():
        raise ValueError("account_assumptions.gross_exposure must be nonnegative")
    if ((normalized["lgd"] < 0) | (normalized["lgd"] > 1)).any():
        raise ValueError("account_assumptions.lgd must be between 0 and 1")
    if (
        (normalized["remaining_maturity_months"] <= 0)
        | (normalized["remaining_maturity_months"] % 1 != 0)
    ).any():
        raise ValueError("account_assumptions.remaining_maturity_months must be a positive integer")
    if (normalized["effective_interest_rate"] <= -1).any():
        raise ValueError("account_assumptions.effective_interest_rate must be greater than -1")
    if ((normalized["days_past_due"] < 0) | (normalized["days_past_due"] % 1 != 0)).any():
        raise ValueError("account_assumptions.days_past_due must be a nonnegative integer")
    if (
        (normalized["prior_stage"] % 1 != 0)
        | (~normalized["prior_stage"].isin([1.0, 2.0, 3.0]))
    ).any():
        raise ValueError("account_assumptions.prior_stage must be one of 1, 2, or 3")

    normalized["remaining_maturity_months"] = normalized["remaining_maturity_months"].astype(int)
    normalized["days_past_due"] = normalized["days_past_due"].astype(int)
    normalized["prior_stage"] = normalized["prior_stage"].astype(int)
    return normalized


def _build_term_structures(
    joined: pd.DataFrame,
    scenarios: tuple[PDScenarioAssumption, ...],
) -> pd.DataFrame:
    rows: list[dict] = []
    for account in joined.to_dict("records"):
        base_hazard = -math.log1p(-float(account["recalibrated_pd"]))
        for scenario in scenarios:
            scenario_hazard = base_hazard * float(scenario.hazard_multiplier)
            monthly_q = 1 - math.exp(-scenario_hazard / 12)
            survival = 1.0
            for month in range(1, int(account["remaining_maturity_months"]) + 1):
                marginal_pd = survival * monthly_q
                survival -= marginal_pd
                rows.append(
                    {
                        "account_id": account["account_id"],
                        "scenario": scenario.name,
                        "month": month,
                        "marginal_pd": marginal_pd,
                        "lgd": float(account["lgd"]) + float(scenario.lgd_addon),
                        "ead": _straight_line_ead(
                            float(account["gross_exposure"]),
                            int(account["remaining_maturity_months"]),
                            month,
                        ),
                    }
                )
    term_structures = pd.DataFrame(rows)
    cumulative_pd = term_structures.groupby(["account_id", "scenario"])["marginal_pd"].sum()
    if (cumulative_pd > 1 + 1e-12).any():
        raise ValueError("Generated term cumulative PD must be less than or equal to 1")
    return term_structures.sort_values(["account_id", "scenario", "month"]).reset_index(drop=True)


def _straight_line_ead(gross_exposure: float, maturity_months: int, month: int) -> float:
    return gross_exposure * (maturity_months - month + 1) / maturity_months


def _build_input_audit(joined: pd.DataFrame, config: PDIntegrationConfig) -> pd.DataFrame:
    audit = joined[
        [
            "customer_id",
            "account_id",
            "observation_date",
            "recalibrated_pd",
            "gross_exposure",
            "lgd",
            "remaining_maturity_months",
            "effective_interest_rate",
            "days_past_due",
            "sicr",
            "credit_impaired",
            "defaulted",
            "prior_stage",
        ]
    ].copy()
    audit["annual_hazard"] = audit["recalibrated_pd"].map(lambda value: -math.log1p(-float(value)))
    audit["ead_method"] = config.ead_method
    audit["assumption_basis"] = (
        "Illustrative non-PD account assumptions independent of Project 1 actual_default outcomes"
    )
    return audit.sort_values("account_id").reset_index(drop=True)


def _validate_one_to_one_bridge(snapshot: pd.DataFrame, assumptions: pd.DataFrame) -> None:
    snapshot_ids = set(snapshot["customer_id"])
    assumption_ids = set(assumptions["customer_id"])
    missing_assumptions = sorted(snapshot_ids - assumption_ids)
    extra_assumptions = sorted(assumption_ids - snapshot_ids)
    if missing_assumptions:
        raise ValueError(
            "account_assumptions missing customer_id records from PD snapshot: "
            + ", ".join(missing_assumptions)
        )
    if extra_assumptions:
        raise ValueError(
            "account_assumptions contain customer_id records absent from PD snapshot: "
            + ", ".join(extra_assumptions)
        )


def _validate_scenario_lgd(
    accounts: pd.DataFrame,
    scenarios: tuple[PDScenarioAssumption, ...],
) -> None:
    for scenario in scenarios:
        scenario_lgd = accounts["lgd"] + float(scenario.lgd_addon)
        if ((scenario_lgd < 0) | (scenario_lgd > 1)).any():
            raise ValueError(
                f"Scenario LGD add-on for {scenario.name} produces LGD outside [0, 1]"
            )


def _validate_scenario_ordering(scenarios: Iterable[PDScenarioAssumption]) -> None:
    by_name = {scenario.name: scenario for scenario in scenarios}
    if {"upside", "base", "downside"}.issubset(by_name):
        if not (
            by_name["upside"].hazard_multiplier
            < by_name["base"].hazard_multiplier
            < by_name["downside"].hazard_multiplier
        ):
            raise ValueError(
                "Scenario hazard multipliers must satisfy upside < base < downside"
            )
        if not (
            by_name["upside"].lgd_addon
            <= by_name["base"].lgd_addon
            <= by_name["downside"].lgd_addon
        ):
            raise ValueError("Scenario LGD add-ons must satisfy upside <= base <= downside")


def _parse_dates(values: pd.Series, label: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{label} must contain valid dates")
    return parsed.dt.normalize()


def _validate_required_columns(
    frame: pd.DataFrame,
    required_columns: set[str],
    frame_name: str,
) -> None:
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {', '.join(missing)}")


def _validate_not_empty(frame: pd.DataFrame, frame_name: str) -> None:
    if frame.empty:
        raise ValueError(f"{frame_name} must contain at least one row")


def _validate_pd_values(values: pd.Series, label: str) -> None:
    _validate_finite_numeric(values, label)
    numeric_values = pd.to_numeric(values)
    if ((numeric_values < 0) | (numeric_values >= 1)).any():
        raise ValueError(f"{label} must be greater than or equal to 0 and less than 1")


def _validate_finite_number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be numeric")
    try:
        numeric_value = float(value)
    except TypeError as error:
        raise TypeError(f"{label} must be numeric") from error
    except ValueError as error:
        raise ValueError(f"{label} must be numeric") from error
    if not math.isfinite(numeric_value):
        raise ValueError(f"{label} must be finite")
    return numeric_value


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


def _duplicates(values: Iterable[object]) -> list[str]:
    series = pd.Series(list(values), dtype=object)
    duplicate_values = series[series.duplicated()].drop_duplicates().astype(str)
    return sorted(duplicate_values.tolist())
