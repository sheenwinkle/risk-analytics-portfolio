from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SUPPORTED_CONTRACT_VERSION = "1.0"
EXPECTED_ROLES = ("model_development", "calibration_holdout")
SUPPORTED_PREPROCESSING = {
    "numeric": ["median_imputation", "standard_scaling"],
    "categorical": ["most_frequent_imputation", "one_hot_ignore_unknown"],
}
SUPPORTED_ESTIMATORS = {
    "logistic_regression": "sklearn.linear_model.LogisticRegression",
    "random_forest": "sklearn.ensemble.RandomForestClassifier",
}
REPLICATION_REPORT_TABLES = (
    "replication_input_audit",
    "model_replication_summary",
    "parameter_stability_summary",
    "parameter_stability_detail",
)


@dataclass(frozen=True)
class Project1DevelopmentAdapter:
    sample_path: str | Path
    specification_path: str | Path
    selection_audit_path: str | Path
    parameter_reference_path: str | Path

    def load(self) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame, pd.DataFrame]:
        paths = {
            "development sample": Path(self.sample_path),
            "model specification": Path(self.specification_path),
            "selection audit": Path(self.selection_audit_path),
            "parameter reference": Path(self.parameter_reference_path),
        }
        for label, path in paths.items():
            if not path.is_file():
                raise FileNotFoundError(f"Project 1 {label} file not found: {path}")

        specification = json.loads(paths["model specification"].read_text(encoding="utf-8"))
        return (
            pd.read_csv(paths["development sample"], dtype={"customer_id": "string"}),
            specification,
            pd.read_csv(paths["selection audit"]),
            pd.read_csv(paths["parameter reference"]),
        )


@dataclass(frozen=True)
class ModelReplicationResult:
    replication_input_audit: pd.DataFrame
    model_replication_summary: pd.DataFrame
    parameter_stability_summary: pd.DataFrame
    parameter_stability_detail: pd.DataFrame
    report_paths: dict[str, str] = field(default_factory=dict)


def run_model_replication(
    adapter: Project1DevelopmentAdapter,
    *,
    auc_tolerance: float = 1e-8,
    parameter_tolerance: float = 1e-8,
) -> ModelReplicationResult:
    """Independently rebuild Project 1 candidates from its governed development extract."""
    _validate_tolerance(auc_tolerance, "auc_tolerance")
    _validate_tolerance(parameter_tolerance, "parameter_tolerance")
    sample, specification, selection, parameter_reference = adapter.load()
    normalized, audit = _validate_inputs(sample, specification, selection, parameter_reference)

    numeric_features = list(specification["numeric_features"])
    categorical_features = list(specification["categorical_features"])
    feature_columns = [*numeric_features, *categorical_features]
    development = normalized[normalized["sample_role"].eq(EXPECTED_ROLES[0])]
    holdout = normalized[normalized["sample_role"].eq(EXPECTED_ROLES[1])]

    fitted_models: dict[str, Pipeline] = {}
    replicated_auc: dict[str, float] = {}
    for model_name, model in _build_candidate_models(specification).items():
        model.fit(development[feature_columns], development["actual_default"])
        scores = model.predict_proba(holdout[feature_columns])[:, 1]
        fitted_models[model_name] = model
        replicated_auc[model_name] = float(roc_auc_score(holdout["actual_default"], scores))

    replicated_selected = min(
        replicated_auc,
        key=lambda name: (-replicated_auc[name], name),
    )
    replication_summary = _build_replication_summary(
        selection,
        replicated_auc,
        replicated_selected,
        auc_tolerance,
    )
    replicated_parameters = _extract_parameters(fitted_models)
    parameter_detail, parameter_summary = _build_parameter_stability(
        parameter_reference,
        replicated_parameters,
        parameter_tolerance,
    )
    return ModelReplicationResult(
        replication_input_audit=audit,
        model_replication_summary=replication_summary,
        parameter_stability_summary=parameter_summary,
        parameter_stability_detail=parameter_detail,
    )


def run_model_replication_pipeline(
    adapter: Project1DevelopmentAdapter,
    output_dir: str | Path,
    *,
    auc_tolerance: float = 1e-8,
    parameter_tolerance: float = 1e-8,
) -> ModelReplicationResult:
    result = run_model_replication(
        adapter,
        auc_tolerance=auc_tolerance,
        parameter_tolerance=parameter_tolerance,
    )
    report_paths = write_model_replication_reports(result, Path(output_dir))
    return replace(result, report_paths=report_paths)


