from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from numbers import Integral

import pandas as pd

APPROVAL_STATUSES = {"approved", "pending", "rejected"}


@dataclass(frozen=True)
class SICRRebuttal:
    rebuttal_id: str
    account_id: str
    observed_days_past_due: int
    evidence_reference: str
    evidence_summary: str
    reasonable_and_supportable: bool
    forward_looking_review_completed: bool
    other_sicr_indicators_present: bool
    decision_date: str
    valid_until: str
    approval_status: str
    approved_by: str | None


@dataclass(frozen=True)
class SICRRebuttalEvaluation:
    register: pd.DataFrame
    approved_account_ids: frozenset[str]


def evaluate_sicr_rebuttals(
    accounts: pd.DataFrame,
    rebuttals: Sequence[SICRRebuttal],
    reporting_date: str | None,
    *,
    stage2_dpd_backstop: int | None,
    stage3_dpd_backstop: int | None,
) -> SICRRebuttalEvaluation:
    if not rebuttals:
        return SICRRebuttalEvaluation(
            register=pd.DataFrame(columns=_register_columns()),
            approved_account_ids=frozenset(),
        )
    if reporting_date is None:
        raise ValueError("reporting_date is required when SICR rebuttals are provided")
    _validate_rebuttal_batch(accounts, rebuttals)
    as_of_date = _parse_date(reporting_date, "reporting_date")
    accounts_by_id = accounts.set_index("account_id")
    rows = []
    approved_account_ids = set()
    for rebuttal in rebuttals:
        row = _evaluate_rebuttal(
            accounts_by_id.loc[rebuttal.account_id],
            rebuttal,
            as_of_date,
            stage2_dpd_backstop=stage2_dpd_backstop,
            stage3_dpd_backstop=stage3_dpd_backstop,
        )
        rows.append(row)
        if row["decision_outcome"] == "approved_effective":
            approved_account_ids.add(rebuttal.account_id)
    return SICRRebuttalEvaluation(
        register=pd.DataFrame(rows, columns=_register_columns()),
        approved_account_ids=frozenset(approved_account_ids),
    )


def _validate_rebuttal_batch(
    accounts: pd.DataFrame,
    rebuttals: Sequence[SICRRebuttal],
) -> None:
    rebuttal_ids = [rebuttal.rebuttal_id for rebuttal in rebuttals]
    if len(rebuttal_ids) != len(set(rebuttal_ids)):
        raise ValueError("SICR rebuttal IDs must be unique")
    account_ids = [rebuttal.account_id for rebuttal in rebuttals]
    if len(account_ids) != len(set(account_ids)):
        raise ValueError("Only one SICR rebuttal is allowed per account")
    unknown_account_ids = set(account_ids) - set(accounts["account_id"])
    if unknown_account_ids:
        raise ValueError("SICR rebuttals contain unknown account IDs")
    for rebuttal in rebuttals:
        for field_name in [
            "rebuttal_id",
            "account_id",
            "evidence_reference",
            "evidence_summary",
        ]:
            _validate_text(getattr(rebuttal, field_name), field_name)
        if (
            isinstance(rebuttal.observed_days_past_due, bool)
            or not isinstance(rebuttal.observed_days_past_due, Integral)
            or rebuttal.observed_days_past_due < 0
        ):
            raise ValueError("observed_days_past_due must be a nonnegative integer")
        for field_name in [
            "reasonable_and_supportable",
            "forward_looking_review_completed",
            "other_sicr_indicators_present",
        ]:
            if not isinstance(getattr(rebuttal, field_name), bool):
                raise TypeError(f"{field_name} must be boolean")
        if rebuttal.approval_status not in APPROVAL_STATUSES:
            raise ValueError(
                "approval_status must be one of: "
                + ", ".join(sorted(APPROVAL_STATUSES))
            )
        if rebuttal.approval_status == "approved" and (
            not isinstance(rebuttal.approved_by, str) or not rebuttal.approved_by.strip()
        ):
            raise ValueError("approved_by is required for approved rebuttals")
        if rebuttal.approved_by is not None and (
            not isinstance(rebuttal.approved_by, str) or not rebuttal.approved_by.strip()
        ):
            raise ValueError("approved_by must be a non-empty string when provided")


