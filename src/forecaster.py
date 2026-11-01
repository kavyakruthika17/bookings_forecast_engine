"""
Enterprise Bookings Forecasting Engine with Scenario-Based Uncertainty.
Implements:
1. Absorbing Markov Chain for empirical stage conversion matrices.
2. Rep Activity Scoring (frequency, multi-touch variety, and sentiment).
3. Deal Age & Stagnation Hazard discounting.
4. Scenario Analysis (Base, Bull, Bear).
5. Monte Carlo Simulation for probabilistic distributions (P10, P50, P90, VaR).
6. Operational Decisions and Exception Engine for sales ops.
7. End-to-end traceability and audit trail.
"""

import math
import uuid
import datetime
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

from src.config import (
    STAGES,
    STAGE_LOOKUP,
    ACTIVITY_WEIGHTS,
    SCENARIO_CONFIGS,
    QUARTERS,
    QUARTER_DATE_RANGES
)


class BookingsForecastingEngine:
    """
    Forecasting engine that models deal conversion dynamics, rep activity uplift,
    deal aging decay, and scenario-based uncertainty.
    """

    def __init__(self, data: Dict[str, List[Dict[str, Any]]], random_seed: int = 20261022):
        self.data = data
        self.rng = np.random.default_rng(random_seed)
        self.run_id = f"RUN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"

        # State mapping
        self.transient_stages = ["STG-01-PROSPECT", "STG-02-DISCOV", "STG-03-PROP", "STG-04-NEGOT"]
        self.absorbing_stages = ["STG-05-WON", "STG-06-LOST"]
        self.all_stages = self.transient_stages + self.absorbing_stages

        # Calibrated matrices
        self.transition_matrix: Optional[np.ndarray] = None
        self.absorption_matrix: Optional[np.ndarray] = None
        self.stage_to_won_prob: Dict[str, float] = {}

        # Lookups
        self._build_lookups()

        # Fit Markov model from historical state transitions
        self.fit_markov_model()

    def _build_lookups(self):
        """Constructs fast in-memory indexing for deals, activities, and territories."""
        self.opp_map = {o["opportunity_id"]: o for o in self.data.get("opportunities", [])}
        self.territory_map = {t["territory_id"]: t for t in self.data.get("territories", [])}
        self.rep_map = {r["rep_id"]: r for r in self.data.get("sales_reps", [])}

        # Activity index by opp_id
        self.activities_by_opp: Dict[str, List[Dict[str, Any]]] = {}
        for act in self.data.get("activities", []):
            self.activities_by_opp.setdefault(act["opportunity_id"], []).append(act)

    # -------------------------------------------------------------------------
    # 1. Absorbing Markov Chain Historical Conversion
    # -------------------------------------------------------------------------

    def fit_markov_model(self):
        """
        Calculates the empirical transition probability matrix from StageHistory
        and solves the absorbing Markov chain for absorption probabilities into Closed Won.
        """
        n_trans = len(self.transient_stages)
        n_abs = len(self.absorbing_stages)

        stage_idx = {s: i for i, s in enumerate(self.all_stages)}
        counts = np.zeros((len(self.all_stages), len(self.all_stages)), dtype=float)

        for sh in self.data.get("stage_histories", []):
            from_stg = sh["from_stage_id"]
            to_stg = sh["to_stage_id"]
            if from_stg and from_stg in stage_idx and to_stg in stage_idx:
                counts[stage_idx[from_stg], stage_idx[to_stg]] += 1.0

        # Build transition matrix P
        P = np.zeros_like(counts)
        for i in range(len(self.all_stages)):
            row_sum = counts[i].sum()
            if row_sum > 0:
                P[i] = counts[i] / row_sum
            else:
                # If absorbing or no outward edges, state transitions to itself
                P[i, i] = 1.0

        # Sub-matrices
        Q = P[:n_trans, :n_trans]
        R = P[:n_trans, n_trans:]

        # Fundamental matrix: N = (I - Q)^(-1)
        I = np.eye(n_trans)
        try:
            N = np.linalg.inv(I - Q)
            B = N @ R  # Absorption probabilities
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse if singular
            N = np.linalg.pinv(I - Q)
            B = N @ R

        self.transition_matrix = P
        self.absorption_matrix = B

        # Map transient stage -> historical conversion probability to Closed Won (col 0 of R/B)
        for i, stg in enumerate(self.transient_stages):
            # Clip between 0.05 and 0.95
            won_p = float(np.clip(B[i, 0], 0.05, 0.95))
            self.stage_to_won_prob[stg] = round(won_p, 4)

        # Absorbing states have trivial absorption
        self.stage_to_won_prob["STG-05-WON"] = 1.00
        self.stage_to_won_prob["STG-06-LOST"] = 0.00

    # -------------------------------------------------------------------------
    # 2. Rep Activity Scoring & Deal Age Stagnation Adjustments
    # -------------------------------------------------------------------------

    def calculate_rep_activity_multiplier(self, opportunity_id: str, snapshot_date: datetime.date) -> Tuple[float, int, float]:
        """
        Calculates an activity multiplier M_act in [0.65, 1.30] based on
        engagement frequency, meeting variety, and sentiment in the 30-day window.
        Returns: (multiplier, activity_count_30d, weighted_activity_score)
        """
        acts = self.activities_by_opp.get(opportunity_id, [])
        window_start = snapshot_date - datetime.timedelta(days=30)
        recent_acts = [
            a for a in acts
            if window_start <= datetime.date.fromisoformat(a["activity_date"]) <= snapshot_date
        ]

        if not recent_acts:
            # Neglected deal penalty
            return 0.65, 0, 0.0

        score = 0.0
        for a in recent_acts:
            w = ACTIVITY_WEIGHTS.get(a["activity_type"], 1.0)
            sentiment_mod = 1.0 + 0.5 * a["sentiment_score"]
            score += w * sentiment_mod

        # Nonlinear scaling to multiplier
        # Score of 5.0 is neutral (1.0x). Score > 15 reaches 1.25x. Score < 2 drops to 0.75x.
        multiplier = 0.70 + 0.55 * (1.0 - math.exp(-score / 8.0))
        multiplier = float(np.clip(multiplier, 0.65, 1.30))

        return round(multiplier, 3), len(recent_acts), round(score, 2)

    def calculate_deal_age_hazard(self, stage_id: str, deal_age_days: int) -> Tuple[float, bool]:
        """
        Calculates stagnation decay factor based on time spent relative to target stage duration.
        Returns: (hazard_decay_factor, is_stale_flag)
        """
        stage_cfg = STAGE_LOOKUP.get(stage_id, {})
        target_days = stage_cfg.get("target_duration_days", 20)

        if stage_cfg.get("is_closed", False) or target_days == 0:
            return 1.0, False

        # If deal age exceeds target duration, decay kicks in
        excess_ratio = max(0.0, (deal_age_days - target_days) / float(target_days))
        decay_factor = math.exp(-0.25 * excess_ratio)
        decay_factor = float(np.clip(decay_factor, 0.40, 1.00))

        is_stale = (deal_age_days > 2.0 * target_days) or (deal_age_days > 60)
        return round(decay_factor, 3), is_stale

    # -------------------------------------------------------------------------
    # 3. Forecast Pipeline Evaluation at Snapshot Date
    # -------------------------------------------------------------------------

    def forecast_snapshot(
        self,
        snapshot_date_str: str,
        target_quarter: str,
        num_monte_carlo_runs: int = 500
    ) -> Dict[str, Any]:
        """
        Generates calibrated scenario forecasts and Monte Carlo distributions
        for all open opportunities closing in target_quarter as of snapshot_date.
        """
        snapshot_date = datetime.date.fromisoformat(snapshot_date_str)
        q_start_str, q_end_str = QUARTER_DATE_RANGES[target_quarter]
        q_start = datetime.date.fromisoformat(q_start_str)
        q_end = datetime.date.fromisoformat(q_end_str)

        # Filter snapshots matching this date
        snaps = [
            s for s in self.data.get("forecast_snapshots", [])
            if s["snapshot_date"] == snapshot_date_str
        ]

        deal_forecasts: List[Dict[str, Any]] = []
        exceptions: List[Dict[str, Any]] = []

        total_open_pipeline = 0.0
        total_weighted_pipeline = 0.0

        for s in snaps:
            opp_id = s["opportunity_id"]
            opp = self.opp_map.get(opp_id)
            if not opp:
                continue

            as_of_close = datetime.date.fromisoformat(s["as_of_close_date"])
            # Target quarter filtering
            if not (q_start <= as_of_close <= q_end):
                continue

            as_of_stage = s["as_of_stage_id"]
            amount = s["as_of_amount"]
            total_open_pipeline += amount
            total_weighted_pipeline += s["weighted_amount"]

            # 1. Base conversion from Markov model
            base_conversion = self.stage_to_won_prob.get(as_of_stage, s["stage_probability"])

            # 2. Activity multiplier
            act_mult, act_count, act_score = self.calculate_rep_activity_multiplier(opp_id, snapshot_date)

            # 3. Deal age hazard
            hazard_factor, is_stale = self.calculate_deal_age_hazard(as_of_stage, s["deal_age_days"])

            # Calibrated probability
            p_calibrated = float(np.clip(base_conversion * act_mult * hazard_factor, 0.02, 0.98))

            # Slippage hazard
            p_slippage = 0.15 + (0.25 if is_stale else 0.0) + (0.15 if act_count == 0 else 0.0)
            p_slippage = float(np.clip(p_slippage, 0.05, 0.75))

            # Scenario Probabilities
            p_base = p_calibrated
            p_bull = float(np.clip(p_calibrated * SCENARIO_CONFIGS["bull"]["conversion_multiplier"], 0.02, 0.99))
            p_bear = float(np.clip(p_calibrated * SCENARIO_CONFIGS["bear"]["conversion_multiplier"], 0.01, 0.90))

            slip_base = p_slippage
            slip_bull = float(np.clip(p_slippage * SCENARIO_CONFIGS["bull"]["slippage_hazard_multiplier"], 0.02, 0.60))
            slip_bear = float(np.clip(p_slippage * SCENARIO_CONFIGS["bear"]["slippage_hazard_multiplier"], 0.10, 0.90))

            deal_entry = {
                "opportunity_id": opp_id,
                "snapshot_id": s["snapshot_id"],
                "account_id": opp["account_id"],
                "rep_id": opp["rep_id"],
                "territory_id": opp["territory_id"],
                "segment": self.territory_map[opp["territory_id"]]["segment"],
                "as_of_stage": as_of_stage,
                "deal_age_days": s["deal_age_days"],
                "activity_count_30d": act_count,
                "activity_score": act_score,
                "amount": amount,
                "base_win_prob": round(p_base, 4),
                "bull_win_prob": round(p_bull, 4),
                "bear_win_prob": round(p_bear, 4),
                "slippage_prob": round(slip_base, 4),
                "expected_base_booking": round(amount * p_base * (1.0 - slip_base), 2),
                "expected_bull_booking": round(amount * p_bull * (1.0 - slip_bull), 2),
                "expected_bear_booking": round(amount * p_bear * (1.0 - slip_bear), 2),
            }
            deal_forecasts.append(deal_entry)

            # Identify Operational Exceptions
            if is_stale and amount >= 50000:
                exceptions.append({
                    "exception_id": f"EXC-STALE-{opp_id}",
                    "opportunity_id": opp_id,
                    "exception_type": "STALE_DEAL_EXCEPTION",
                    "severity": "HIGH" if amount >= 150000 else "MEDIUM",
                    "deal_amount": amount,
                    "stage": as_of_stage,
                    "deal_age_days": s["deal_age_days"],
                    "recommended_action": "Conduct deal triage; qualify out or schedule executive alignment"
                })

            if act_count == 0 and amount >= 75000:
                exceptions.append({
                    "exception_id": f"EXC-INACT-{opp_id}",
                    "opportunity_id": opp_id,
                    "exception_type": "REP_INACTIVITY_EXCEPTION",
                    "severity": "HIGH",
                    "deal_amount": amount,
                    "stage": as_of_stage,
                    "recommended_action": "Rep outreach required; no activity recorded in past 30 days"
                })

            if slip_base >= 0.40 and s["forecast_category"] == "Commit":
                exceptions.append({
                    "exception_id": f"EXC-SLIP-{opp_id}",
                    "opportunity_id": opp_id,
                    "exception_type": "SLIPPAGE_RISK_EXCEPTION",
                    "severity": "MEDIUM",
                    "deal_amount": amount,
                    "stage": as_of_stage,
                    "recommended_action": "Downgrade forecast category from Commit to Best Case due to slippage risk"
                })

        # ---------------------------------------------------------------------
        # 4. Monte Carlo Simulation for Probabilistic Distribution
        # ---------------------------------------------------------------------
        mc_base_totals = np.zeros(num_monte_carlo_runs)
        mc_bull_totals = np.zeros(num_monte_carlo_runs)
        mc_bear_totals = np.zeros(num_monte_carlo_runs)

        for d in deal_forecasts:
            amt = d["amount"]

            # Base simulation
            slips_base = self.rng.random(num_monte_carlo_runs) < d["slippage_prob"]
            wins_base = self.rng.random(num_monte_carlo_runs) < d["base_win_prob"]
            mc_base_totals += np.where(~slips_base & wins_base, amt, 0.0)

            # Bull simulation
            slips_bull = self.rng.random(num_monte_carlo_runs) < (d["slippage_prob"] * 0.75)
            wins_bull = self.rng.random(num_monte_carlo_runs) < d["bull_win_prob"]
            mc_bull_totals += np.where(~slips_bull & wins_bull, amt, 0.0)

            # Bear simulation
            slips_bear = self.rng.random(num_monte_carlo_runs) < min(0.9, d["slippage_prob"] * 1.40)
            wins_bear = self.rng.random(num_monte_carlo_runs) < d["bear_win_prob"]
            mc_bear_totals += np.where(~slips_bear & wins_bear, amt, 0.0)

        # Compute percentiles & metrics
        p10_base = float(np.percentile(mc_base_totals, 10))
        p50_base = float(np.percentile(mc_base_totals, 50))
        p90_base = float(np.percentile(mc_base_totals, 90))
        mean_base = float(np.mean(mc_base_totals))
        std_base = float(np.std(mc_base_totals))

        # Value at Risk at 95% confidence (Downside shortfall below median)
        var_95 = max(0.0, p50_base - float(np.percentile(mc_base_totals, 5)))

        # Aggregation by segment
        segment_breakdown: Dict[str, Dict[str, float]] = {}
        for seg in ["Enterprise", "Mid-Market", "SMB"]:
            seg_deals = [d for d in deal_forecasts if d["segment"] == seg]
            seg_pipe = sum(d["amount"] for d in seg_deals)
            seg_exp = sum(d["expected_base_booking"] for d in seg_deals)
            segment_breakdown[seg] = {
                "open_pipeline": round(seg_pipe, 2),
                "expected_bookings": round(seg_exp, 2),
                "deal_count": len(seg_deals)
            }

        return {
            "run_id": self.run_id,
            "snapshot_date": snapshot_date_str,
            "target_quarter": target_quarter,
            "num_deals_evaluated": len(deal_forecasts),
            "open_pipeline_total": round(total_open_pipeline, 2),
            "standard_weighted_pipeline": round(total_weighted_pipeline, 2),
            "scenario_forecasts": {
                "base": {
                    "expected_mean": round(mean_base, 2),
                    "std_deviation": round(std_base, 2),
                    "p10_conservative": round(p10_base, 2),
                    "p50_median": round(p50_base, 2),
                    "p90_optimistic": round(p90_base, 2),
                    "var_95_downside": round(var_95, 2)
                },
                "bull": {
                    "expected_mean": round(float(np.mean(mc_bull_totals)), 2),
                    "p50_median": round(float(np.percentile(mc_bull_totals, 50)), 2),
                    "p90_optimistic": round(float(np.percentile(mc_bull_totals, 90)), 2)
                },
                "bear": {
                    "expected_mean": round(float(np.mean(mc_bear_totals)), 2),
                    "p10_conservative": round(float(np.percentile(mc_bear_totals, 10)), 2),
                    "p50_median": round(float(np.percentile(mc_bear_totals, 50)), 2)
                }
            },
            "segment_breakdown": segment_breakdown,
            "operational_exceptions": exceptions,
            "evaluated_opp_ids": [d["opportunity_id"] for d in deal_forecasts],
            "deal_forecasts_sample": deal_forecasts[:10],
            "traceability": {
                "markov_absorption_probs": self.stage_to_won_prob,
                "activity_weights_applied": ACTIVITY_WEIGHTS,
                "monte_carlo_iterations": num_monte_carlo_runs
            }
        }
