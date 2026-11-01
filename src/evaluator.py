"""
Forecast Evaluation and Backtesting Engine.
Calculates performance and error metrics against ground-truth historical bookings:
- Cohort Realization Metrics (Actual realized bookings from open snapshot cohort vs Forecast)
- Full Quarter Reconciliation (Closed-to-Date + Remaining Pipeline vs Total Quarter Bookings)
- WAPE (Weighted Absolute Percentage Error)
- MAPE (Mean Absolute Percentage Error)
- RMSE (Root Mean Square Error)
- Forecast Bias (Systematic Over/Under-forecasting)
- Prediction Interval Coverage (P10-P90 / Bear-Bull)
Slices metrics across forecast horizons (30d, 60d, 90d) and market segments.
"""

from typing import Dict, List, Any, Tuple
import datetime
import math
import numpy as np

from src.forecaster import BookingsForecastingEngine
from src.config import QUARTERS, QUARTER_DATE_RANGES


class ForecastEvaluator:
    """
    Backtests forecast snapshots against actual closed historical bookings,
    providing rigorous quantitative performance reporting.
    """

    def __init__(self, data: Dict[str, List[Dict[str, Any]]], forecaster: BookingsForecastingEngine):
        self.data = data
        self.forecaster = forecaster
        self.historical_bookings = data.get("historical_bookings", [])
        self.territory_map = {t["territory_id"]: t for t in data.get("territories", [])}

        # Index actual bookings by opportunity_id and by quarter
        self.bookings_by_opp: Dict[str, Dict[str, Any]] = {
            b["opportunity_id"]: b for b in self.historical_bookings
        }
        self.actuals_by_quarter: Dict[str, float] = {}
        self.actuals_by_quarter_segment: Dict[Tuple[str, str], float] = {}
        self._index_actual_bookings()

    def _index_actual_bookings(self):
        """Aggregates confirmed historical bookings by quarter and segment."""
        for bkg in self.historical_bookings:
            q = bkg["fiscal_quarter"]
            amt = bkg["booking_amount"]
            self.actuals_by_quarter[q] = self.actuals_by_quarter.get(q, 0.0) + amt

            terr = self.territory_map.get(bkg["territory_id"])
            if terr:
                seg = terr["segment"]
                key = (q, seg)
                self.actuals_by_quarter_segment[key] = self.actuals_by_quarter_segment.get(key, 0.0) + amt

    def evaluate_quarters(
        self,
        test_quarters: List[str] = ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    ) -> Dict[str, Any]:
        """
        Runs backtesting across multiple historical quarters and forecast lead horizons:
        - 90 days out (Prior quarter close)
        - 60 days out (Month 1 of target quarter)
        - 30 days out (Month 2 of target quarter)
        """
        cohort_evaluation_records: List[Dict[str, Any]] = []
        quarter_total_records: List[Dict[str, Any]] = []

        snaps = sorted(list({s["snapshot_date"] for s in self.data.get("forecast_snapshots", [])}))

        for q in test_quarters:
            total_quarter_actual = self.actuals_by_quarter.get(q, 0.0)
            if total_quarter_actual <= 0:
                continue

            q_start_str, q_end_str = QUARTER_DATE_RANGES[q]
            q_start = datetime.date.fromisoformat(q_start_str)
            q_end = datetime.date.fromisoformat(q_end_str)

            # Snapshots before quarter start
            prior_snaps = [s for s in snaps if datetime.date.fromisoformat(s) <= q_start]
            if not prior_snaps:
                continue

            snap_90d = prior_snaps[-1]
            in_q_snaps = [s for s in snaps if q_start <= datetime.date.fromisoformat(s) < q_end]

            candidate_evals = [("90d", snap_90d)]
            if len(in_q_snaps) >= 1:
                candidate_evals.append(("60d", in_q_snaps[0]))
            if len(in_q_snaps) >= 2:
                candidate_evals.append(("30d", in_q_snaps[1]))

            for horizon_name, snap_date_str in candidate_evals:
                snap_date = datetime.date.fromisoformat(snap_date_str)
                fcst_res = self.forecaster.forecast_snapshot(snap_date_str, q, num_monte_carlo_runs=300)

                # 1. Closed bookings to date in quarter Q up to snapshot date
                closed_to_date = sum(
                    b["booking_amount"] for b in self.historical_bookings
                    if b["fiscal_quarter"] == q and datetime.date.fromisoformat(b["booked_date"]) <= snap_date
                )

                # 2. Cohort Actuals: deals in this specific snapshot that actually closed WON in quarter Q
                evaluated_opp_ids = set(fcst_res.get("evaluated_opp_ids", []))
                cohort_actual = sum(
                    b["booking_amount"] for opp_id, b in self.bookings_by_opp.items()
                    if opp_id in evaluated_opp_ids
                    and b["fiscal_quarter"] == q
                    and datetime.date.fromisoformat(b["booked_date"]) > snap_date
                )

                base_fcst = fcst_res["scenario_forecasts"]["base"]["expected_mean"]
                naive_weighted = fcst_res["standard_weighted_pipeline"]
                p10 = fcst_res["scenario_forecasts"]["base"]["p10_conservative"]
                p90 = fcst_res["scenario_forecasts"]["base"]["p90_optimistic"]
                bull_fcst = fcst_res["scenario_forecasts"]["bull"]["expected_mean"]
                bear_fcst = fcst_res["scenario_forecasts"]["bear"]["expected_mean"]

                # Total quarter projection = closed_to_date + base_fcst
                proj_quarter_total = closed_to_date + base_fcst
                proj_naive_total = closed_to_date + naive_weighted

                # Cohort realization record
                abs_err_calib_cohort = abs(cohort_actual - base_fcst)
                abs_err_naive_cohort = abs(cohort_actual - naive_weighted)

                inside_p10_p90 = (p10 <= cohort_actual <= p90)
                inside_bear_bull = (bear_fcst <= cohort_actual <= bull_fcst)

                cohort_record = {
                    "quarter": q,
                    "horizon": horizon_name,
                    "snapshot_date": snap_date_str,
                    "cohort_actual_won": round(cohort_actual, 2),
                    "calibrated_forecast": round(base_fcst, 2),
                    "naive_weighted_pipeline": round(naive_weighted, 2),
                    "p10_conservative": round(p10, 2),
                    "p90_optimistic": round(p90, 2),
                    "bear_forecast": round(bear_fcst, 2),
                    "bull_forecast": round(bull_fcst, 2),
                    "abs_error_calibrated": round(abs_err_calib_cohort, 2),
                    "abs_error_naive": round(abs_err_naive_cohort, 2),
                    "inside_p10_p90": inside_p10_p90,
                    "inside_bear_bull": inside_bear_bull
                }
                cohort_evaluation_records.append(cohort_record)

                # Full quarter record
                abs_err_quarter = abs(total_quarter_actual - proj_quarter_total)
                abs_err_quarter_naive = abs(total_quarter_actual - proj_naive_total)
                quarter_total_records.append({
                    "quarter": q,
                    "horizon": horizon_name,
                    "snapshot_date": snap_date_str,
                    "closed_to_date": round(closed_to_date, 2),
                    "pipeline_forecast": round(base_fcst, 2),
                    "projected_total": round(proj_quarter_total, 2),
                    "actual_quarter_total": round(total_quarter_actual, 2),
                    "abs_error_projected": round(abs_err_quarter, 2),
                    "abs_error_naive": round(abs_err_quarter_naive, 2)
                })

        cohort_metrics = self._compute_aggregate_metrics(cohort_evaluation_records, actual_key="cohort_actual_won", pred_key="calibrated_forecast", naive_key="naive_weighted_pipeline", err_key="abs_error_calibrated", naive_err_key="abs_error_naive")
        quarter_metrics = self._compute_aggregate_metrics(quarter_total_records, actual_key="actual_quarter_total", pred_key="projected_total", naive_key="projected_total", err_key="abs_error_projected", naive_err_key="abs_error_naive")

        by_horizon: Dict[str, Any] = {}
        for h in ["90d", "60d", "30d"]:
            subset = [r for r in cohort_evaluation_records if r["horizon"] == h]
            if subset:
                by_horizon[h] = self._compute_aggregate_metrics(
                    subset,
                    actual_key="cohort_actual_won",
                    pred_key="calibrated_forecast",
                    naive_key="naive_weighted_pipeline",
                    err_key="abs_error_calibrated",
                    naive_err_key="abs_error_naive"
                )

        return {
            "cohort_evaluation_records": cohort_evaluation_records,
            "quarter_total_records": quarter_total_records,
            "cohort_accuracy_metrics": cohort_metrics,
            "quarter_reconciliation_metrics": quarter_metrics,
            "by_horizon_cohort_metrics": by_horizon,
            "total_evaluations_run": len(cohort_evaluation_records)
        }

    def _compute_aggregate_metrics(
        self,
        records: List[Dict[str, Any]],
        actual_key: str,
        pred_key: str,
        naive_key: str,
        err_key: str,
        naive_err_key: str
    ) -> Dict[str, Any]:
        """Calculates WAPE, MAPE, RMSE, Bias, and Interval Coverage."""
        if not records:
            return {}

        n = len(records)
        sum_actual = sum(r[actual_key] for r in records)
        sum_pred = sum(r[pred_key] for r in records)
        sum_naive = sum(r.get(naive_key, sum_pred) for r in records)

        sum_abs_err = sum(r[err_key] for r in records)
        sum_abs_err_naive = sum(r.get(naive_err_key, sum_abs_err) for r in records)

        # WAPE
        wape = sum_abs_err / sum_actual if sum_actual > 0 else 0.0
        wape_naive = sum_abs_err_naive / sum_actual if sum_actual > 0 else 0.0

        # MAPE
        valid_mapes = [r[err_key] / r[actual_key] for r in records if r[actual_key] > 0]
        mape = (sum(valid_mapes) / len(valid_mapes)) if valid_mapes else 0.0

        # RMSE
        rmse = math.sqrt(sum(r[err_key] ** 2 for r in records) / n)
        rmse_naive = math.sqrt(sum(r.get(naive_err_key, 0.0) ** 2 for r in records) / n)

        # Forecast Bias
        bias = (sum_pred / sum_actual) - 1.0 if sum_actual > 0 else 0.0
        bias_naive = (sum_naive / sum_actual) - 1.0 if sum_actual > 0 else 0.0

        # Interval Coverage
        p10_p90_cov = sum(1 for r in records if r.get("inside_p10_p90", False)) / n
        bear_bull_cov = sum(1 for r in records if r.get("inside_bear_bull", False)) / n

        return {
            "num_evaluations": n,
            "total_actual": round(sum_actual, 2),
            "total_forecast": round(sum_pred, 2),
            "model_metrics": {
                "wape": round(wape, 4),
                "mape": round(mape, 4),
                "rmse": round(rmse, 2),
                "bias": round(bias, 4),
                "p10_p90_coverage": round(p10_p90_cov, 4),
                "bear_bull_coverage": round(bear_bull_cov, 4)
            },
            "naive_benchmark": {
                "wape": round(wape_naive, 4),
                "rmse": round(rmse_naive, 2),
                "bias": round(bias_naive, 4)
            },
            "accuracy_improvement_vs_naive": {
                "wape_reduction_pct": round(max(0.0, (wape_naive - wape) / wape_naive * 100), 2) if wape_naive > 0 else 0.0,
                "rmse_reduction_pct": round(max(0.0, (rmse_naive - rmse) / rmse_naive * 100), 2) if rmse_naive > 0 else 0.0
            }
        }