def write_model_replication_reports(
    result: ModelReplicationResult,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_paths: dict[str, str] = {}
    for table_name in REPLICATION_REPORT_TABLES:
        path = output_dir / f"{table_name}.csv"
        getattr(result, table_name).to_csv(
            path,
            index=False,
            float_format="%.10f",
            lineterminator="\n",
        )
        report_paths[path.name] = str(path)
    report_path = output_dir / "model_replication_report.md"
    report_path.write_text(
        _build_markdown_report(result),
        encoding="utf-8",
        newline="\n",
    )
    report_paths[report_path.name] = str(report_path)
    return report_paths


def _validate_inputs(
    sample: pd.DataFrame,
    specification: dict[str, object],
    selection: pd.DataFrame,
    parameter_reference: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _validate_specification(specification)
    numeric_features = list(specification["numeric_features"])
    categorical_features = list(specification["categorical_features"])
    required_sample_columns = {
        "customer_id",
        "observation_date",
        "sample_role",
        "actual_default",
        *numeric_features,
        *categorical_features,
    }
    missing = sorted(required_sample_columns - set(sample.columns))
    if missing:
        raise ValueError("Development sample missing required columns: " + ", ".join(missing))
    if sample.empty:
        raise ValueError("Development sample must contain at least one row")

    normalized = sample.loc[
        :,
        [
            "customer_id",
            "observation_date",
            "sample_role",
            *numeric_features,
            *categorical_features,
            "actual_default",
        ],
    ].copy()
    _validate_customer_ids(normalized["customer_id"])
    normalized["observation_date"] = pd.to_datetime(
        normalized["observation_date"],
        errors="coerce",
        format="mixed",
    )
    if normalized["observation_date"].isna().any():
        raise ValueError("observation_date must contain parseable dates")
    normalized["sample_role"] = normalized["sample_role"].astype("string").str.strip()
    if set(normalized["sample_role"].dropna()) != set(EXPECTED_ROLES):
        raise ValueError(
            "sample_role must contain exactly model_development and calibration_holdout"
        )

    for feature in numeric_features:
        values = pd.to_numeric(normalized[feature], errors="coerce")
        invalid = normalized[feature].notna() & values.isna()
        if invalid.any() or not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
            raise ValueError(f"{feature} must contain finite numeric values when present")
        if values.notna().sum() == 0:
            raise ValueError(f"{feature} must contain at least one numeric value")
        normalized[feature] = values.astype(float)
    for feature in categorical_features:
        values = normalized[feature]
        present = values.dropna().astype(str).str.strip()
        if present.eq("").any() or present.empty:
            raise ValueError(f"{feature} must contain category values when present")
        normalized[feature] = values.where(values.notna(), np.nan).astype(object)

    target = pd.to_numeric(normalized["actual_default"], errors="coerce")
    if target.isna().any() or (~target.isin([0, 1])).any():
        raise ValueError("actual_default must contain only binary 0/1 values")
    normalized["actual_default"] = target.astype(int)
    for role in EXPECTED_ROLES:
        role_target = normalized.loc[normalized["sample_role"].eq(role), "actual_default"]
        if set(role_target) != {0, 1}:
            raise ValueError(f"{role} must contain both default classes")

    development = normalized[normalized["sample_role"].eq(EXPECTED_ROLES[0])]
    holdout = normalized[normalized["sample_role"].eq(EXPECTED_ROLES[1])]
    if development["observation_date"].max() >= holdout["observation_date"].min():
        raise ValueError("model_development must end before calibration_holdout begins")
    _validate_loan_to_income(normalized)
    _validate_selection_audit(selection, specification, development, holdout)
    _validate_parameter_reference(parameter_reference, specification)

    audit = pd.DataFrame(
        [
            {
                "check": "contract_version",
                "status": "pass",
                "detail": SUPPORTED_CONTRACT_VERSION,
            },
            {
                "check": "row_count",
                "status": "pass",
                "detail": f"{len(normalized)} governed development rows",
            },
            {
                "check": "unique_customer_id",
                "status": "pass",
                "detail": "non-empty and unique across both samples",
            },
            {
                "check": "temporal_roles",
                "status": "pass",
                "detail": (
                    f"development ends {development['observation_date'].max().date()}; "
                    f"holdout starts {holdout['observation_date'].min().date()}"
                ),
            },
            {
                "check": "binary_target",
                "status": "pass",
                "detail": "both classes present in each sample role",
            },
            {
                "check": "derived_feature_lineage",
                "status": "pass",
                "detail": "loan_to_income independently reproduced",
            },
            {
                "check": "selection_audit",
                "status": "pass",
                "detail": "candidate, sample count, date range, and selection checks passed",
            },
            {
                "check": "parameter_reference",
                "status": "pass",
                "detail": "unique finite parameter references available for both candidates",
            },
        ]
    )
    return normalized, audit


def _validate_specification(specification: dict[str, object]) -> None:
    if specification.get("contract_version") != SUPPORTED_CONTRACT_VERSION:
        raise ValueError(f"Unsupported model development contract version: {specification.get('contract_version')}")
    expected_scalars = {
        "id_column": "customer_id",
        "date_column": "observation_date",
        "sample_role_column": "sample_role",
        "target_column": "actual_default",
        "selection_metric": "roc_auc",
        "selection_tie_break": "model_name_ascending",
    }
    for key, expected in expected_scalars.items():
        if specification.get(key) != expected:
            raise ValueError(f"Unsupported model development specification for {key}")
    if specification.get("roles") != list(EXPECTED_ROLES):
        raise ValueError("Model development specification roles are unsupported")
    if specification.get("preprocessing") != SUPPORTED_PREPROCESSING:
        raise ValueError("Model development preprocessing specification is unsupported")

    numeric = specification.get("numeric_features")
    categorical = specification.get("categorical_features")
    if not _is_unique_string_list(numeric) or not _is_unique_string_list(categorical):
        raise ValueError("Model feature lists must contain unique non-empty strings")
    if set(numeric) & set(categorical):
        raise ValueError("Numeric and categorical model features must not overlap")
    if "loan_to_income" not in numeric:
        raise ValueError("Numeric model features must include loan_to_income")
    if specification.get("derived_features") != {
        "loan_to_income": "loan_amount / max(annual_income, 1)"
    }:
        raise ValueError("loan_to_income derivation specification is unsupported")

    candidates = specification.get("candidate_models")
    if not isinstance(candidates, dict) or set(candidates) != set(SUPPORTED_ESTIMATORS):
        raise ValueError("Model development specification must contain both supported candidates")
    for model_name, estimator in SUPPORTED_ESTIMATORS.items():
        model_specification = candidates[model_name]
        if not isinstance(model_specification, dict):
            raise TypeError(f"Invalid candidate model specification: {model_name}")
        if model_specification.get("estimator") != estimator:
            raise ValueError(f"Unsupported estimator for {model_name}")
        if not isinstance(model_specification.get("parameters"), dict):
            raise TypeError(f"Candidate parameters missing for {model_name}")


def _build_candidate_models(specification: dict[str, object]) -> dict[str, Pipeline]:
    numeric_features = list(specification["numeric_features"])
    categorical_features = list(specification["categorical_features"])
    candidates = specification["candidate_models"]
    logistic_parameters = dict(candidates["logistic_regression"]["parameters"])
    forest_parameters = dict(candidates["random_forest"]["parameters"])
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocessor", _build_preprocessor(numeric_features, categorical_features)),
                ("classifier", LogisticRegression(**logistic_parameters)),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", _build_preprocessor(numeric_features, categorical_features)),
                ("classifier", RandomForestClassifier(**forest_parameters)),
            ]
        ),
    }


