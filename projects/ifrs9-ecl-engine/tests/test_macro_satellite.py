from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ifrs9_ecl_engine.macro_satellite import run_macro_satellite
from ifrs9_ecl_engine.macro_satellite_demo import run_macro_satellite_pipeline


def _quarterly_sample() -> pd.DataFrame:
    quarters = pd.date_range("2007-03-31", periods=48, freq="QE")
    unemployment = 5.2 + 0.7 * np.sin(np.arange(48) / 4.0)
    gdp_growth = 2.4 + 1.5 * np.cos(np.arange(48) / 5.0)
    logit_npl = [-4.8]
    for index in range(1, len(quarters)):
        next_value = (
            -0.58
            + 0.86 * logit_npl[-1]
            + 0.09 * unemployment[index]
            + 0.07 * -gdp_growth[index]
        )
        logit_npl.append(next_value)
    npl_ratio = 1.0 / (1.0 + np.exp(-np.asarray(logit_npl)))
    return pd.DataFrame(
        {
            "quarter": quarters,
            "npl_proxy_ratio": npl_ratio,
            "unemployment_rate_pct": unemployment,
            "real_gdp_yoy_pct": gdp_growth,
            "apra_reporting_basis": "pre_aps_220_impaired_plus_past_due",
        }
    )


def test_macro_satellite_freezes_oot_and_orders_scenario_response() -> None:
    data = _quarterly_sample()
    kwargs = {
        "development_end": "2013-12-31",
        "validation_end": "2015-12-31",
        "oot_end": "2018-12-31",
        "alpha_grid": (0.01, 0.1, 1.0),
    }

    result = run_macro_satellite(data, **kwargs)
    changed_oot = data.copy()
    changed_oot.loc[changed_oot["quarter"] > "2015-12-31", "npl_proxy_ratio"] *= 1.25
    rerun = run_macro_satellite(changed_oot, **kwargs)

    pd.testing.assert_frame_equal(result.coefficients, rerun.coefficients)
    pd.testing.assert_frame_equal(result.scenario_response, rerun.scenario_response)
    assert set(result.predictions["split"]) == {"development", "validation", "oot"}
    assert result.predictions.loc[
        result.predictions["split"] == "oot", "quarter"
    ].min() == pd.Timestamp("2016-03-31")

    multipliers = result.scenario_response.set_index("scenario")["npl_multiplier"]
    assert multipliers["upside"] < multipliers["base"] < multipliers["downside"]
    assert multipliers["base"] == pytest.approx(1.0)
    assert (result.coefficients["standardized_coefficient"] >= 0).all()


def test_macro_satellite_rejects_reporting_break_and_non_quarterly_data() -> None:
    data = _quarterly_sample()
    post_break = pd.concat(
        [
            data,
            pd.DataFrame(
                [
                    {
                        "quarter": "2022-03-31",
                        "npl_proxy_ratio": 0.01,
                        "unemployment_rate_pct": 4.0,
                        "real_gdp_yoy_pct": 3.0,
                        "apra_reporting_basis": "aps_220_non_performing",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="APS 220 reporting break"):
        run_macro_satellite(post_break)

    missing_quarter = data.drop(index=10).reset_index(drop=True)
    with pytest.raises(ValueError, match="contiguous quarter ends"):
        run_macro_satellite(
            missing_quarter,
            development_end="2013-12-31",
            validation_end="2015-12-31",
            oot_end="2018-12-31",
        )


def test_committed_public_macro_snapshot_is_complete_and_traceable() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    data_path = project_dir / "data" / "public" / "australia_macro_credit.csv"
    lineage_path = project_dir / "data" / "public" / "australia_macro_credit_lineage.json"

    data = pd.read_csv(data_path, parse_dates=["quarter"])
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))

    assert len(data) == 70
    assert data["quarter"].iloc[0] == pd.Timestamp("2004-09-30")
    assert data["quarter"].iloc[-1] == pd.Timestamp("2021-12-31")
    assert data["npl_proxy_ratio"].iloc[0] == pytest.approx(7_948.3 / 1_077_915.6)
    assert data["npl_proxy_ratio"].iloc[-1] == pytest.approx(32_641.5 / 3_640_021.5)
    assert set(data["apra_reporting_basis"]) == {
        "pre_aps_220_impaired_plus_past_due"
    }
    assert lineage["reporting_break"]["excluded_from"] == "2022-03-31"
    assert {source["publisher"] for source in lineage["sources"]} == {
        "APRA",
        "RBA",
    }
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == lineage[
        "curated_file_sha256"
    ]


def test_macro_satellite_pipeline_quantifies_a_b_ecl_impact(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    data_path = project_dir / "data" / "public" / "australia_macro_credit.csv"

    output = run_macro_satellite_pipeline(data_path, tmp_path)

    oot = output.satellite.performance.set_index("split").loc["oot"]
    assert oot["mae_improvement_vs_persistence"] < 0
    multipliers = output.satellite.scenario_response.set_index("scenario")[
        "npl_multiplier"
    ]
    assert multipliers["downside"] > 1.0
    assert multipliers["upside"] < 1.0

    comparison = output.ecl_comparison
    total = comparison[comparison["stage"] == "Total"].set_index("variant")
    assert total.loc["challenger_empirical", "modelled_ecl"] < total.loc[
        "incumbent_manual", "modelled_ecl"
    ]
    assert total.loc["challenger_empirical", "change_vs_incumbent"] < 0
    assert "not approved for point forecasting" in output.report_paths[
        "macro_satellite_report"
    ].read_text(encoding="utf-8")


def test_macro_satellite_cli_is_reproducible(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    data_path = project_dir / "data" / "public" / "australia_macro_credit.csv"
    expected_files = [
        "backtest_performance.csv",
        "backtest_predictions.csv",
        "data_audit.csv",
        "ecl_ab_comparison.csv",
        "ecl_scenario_comparison.csv",
        "macro_satellite_report.md",
        "model_coefficients.csv",
        "model_specification.json",
        "model_tuning.csv",
        "scenario_pd_multipliers.csv",
    ]

    output_dirs = [tmp_path / "first", tmp_path / "second"]
    for output_dir in output_dirs:
        subprocess.run(
            [
                sys.executable,
                str(project_dir / "scripts" / "run_macro_satellite.py"),
                "--data-path",
                str(data_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=project_dir,
            check=True,
        )
        assert sorted(path.name for path in output_dir.iterdir()) == expected_files

    for report_name in expected_files:
        assert (output_dirs[0] / report_name).read_bytes() == (
            output_dirs[1] / report_name
        ).read_bytes()


def test_sql_schema_persists_macro_backtest_scenarios_and_a_b_result() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    schema = (project_dir / "sql" / "schema.sql").read_text(encoding="utf-8")

    with sqlite3.connect(":memory:") as connection:
        connection.executescript(schema)
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "ecl_macro_satellite_backtest",
            "ecl_macro_scenario_multiplier",
            "ecl_macro_challenger_comparison",
        }.issubset(table_names)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ecl_macro_scenario_multiplier (
                    scenario, anchor_quarter, unemployment_shock_pp,
                    real_gdp_growth_shock_pp, predicted_npl_ratio,
                    npl_multiplier, evidence_use
                ) VALUES ('base', '2018-12-31', 0, 0, 0.01, 1.2, 'sensitivity_only')
                """
            )