def _evaluate_rebuttal(
    account: pd.Series,
    rebuttal: SICRRebuttal,
    as_of_date: date,
    *,
    stage2_dpd_backstop: int | None,
    stage3_dpd_backstop: int | None,
) -> dict[str, object]:
    current_dpd = int(account["days_past_due"])
    decision_date = _parse_date(rebuttal.decision_date, "decision_date")
    valid_until = _parse_date(rebuttal.valid_until, "valid_until")
    if valid_until < decision_date:
        raise ValueError("valid_until must not precede decision_date")
    stage3_precedence = (
        bool(account["credit_impaired"])
        or bool(account["defaulted"])
        or (
            stage3_dpd_backstop is not None
            and current_dpd >= stage3_dpd_backstop
        )
    )
    presumption_applicable = (
        stage2_dpd_backstop is not None
        and current_dpd >= stage2_dpd_backstop
        and not stage3_precedence
        and not bool(account["sicr"])
    )
    decision_outcome = _decision_outcome(
        account,
        rebuttal,
        as_of_date,
        decision_date,
        valid_until,
        current_dpd=current_dpd,
        stage3_precedence=stage3_precedence,
        presumption_applicable=presumption_applicable,
    )
    return {
        "rebuttal_id": rebuttal.rebuttal_id,
        "account_id": rebuttal.account_id,
        "reporting_date": as_of_date.isoformat(),
        "observed_days_past_due": rebuttal.observed_days_past_due,
        "current_days_past_due": current_dpd,
        "stage2_dpd_backstop": stage2_dpd_backstop,
        "stage3_dpd_backstop": stage3_dpd_backstop,
        "presumption_applicable": presumption_applicable,
        "evidence_reference": rebuttal.evidence_reference,
        "evidence_summary": rebuttal.evidence_summary,
        "reasonable_and_supportable": rebuttal.reasonable_and_supportable,
        "forward_looking_review_completed": rebuttal.forward_looking_review_completed,
        "other_sicr_indicators_present": rebuttal.other_sicr_indicators_present,
        "decision_date": decision_date.isoformat(),
        "valid_until": valid_until.isoformat(),
        "approval_status": rebuttal.approval_status,
        "approved_by": rebuttal.approved_by or "",
        "decision_outcome": decision_outcome,
    }


def _decision_outcome(
    account: pd.Series,
    rebuttal: SICRRebuttal,
    as_of_date: date,
    decision_date: date,
    valid_until: date,
    *,
    current_dpd: int,
    stage3_precedence: bool,
    presumption_applicable: bool,
) -> str:
    if stage3_precedence:
        return "blocked_stage3_precedence"
    if bool(account["sicr"]) or rebuttal.other_sicr_indicators_present:
        return "blocked_other_sicr_indicator"
    if not presumption_applicable:
        return "blocked_not_applicable"
    if current_dpd != rebuttal.observed_days_past_due:
        return "blocked_dpd_mismatch"
    if not rebuttal.reasonable_and_supportable:
        return "blocked_insufficient_evidence"
    if not rebuttal.forward_looking_review_completed:
        return "blocked_forward_looking_review"
    if as_of_date < decision_date:
        return "not_yet_effective"
    if as_of_date > valid_until:
        return "expired"
    if rebuttal.approval_status == "pending":
        return "pending_approval"
    if rebuttal.approval_status == "rejected":
        return "rejected"
    return "approved_effective"


def _parse_date(value: object, label: str) -> date:
    if not isinstance(value, str):
        raise TypeError(f"{label} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} must use YYYY-MM-DD") from error


def _validate_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _register_columns() -> list[str]:
    return [
        "rebuttal_id",
        "account_id",
        "reporting_date",
        "observed_days_past_due",
        "current_days_past_due",
        "stage2_dpd_backstop",
        "stage3_dpd_backstop",
        "presumption_applicable",
        "evidence_reference",
        "evidence_summary",
        "reasonable_and_supportable",
        "forward_looking_review_completed",
        "other_sicr_indicators_present",
        "decision_date",
        "valid_until",
        "approval_status",
        "approved_by",
        "decision_outcome",
    ]