def _build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
) -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(strategy="median", keep_empty_features=True),
                        ),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_features,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
        ]
    )


def _build_replication_summary(
    selection: pd.DataFrame,
    replicated_auc: dict[str, float],
    replicated_selected: str,
    tolerance: float,
) -> pd.DataFrame:
    reference = selection.copy()
    reference["selected_model"] = _boolean_series(reference["selected_model"])
    rows = []
    for model_name in sorted(replicated_auc):
        reference_row = reference[reference["model"].eq(model_name)].iloc[0]
        reference_auc = float(reference_row["calibration_holdout_roc_auc"])
        replicated_value = replicated_auc[model_name]
        delta = abs(reference_auc - replicated_value)
        reference_selected = bool(reference_row["selected_model"])
        replicated_is_selected = model_name == replicated_selected
        selection_matches = reference_selected == replicated_is_selected
        rows.append(
            {
                "model": model_name,
                "reference_calibration_auc": reference_auc,
                "replicated_calibration_auc": replicated_value,
                "auc_absolute_delta": delta,
                "auc_tolerance": tolerance,
                "reference_selected": reference_selected,
                "replicated_selected": replicated_is_selected,
                "selection_matches": selection_matches,
                "status": "pass" if delta <= tolerance and selection_matches else "fail",
            }
        )
    return pd.DataFrame(rows)


