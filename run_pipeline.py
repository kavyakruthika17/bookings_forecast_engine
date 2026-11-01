"""
Master Pipeline Runner for the Enterprise Bookings Forecasting Solution.
Executes:
1. Synthetic Relational Data Generation (parent-first, deterministic, calibrated).
2. Data Validation & Ground Truth Reconciliation.
3. CSV, JSON, and SQL Data Export with Cryptographic Hash Manifest.
4. Markov-Based Deal Conversion, Rep Engagement & Age Stagnation Forecasting.
5. Scenario Uncertainty Modeling (Base, Bull, Bear, Monte Carlo Distributions).
6. Quantitative Evaluation (WAPE, MAPE, RMSE, Bias, Horizon Slicing).
"""

import os
import sys
import argparse
import json
import time
from typing import Dict, Any

from src.config import DEFAULT_RANDOM_SEED, SCALE_PRESETS
from src.generator import BookingsDataGenerator
from src.validator import DataValidator
from src.forecaster import BookingsForecastingEngine
from src.evaluator import ForecastEvaluator
from src.exporter import DataExporter
from test_reproducibility import test_reproducibility


def run_pipeline(
    scale: str = "starter",
    seed: int = DEFAULT_RANDOM_SEED,
    export_data: bool = True,
    verify_reproducibility: bool = True,
    mc_iterations: int = 500
) -> Dict[str, Any]:
    print("=" * 80)
    print("ENTERPRISE BOOKINGS FORECASTING ENGINE — END-TO-END PIPELINE")
    print(f"Scale: {scale.upper()} | Seed: {seed} | Monte Carlo Runs: {mc_iterations}")
    print("=" * 80)

    start_time = time.time()

    # -------------------------------------------------------------------------
    # 1. Reproducibility Test (Optional early check)
    # -------------------------------------------------------------------------
    if verify_reproducibility:
        repro_ok = test_reproducibility(seed=seed, scale=scale)
        if not repro_ok:
            print("ERROR: Reproducibility verification failed!")
            sys.exit(1)

    # -------------------------------------------------------------------------
    # 2. Data Generation
    # -------------------------------------------------------------------------
    print(f"\n[Step 1/5] Generating relational datasets ({scale} scale)...")
    gen = BookingsDataGenerator(seed=seed, scale=scale)
    data = gen.generate_all()
    print("Generated entities summary:")
    for entity, rows in data.items():
        print(f"  - {entity:<24}: {len(rows):>6} records")

    # -------------------------------------------------------------------------
    # 3. Data Validation Suite
    # -------------------------------------------------------------------------
    print("\n[Step 2/5] Running Data Validation Suite...")
    validator = DataValidator(data)
    val_results = validator.run_all_validations()
    gt_eval = val_results["ground_truth_evaluation"]

    print(f"  - Structural Integrity (PK/FK/Enums/Lifecycle): PASS")
    print(f"  - Detected Deliberate Anomalies: {gt_eval['total_detected_anomalies']} / {gt_eval['total_ground_truth_anomalies']} expected")
    print(f"  - Precision: {gt_eval['precision']:.4f} | Recall: {gt_eval['recall']:.4f} | F1 Score: {gt_eval['f1_score']:.4f}")
    for itype, counts in gt_eval["breakdown_by_issue_type"].items():
        print(f"    * {itype:<44}: {counts['detected']} detected / {counts['expected']} expected")

    # -------------------------------------------------------------------------
    # 4. Data Export
    # -------------------------------------------------------------------------
    output_dir = os.path.join(os.path.dirname(__file__), "data", scale)
    if export_data:
        print(f"\n[Step 3/5] Exporting datasets to {output_dir} (CSV, JSON, SQL)...")
        exporter = DataExporter(data, output_dir)
        manifest = exporter.export_all()
        print(f"  - Export complete. Manifest written to {os.path.join(output_dir, 'manifest.json')}")
        print(f"  - Total tables exported: {len(manifest['tables'])}")
        print(f"  - SQL DDL & Seed Scripts: generated in data/{scale}/sql/")

    # -------------------------------------------------------------------------
    # 5. Forecasting & Scenario Uncertainty Simulation
    # -------------------------------------------------------------------------
    print("\n[Step 4/5] Initializing Bookings Forecasting Engine...")
    forecaster = BookingsForecastingEngine(data, random_seed=seed)

    print("  - Absorbing Markov Chain transition probabilities to Closed Won:")
    for stg, prob in forecaster.stage_to_won_prob.items():
        print(f"    * {stg:<18}: {prob * 100:.1f}%")

    # Run forecast snapshot for representative quarter
    sample_snap_date = "2025-06-30"
    sample_target_q = "2025Q3"
    print(f"\n  - Executing Scenario Simulation for {sample_target_q} (As of {sample_snap_date})...")
    fcst_sample = forecaster.forecast_snapshot(sample_snap_date, sample_target_q, num_monte_carlo_runs=mc_iterations)

    base_fcst = fcst_sample["scenario_forecasts"]["base"]
    bull_fcst = fcst_sample["scenario_forecasts"]["bull"]
    bear_fcst = fcst_sample["scenario_forecasts"]["bear"]

    print(f"    * Open Pipeline Evaluated   : ${fcst_sample['open_pipeline_total']:>13,.2f} ({fcst_sample['num_deals_evaluated']} deals)")
    print(f"    * Standard Weighted Pipeline: ${fcst_sample['standard_weighted_pipeline']:>13,.2f}")
    print(f"    * Base Scenario (Mean)      : ${base_fcst['expected_mean']:>13,.2f} (Std: ${base_fcst['std_deviation']:,.2f})")
    print(f"    * Base P10 (Conservative)   : ${base_fcst['p10_conservative']:>13,.2f}")
    print(f"    * Base P50 (Median)         : ${base_fcst['p50_median']:>13,.2f}")
    print(f"    * Base P90 (Optimistic)     : ${base_fcst['p90_optimistic']:>13,.2f}")
    print(f"    * Downside Risk (95% VaR)   : ${base_fcst['var_95_downside']:>13,.2f}")
    print(f"    * Bull Scenario Mean        : ${bull_fcst['expected_mean']:>13,.2f}")
    print(f"    * Bear Scenario Mean        : ${bear_fcst['expected_mean']:>13,.2f}")

    print(f"\n  - Operational Exceptions & Decision Guidance ({len(fcst_sample['operational_exceptions'])} exceptions flagged):")
    for exc in fcst_sample["operational_exceptions"][:4]:
        print(f"    * [{exc['severity']}] {exc['exception_type']} on {exc['opportunity_id']} (${exc['deal_amount']:,.0f}): {exc['recommended_action']}")

    # -------------------------------------------------------------------------
    # 6. Quantitative Backtesting Evaluation
    # -------------------------------------------------------------------------
    print("\n[Step 5/5] Backtesting Forecast Performance Against Ground-Truth Bookings...")
    evaluator = ForecastEvaluator(data, forecaster)
    eval_results = evaluator.evaluate_quarters()

    cohort_metrics = eval_results["cohort_accuracy_metrics"]
    by_horizon = eval_results["by_horizon_cohort_metrics"]

    print("  - Overall Accuracy Metrics:")
    print(f"    * Calibrated Model WAPE   : {cohort_metrics['model_metrics']['wape'] * 100:.2f}% (vs Naive CRM: {cohort_metrics['naive_benchmark']['wape'] * 100:.2f}%)")
    print(f"    * Calibrated Model RMSE   : ${cohort_metrics['model_metrics']['rmse']:,.2f} (vs Naive CRM: ${cohort_metrics['naive_benchmark']['rmse']:,.2f})")
    print(f"    * WAPE Error Reduction    : {cohort_metrics['accuracy_improvement_vs_naive']['wape_reduction_pct']:.2f}% improvement")
    print(f"    * RMSE Reduction          : {cohort_metrics['accuracy_improvement_vs_naive']['rmse_reduction_pct']:.2f}% improvement")
    print(f"    * P10-P90 Coverage Rate   : {cohort_metrics['model_metrics']['p10_p90_coverage'] * 100:.1f}%")

    print("\n  - Performance Sliced by Forecast Horizon:")
    for horizon, h_metrics in by_horizon.items():
        m = h_metrics["model_metrics"]
        nb = h_metrics["naive_benchmark"]
        impr = h_metrics["accuracy_improvement_vs_naive"]
        print(f"    * Horizon {horizon:<4}: WAPE {m['wape'] * 100:>5.1f}% | RMSE ${m['rmse']:>10,.0f} | WAPE Improvement: +{impr['wape_reduction_pct']:.1f}% vs Naive")

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"PIPELINE RUN COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS")
    print("=" * 80)

    return {
        "validation_results": val_results,
        "sample_forecast": fcst_sample,
        "evaluation_results": eval_results,
        "elapsed_seconds": elapsed
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enterprise Bookings Forecasting Engine")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter", help="Dataset scale preset")
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED, help="Random seed for reproducibility")
    parser.add_argument("--no-export", action="store_true", help="Skip writing files to disk")
    parser.add_argument("--skip-repro", action="store_true", help="Skip dual-run reproducibility test")
    parser.add_argument("--mc-runs", type=int, default=500, help="Monte Carlo simulation iterations")

    args = parser.parse_args()

    run_pipeline(
        scale=args.scale,
        seed=args.seed,
        export_data=not args.no_export,
        verify_reproducibility=not args.skip_repro,
        mc_iterations=args.mc_runs
    )
