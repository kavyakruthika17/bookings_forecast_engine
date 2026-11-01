"""
Unit and Integration Test Suite for the Enterprise Bookings Forecasting Engine.
Tests:
- Generator schema adherence and ID conventions
- Chronological monotonicity and temporal constraints
- Separation of ground truth anomalies from input features
- Validator detection precision, recall, and edge case coverage
- Absorbing Markov chain mathematical properties
- Rep activity scoring bounds and stale deal hazards
- Exact deterministic reproducibility
"""

import unittest
import datetime
import numpy as np

from src.config import DEFAULT_RANDOM_SEED, STAGES, STAGE_LOOKUP
from src.generator import BookingsDataGenerator
from src.validator import DataValidator
from src.forecaster import BookingsForecastingEngine
from src.evaluator import ForecastEvaluator
from test_reproducibility import test_reproducibility, compute_table_sha256


class TestBookingsForecastEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = BookingsDataGenerator(seed=DEFAULT_RANDOM_SEED, scale="starter")
        cls.data = cls.generator.generate_all()
        cls.forecaster = BookingsForecastingEngine(cls.data, random_seed=DEFAULT_RANDOM_SEED)

    def test_id_nomenclature_conventions(self):
        """Verifies strict nomenclature rules from specifications."""
        # SalesRep: REP-000001
        rep = self.data["sales_reps"][0]
        self.assertTrue(rep["rep_id"].startswith("REP-"))
        self.assertEqual(len(rep["rep_id"]), 10)

        # Opportunity: OPP-2026-000001
        opp = self.data["opportunities"][0]
        self.assertTrue(opp["opportunity_id"].startswith("OPP-2026-"))

        # StageHistory: STG-OPP-2026-000001-001
        sh = self.data["stage_histories"][0]
        self.assertTrue(sh["stage_history_id"].startswith("STG-OPP-"))

        # Quota: QUOTA-REP-000001-2025Q1
        quota = self.data["quotas"][0]
        self.assertTrue(quota["quota_id"].startswith("QUOTA-REP-"))

        # ForecastSnapshot: FCST-2025-01-31-000001
        fs = self.data["forecast_snapshots"][0]
        self.assertTrue(fs["snapshot_id"].startswith("FCST-"))

    def test_chronological_ordering(self):
        """Verifies that stage transitions are chronologically ordered."""
        opp_histories = {}
        for sh in self.data["stage_histories"]:
            opp_histories.setdefault(sh["opportunity_id"], []).append(sh)

        for opp_id, transitions in opp_histories.items():
            dates = [datetime.date.fromisoformat(t["transition_date"]) for t in transitions]
            # Ensure non-decreasing transition dates
            for i in range(len(dates) - 1):
                self.assertLessEqual(dates[i], dates[i + 1])

    def test_ground_truth_isolation(self):
        """Verifies ground truth anomalies are recorded in dedicated table and not leaked."""
        gt = self.data.get("ground_truth_anomalies", [])
        self.assertGreater(len(gt), 0)
        # Verify no ground truth fields exist on opportunities table
        sample_opp = self.data["opportunities"][0]
        self.assertNotIn("issue_type", sample_opp)
        self.assertNotIn("detection_rule", sample_opp)
        self.assertNotIn("expected_clean_value", sample_opp)

    def test_validator_detects_all_anomalies(self):
        """Verifies validator achieves 100% precision and recall on injected anomalies."""
        validator = DataValidator(self.data)
        results = validator.run_all_validations()
        gt_eval = results["ground_truth_evaluation"]

        self.assertEqual(gt_eval["precision"], 1.0)
        self.assertEqual(gt_eval["recall"], 1.0)
        self.assertEqual(gt_eval["f1_score"], 1.0)
        self.assertEqual(gt_eval["false_positives"], 0)
        self.assertEqual(gt_eval["false_negatives"], 0)

    def test_markov_conversion_matrix(self):
        """Verifies Markov transition matrix and absorption probabilities."""
        P = self.forecaster.transition_matrix
        self.assertIsNotNone(P)
        # Check that rows sum to 1.0
        row_sums = P.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-5)

        # Check absorption probabilities: Stage 4 (Negotiation) > Stage 1 (Prospecting)
        prob_prospect = self.forecaster.stage_to_won_prob["STG-01-PROSPECT"]
        prob_negot = self.forecaster.stage_to_won_prob["STG-04-NEGOT"]
        self.assertGreater(prob_negot, prob_prospect)

        # Terminal stages
        self.assertEqual(self.forecaster.stage_to_won_prob["STG-05-WON"], 1.0)
        self.assertEqual(self.forecaster.stage_to_won_prob["STG-06-LOST"], 0.0)

    def test_rep_activity_bounds(self):
        """Verifies activity multiplier is clamped within [0.65, 1.30]."""
        snap_dt = datetime.date(2025, 6, 30)
        for opp in self.data["opportunities"][:50]:
            mult, count, score = self.forecaster.calculate_rep_activity_multiplier(opp["opportunity_id"], snap_dt)
            self.assertGreaterEqual(mult, 0.65)
            self.assertLessEqual(mult, 1.30)

    def test_scenario_uncertainty_ordering(self):
        """Verifies that Bull >= Base >= Bear in scenario simulation."""
        res = self.forecaster.forecast_snapshot("2025-06-30", "2025Q3", num_monte_carlo_runs=200)
        base = res["scenario_forecasts"]["base"]["expected_mean"]
        bull = res["scenario_forecasts"]["bull"]["expected_mean"]
        bear = res["scenario_forecasts"]["bear"]["expected_mean"]

        self.assertGreaterEqual(bull, base)
        self.assertGreaterEqual(base, bear)

    def test_deterministic_reproducibility(self):
        """Verifies 100% reproducible row counts and hashes across runs."""
        repro_ok = test_reproducibility(seed=DEFAULT_RANDOM_SEED, scale="starter")
        self.assertTrue(repro_ok)


if __name__ == "__main__":
    unittest.main()