def _extract_parameters(models: dict[str, Pipeline]) -> pd.DataFrame:
    rows = []
    for model_name, model in models.items():
        preprocessor = model.named_steps["preprocessor"]
        classifier = model.named_steps["classifier"]
        feature_names = [
            str(value).split("__", maxsplit=1)[-1]
            for value in preprocessor.get_feature_names_out()
        ]
        if model_name == "logistic_regression":
            parameter_type = "standardized_coefficient"
            values = classifier.coef_[0]
        else:
            parameter_type = "impurity_importance"
            values = classifier.feature_importances_
        rows.extend(
            {
                "model": model_name,
                "feature_name": feature_name,
                "parameter_type": parameter_type,
                "replicated_value": float(value),
            }
            for feature_name, value in zip(feature_names, values, strict=True)
        )
    return pd.DataFrame(rows)


def _build_parameter_stability(
    reference: pd.DataFrame,
    replicated: pd.DataFrame,
    tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = reference.merge(
        replicated,
        on=["model", "feature_name", "parameter_type"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    detail["absolute_delta"] = (
        detail["reference_value"] - detail["replicated_value"]
    ).abs()
    detail["within_tolerance"] = detail["absolute_delta"].le(tolerance) & detail[
        "_merge"
    ].eq("both")
    detail["status"] = np.where(detail["within_tolerance"], "pass", "fail")
    detail = detail.drop(columns="_merge").sort_values(
        ["model", "parameter_type", "feature_name"]
    )

    summary_rows = []
    for (model_name, parameter_type), group in detail.groupby(
        ["model", "parameter_type"],
        sort=True,
    ):
        comparable = group.dropna(subset=["reference_value", "replicated_value"])
        rank_correlation = comparable["reference_value"].abs().corr(
            comparable["replicated_value"].abs(),
            method="spearman",
        )
        if parameter_type == "standardized_coefficient":
            sign_agreement = float(
                np.sign(comparable["reference_value"])
                .eq(np.sign(comparable["replicated_value"]))
                .mean()
            )
        else:
            sign_agreement = math.nan
        summary_rows.append(
            {
                "model": model_name,
                "parameter_type": parameter_type,
                "reference_features": int(group["reference_value"].notna().sum()),
                "replicated_features": int(group["replicated_value"].notna().sum()),
                "feature_set_matches": bool(group[["reference_value", "replicated_value"]].notna().all(axis=1).all()),
                "mean_absolute_delta": float(comparable["absolute_delta"].mean()),
                "max_absolute_delta": float(comparable["absolute_delta"].max()),
                "absolute_rank_correlation": float(rank_correlation),
                "coefficient_sign_agreement_rate": sign_agreement,
                "parameter_tolerance": tolerance,
                "status": "pass" if group["status"].eq("pass").all() else "fail",
            }
        )
    ordered_detail = detail[
        [
            "model",
            "parameter_type",
            "feature_name",
            "reference_value",
            "replicated_value",
            "absolute_delta",
            "within_tolerance",
            "status",
        ]
    ].reset_index(drop=True)
    return ordered_detail, pd.DataFrame(summary_rows)


def _validate_selection_audit(
    selection: pd.DataFrame,
    specification: dict[str, object],
    development: pd.DataFrame,
    holdout: pd.DataFrame,
) -> None:
    required = {
        "model",
        "model_development_accounts",
        "calibration_holdout_accounts",
        "model_development_start",
        "model_development_end",
        "calibration_holdout_start",
        "calibration_holdout_end",
        "calibration_holdout_roc_auc",
        "selected_model",
    }
    missing = sorted(required - set(selection.columns))
    if missing:
        raise ValueError("Selection audit missing required columns: " + ", ".join(missing))
    expected_models = set(specification["candidate_models"])
    if set(selection["model"]) != expected_models or selection["model"].duplicated().any():
        raise ValueError("Selection audit must contain one row per specified candidate")
    auc = pd.to_numeric(selection["calibration_holdout_roc_auc"], errors="coerce")
    if auc.isna().any() or (~auc.between(0, 1)).any():
        raise ValueError("Selection audit AUC values must be finite values in [0, 1]")
    selected = _boolean_series(selection["selected_model"])
    if selected.sum() != 1:
        raise ValueError("Selection audit must identify exactly one selected model")

    expected_values = {
        "model_development_accounts": len(development),
        "calibration_holdout_accounts": len(holdout),
        "model_development_start": development["observation_date"].min().date().isoformat(),
        "model_development_end": development["observation_date"].max().date().isoformat(),
        "calibration_holdout_start": holdout["observation_date"].min().date().isoformat(),
        "calibration_holdout_end": holdout["observation_date"].max().date().isoformat(),
    }
    for column, expected in expected_values.items():
        values = selection[column]
        if column.endswith("accounts"):
            matches = pd.to_numeric(values, errors="coerce").eq(expected)
        else:
            parsed = pd.to_datetime(values, errors="coerce", format="mixed")
            matches = parsed.dt.strftime("%Y-%m-%d").eq(expected)
        if not matches.all():
            raise ValueError(f"Selection audit {column} does not match the development sample")


def _validate_parameter_reference(
    reference: pd.DataFrame,
    specification: dict[str, object],
) -> None:
    required = {"model", "feature_name", "parameter_type", "reference_value"}
    missing = sorted(required - set(reference.columns))
    if missing:
        raise ValueError("Parameter reference missing required columns: " + ", ".join(missing))
    if reference.empty:
        raise ValueError("Parameter reference must contain model parameters")
    if set(reference["model"]) != set(specification["candidate_models"]):
        raise ValueError("Parameter reference must cover all specified candidates")
    if reference.duplicated(["model", "feature_name", "parameter_type"]).any():
        raise ValueError("Parameter reference rows must be unique")
    values = pd.to_numeric(reference["reference_value"], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Parameter reference values must be finite")


def _validate_customer_ids(values: pd.Series) -> None:
    normalized = values.astype("string").str.strip()
    if normalized.isna().any() or normalized.eq("").any():
        raise ValueError("customer_id must contain non-empty string values")
    if normalized.duplicated().any():
        raise ValueError("customer_id must be unique")


def _validate_loan_to_income(sample: pd.DataFrame) -> None:
    expected = sample["loan_amount"] / sample["annual_income"].clip(lower=1)
    if not np.allclose(
        sample["loan_to_income"].to_numpy(dtype=float),
        expected.to_numpy(dtype=float),
        rtol=1e-10,
        atol=1e-10,
        equal_nan=True,
    ):
        raise ValueError("loan_to_income must match the independently derived value")


def _boolean_series(values: pd.Series) -> pd.Series:
    normalized = values.astype("string").str.strip().str.lower()
    if (~normalized.isin(["true", "false"])).any():
        raise ValueError("selected_model must contain Boolean values")
    return normalized.eq("true")


def _validate_tolerance(value: float, label: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{label} must be a non-negative finite number")


def _is_unique_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
        and len(value) == len(set(value))
    )


def _build_markdown_report(result: ModelReplicationResult) -> str:
    replication_outcome = (
        "pass" if result.model_replication_summary["status"].eq("pass").all() else "fail"
    )
    parameter_outcome = (
        "pass" if result.parameter_stability_summary["status"].eq("pass").all() else "fail"
    )
    selected = result.model_replication_summary.loc[
        result.model_replication_summary["replicated_selected"],
        "model",
    ].item()
    maximum_auc_delta = result.model_replication_summary["auc_absolute_delta"].max()
    maximum_parameter_delta = result.parameter_stability_summary[
        "max_absolute_delta"
    ].max()
    return "\n".join(
        [
            "# Independent Model Replication",
            "",
            "## Scope",
            "",
            (
                "Project 3 independently rebuilds both Project 1 candidates from the governed "
                "pre-OOT development extract. It does not import Project 1 model code."
            ),
            "",
            "## Outcome",
            "",
            f"- Replicated selected model: `{selected}`.",
            f"- Selection and AUC replication outcome: **{replication_outcome.upper()}**.",
            f"- Parameter and importance replication outcome: **{parameter_outcome.upper()}**.",
            f"- Maximum absolute AUC delta: {maximum_auc_delta:.10f}.",
            f"- Maximum absolute parameter delta: {maximum_parameter_delta:.10f}.",
            "",
            "## Model Replication",
            "",
            _markdown_table(result.model_replication_summary),
            "",
            "## Parameter Stability",
            "",
            _markdown_table(result.parameter_stability_summary),
            "",
            "## Governance Notes",
            "",
            "- Development and calibration roles are temporally separated before fitting.",
            "- AUC is recomputed on the frozen pre-OOT calibration holdout.",
            "- Standardized logistic coefficients and random-forest impurity importances are reconciled.",
            "- Borrower-level development records remain local and are not written to this report directory.",
            "",
        ]
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(frame.columns)) + " |"
    rows = []
    for _, row in frame.iterrows():
        values = []
        for value in row:
            if pd.isna(value):
                values.append("N/A")
            elif isinstance(value, float):
                values.append(f"{value:.10f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *rows])
