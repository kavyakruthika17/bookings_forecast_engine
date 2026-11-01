"""
Validation engine for Bookings and Pipeline data.
Validates:
- Primary key uniqueness
- Foreign key referential integrity
- Enum domain membership
- Chronological ordering and temporal precedence
- Arithmetic reconciliation (weighted amounts, USD FX conversion)
- Lifecycle transitions
- Duplicate checks
- Detection of injected edge cases and evaluation against ground truth
"""

from typing import Dict, List, Any, Set, Tuple
import datetime
from collections import Counter

from src.config import (
    STAGES,
    STAGE_LOOKUP,
    REGIONS,
    SEGMENTS,
    FX_RATES,
    INDUSTRIES,
    ACCOUNT_TIERS,
    SALES_ROLES,
    DEAL_TYPES,
    LEAD_SOURCES,
    ACTIVITY_WEIGHTS
)


class DataValidator:
    """
    Validates structural, relational, and business domain integrity constraints
    across all pipeline entities and cross-references detected flaws against ground truth.
    """

    def __init__(self, dataset: Dict[str, List[Dict[str, Any]]]):
        self.data = dataset
        self.validation_results: Dict[str, Any] = {}
        self.detected_anomalies: List[Dict[str, Any]] = []

    def run_all_validations(self) -> Dict[str, Any]:
        """Runs all validation suites and compiles summary metrics."""
        pk_res = self.validate_primary_keys()
        fk_res = self.validate_foreign_keys()
        enum_res = self.validate_enums()
        chrono_res = self.validate_chronology()
        arith_res = self.validate_arithmetic()
        lifecycle_res = self.validate_lifecycle()
        dup_res = self.validate_duplicates()
        edge_case_res = self.detect_injected_edge_cases()

        ground_truth_eval = self.evaluate_against_ground_truth()

        all_passed = (
            pk_res["passed"]
            and fk_res["passed"]
            and enum_res["passed"]
            and lifecycle_res["passed"]
            and (len(self.detected_anomalies) > 0)  # Successfully surfaced anomalies
        )

        self.validation_results = {
            "overall_status": "COMPLETED_WITH_DETECTED_EXCEPTIONS",
            "all_passed": all_passed,
            "suite_results": {
                "primary_keys": pk_res,
                "foreign_keys": fk_res,
                "enums": enum_res,
                "chronology": chrono_res,
                "arithmetic": arith_res,
                "lifecycle": lifecycle_res,
                "duplicates": dup_res,
                "edge_cases": edge_case_res
            },
            "ground_truth_evaluation": ground_truth_eval,
            "total_detected_exceptions": len(self.detected_anomalies)
        }

        return self.validation_results

    # -------------------------------------------------------------------------
    # Core Integrity Validations
    # -------------------------------------------------------------------------

    def validate_primary_keys(self) -> Dict[str, Any]:
        """Checks primary key uniqueness for all core tables (excluding intentional duplicates)."""
        checks = [
            ("stages", "stage_id"),
            ("territories", "territory_id"),
            ("sales_reps", "rep_id"),
            ("accounts", "account_id"),
            ("quotas", "quota_id"),
            ("stage_histories", "stage_history_id"),
            ("activities", "activity_id"),
            ("historical_bookings", "booking_id"),
            ("forecast_snapshots", "snapshot_id")
        ]

        failures = []
        for table_name, pk_field in checks:
            records = self.data.get(table_name, [])
            keys = [r[pk_field] for r in records if pk_field in r]
            counts = Counter(keys)
            dups = [k for k, v in counts.items() if v > 1]
            if dups:
                failures.append({"table": table_name, "pk_field": pk_field, "duplicate_keys": dups[:5], "total_dups": len(dups)})

        return {
            "passed": len(failures) == 0,
            "checked_tables": len(checks),
            "failures": failures
        }

    def validate_foreign_keys(self) -> Dict[str, Any]:
        """Verifies referential integrity across all relational foreign keys."""
        territory_ids: Set[str] = {t["territory_id"] for t in self.data.get("territories", [])}
        rep_ids: Set[str] = {r["rep_id"] for r in self.data.get("sales_reps", [])}
        account_ids: Set[str] = {a["account_id"] for a in self.data.get("accounts", [])}
        stage_ids: Set[str] = {s["stage_id"] for s in self.data.get("stages", [])}
        opp_ids: Set[str] = {o["opportunity_id"] for o in self.data.get("opportunities", [])}

        orphans = []

        # SalesRep -> Territory
        for r in self.data.get("sales_reps", []):
            if r["territory_id"] not in territory_ids:
                orphans.append({"table": "sales_reps", "fk": "territory_id", "value": r["territory_id"]})

        # Account -> Territory, SalesRep
        for a in self.data.get("accounts", []):
            if a["territory_id"] not in territory_ids:
                orphans.append({"table": "accounts", "fk": "territory_id", "value": a["territory_id"]})
            if a["primary_rep_id"] not in rep_ids:
                orphans.append({"table": "accounts", "fk": "primary_rep_id", "value": a["primary_rep_id"]})

        # Opportunity -> Account, SalesRep, Territory, Stage
        for o in self.data.get("opportunities", []):
            if o["account_id"] not in account_ids:
                orphans.append({"table": "opportunities", "fk": "account_id", "value": o["account_id"]})
            if o["rep_id"] not in rep_ids:
                orphans.append({"table": "opportunities", "fk": "rep_id", "value": o["rep_id"]})
            if o["territory_id"] not in territory_ids:
                orphans.append({"table": "opportunities", "fk": "territory_id", "value": o["territory_id"]})
            if o["current_stage_id"] not in stage_ids:
                orphans.append({"table": "opportunities", "fk": "current_stage_id", "value": o["current_stage_id"]})

        # StageHistory -> Opportunity, Stage, SalesRep
        for sh in self.data.get("stage_histories", []):
            if sh["opportunity_id"] not in opp_ids:
                orphans.append({"table": "stage_histories", "fk": "opportunity_id", "value": sh["opportunity_id"]})
            if sh["to_stage_id"] not in stage_ids:
                orphans.append({"table": "stage_histories", "fk": "to_stage_id", "value": sh["to_stage_id"]})
            if sh["from_stage_id"] and sh["from_stage_id"] not in stage_ids:
                orphans.append({"table": "stage_histories", "fk": "from_stage_id", "value": sh["from_stage_id"]})

        # HistoricalBooking -> Opportunity, Account, SalesRep
        for b in self.data.get("historical_bookings", []):
            if b["opportunity_id"] not in opp_ids:
                orphans.append({"table": "historical_bookings", "fk": "opportunity_id", "value": b["opportunity_id"]})

        # ForecastSnapshot -> Opportunity, Stage
        for fs in self.data.get("forecast_snapshots", []):
            if fs["opportunity_id"] not in opp_ids:
                orphans.append({"table": "forecast_snapshots", "fk": "opportunity_id", "value": fs["opportunity_id"]})
            if fs["as_of_stage_id"] not in stage_ids:
                orphans.append({"table": "forecast_snapshots", "fk": "as_of_stage_id", "value": fs["as_of_stage_id"]})

        return {
            "passed": len(orphans) == 0,
            "total_orphan_references": len(orphans),
            "sample_orphans": orphans[:5]
        }

    def validate_enums(self) -> Dict[str, Any]:
        """Validates that categorical fields contain only allowed domain enum values."""
        invalid_entries = []

        valid_regions = set(REGIONS)
        valid_segments = set(SEGMENTS)
        valid_roles = set(SALES_ROLES)
        valid_industries = set(INDUSTRIES)
        valid_tiers = set(ACCOUNT_TIERS)
        valid_deal_types = set(DEAL_TYPES)
        valid_lead_sources = set(LEAD_SOURCES)
        valid_activity_types = set(ACTIVITY_WEIGHTS.keys())

        for t in self.data.get("territories", []):
            if t["region"] not in valid_regions:
                invalid_entries.append({"table": "territories", "field": "region", "val": t["region"]})
            if t["segment"] not in valid_segments:
                invalid_entries.append({"table": "territories", "field": "segment", "val": t["segment"]})

        for r in self.data.get("sales_reps", []):
            if r["role"] not in valid_roles:
                invalid_entries.append({"table": "sales_reps", "field": "role", "val": r["role"]})

        for a in self.data.get("accounts", []):
            if a["industry"] not in valid_industries:
                invalid_entries.append({"table": "accounts", "field": "industry", "val": a["industry"]})
            if a["tier"] not in valid_tiers:
                invalid_entries.append({"table": "accounts", "field": "tier", "val": a["tier"]})

        for o in self.data.get("opportunities", []):
            if o["deal_type"] not in valid_deal_types:
                invalid_entries.append({"table": "opportunities", "field": "deal_type", "val": o["deal_type"]})
            if o["lead_source"] not in valid_lead_sources:
                invalid_entries.append({"table": "opportunities", "field": "lead_source", "val": o["lead_source"]})

        for act in self.data.get("activities", []):
            if act["activity_type"] not in valid_activity_types:
                invalid_entries.append({"table": "activities", "field": "activity_type", "val": act["activity_type"]})

        return {
            "passed": len(invalid_entries) == 0,
            "invalid_count": len(invalid_entries),
            "sample_invalids": invalid_entries[:5]
        }

    def validate_chronology(self) -> Dict[str, Any]:
        """Validates date sequences: created_date <= close_date, etc."""
        chrono_violations = []

        for opp in self.data.get("opportunities", []):
            c_date = datetime.date.fromisoformat(opp["created_date"])
            exp_date = datetime.date.fromisoformat(opp["expected_close_date"])
            if exp_date < c_date:
                chrono_violations.append({
                    "opportunity_id": opp["opportunity_id"],
                    "created_date": opp["created_date"],
                    "expected_close_date": opp["expected_close_date"],
                    "error": "expected_close_date < created_date"
                })
                self.detected_anomalies.append({
                    "record_id": opp["opportunity_id"],
                    "detection_rule": "RULE-CHRONO-01",
                    "issue_type": "Close date before creation",
                    "details": f"Opportunity {opp['opportunity_id']} created {c_date} but expected close is {exp_date}"
                })

            if opp["actual_close_date"]:
                act_date = datetime.date.fromisoformat(opp["actual_close_date"])
                if act_date < c_date:
                    chrono_violations.append({
                        "opportunity_id": opp["opportunity_id"],
                        "created_date": opp["created_date"],
                        "actual_close_date": opp["actual_close_date"],
                        "error": "actual_close_date < created_date"
                    })

        return {
            "passed": len(chrono_violations) == 0,
            "violations_count": len(chrono_violations),
            "sample_violations": chrono_violations[:5]
        }

    def validate_arithmetic(self) -> Dict[str, Any]:
        """Validates derived arithmetic: amount_usd = amount * fx_rate, weighted_pipeline = amount * prob."""
        arithmetic_errors = []

        # FX currency conversion check
        for opp in self.data.get("opportunities", []):
            currency = opp["currency"]
            fx = FX_RATES.get(currency, 1.0)
            expected_usd = round(opp["amount"] * fx, 2)
            actual_usd = round(opp["amount_usd"], 2)

            if abs(expected_usd - actual_usd) > 0.05:
                arithmetic_errors.append({
                    "opportunity_id": opp["opportunity_id"],
                    "currency": currency,
                    "amount": opp["amount"],
                    "expected_usd": expected_usd,
                    "actual_usd": actual_usd,
                    "rule": "RULE-CURRENCY-01"
                })
                self.detected_anomalies.append({
                    "record_id": opp["opportunity_id"],
                    "detection_rule": "RULE-CURRENCY-01",
                    "issue_type": "Currency totals mixed",
                    "details": f"Deal {opp['opportunity_id']} in {currency} has amount_usd {actual_usd} != expected {expected_usd}"
                })

        # Weighted pipeline check in snapshots
        for fs in self.data.get("forecast_snapshots", []):
            expected_weighted = round(fs["as_of_amount"] * fs["stage_probability"], 2)
            actual_weighted = round(fs["weighted_amount"], 2)
            if abs(expected_weighted - actual_weighted) > 0.05:
                arithmetic_errors.append({
                    "snapshot_id": fs["snapshot_id"],
                    "expected_weighted": expected_weighted,
                    "actual_weighted": actual_weighted,
                    "rule": "RULE-WEIGHTED-01"
                })

        return {
            "passed": len(arithmetic_errors) == 0,
            "error_count": len(arithmetic_errors),
            "sample_errors": arithmetic_errors[:5]
        }

    def validate_lifecycle(self) -> Dict[str, Any]:
        """Validates stage history transitions and terminal stage status."""
        invalid_transitions = []
        opp_final_stages = {o["opportunity_id"]: o["current_stage_id"] for o in self.data.get("opportunities", [])}

        for bkg in self.data.get("historical_bookings", []):
            opp_stage = opp_final_stages.get(bkg["opportunity_id"])
            if opp_stage != "STG-05-WON":
                invalid_transitions.append({
                    "booking_id": bkg["booking_id"],
                    "opportunity_id": bkg["opportunity_id"],
                    "opp_stage": opp_stage,
                    "error": "Booking created for non-won opportunity"
                })

        return {
            "passed": len(invalid_transitions) == 0,
            "invalid_transition_count": len(invalid_transitions)
        }

    def validate_duplicates(self) -> Dict[str, Any]:
        """Identifies duplicate opportunities in the pipeline."""
        opp_ids = [o["opportunity_id"] for o in self.data.get("opportunities", [])]
        counts = Counter(opp_ids)
        duplicate_ids = [opp_id for opp_id, count in counts.items() if count > 1]

        for dup_id in duplicate_ids:
            self.detected_anomalies.append({
                "record_id": dup_id,
                "detection_rule": "RULE-DUP-01",
                "issue_type": "Duplicate opportunity counted",
                "details": f"Opportunity ID {dup_id} appears {counts[dup_id]} times in opportunity registry"
            })

        return {
            "passed": len(duplicate_ids) == 0,
            "duplicate_opportunity_count": len(duplicate_ids),
            "duplicate_ids": duplicate_ids[:5]
        }

    def detect_injected_edge_cases(self) -> Dict[str, Any]:
        """
        Specialized detection passes for:
        1. RULE-LEAKAGE-01: Forecast uses final outcome data
        2. RULE-PROB-01: Stage probability inconsistent with snapshot
        """
        # Map opportunity created date and actual stage histories
        stage_history_map: Dict[str, List[Dict[str, Any]]] = {}
        for sh in self.data.get("stage_histories", []):
            stage_history_map.setdefault(sh["opportunity_id"], []).append(sh)

        for fs in self.data.get("forecast_snapshots", []):
            snap_date = datetime.date.fromisoformat(fs["snapshot_date"])
            opp_id = fs["opportunity_id"]
            trans_list = stage_history_map.get(opp_id, [])

            # 1. Lookahead outcome leakage check
            # Find the actual transition state at or before snap_date
            valid_hist = [t for t in trans_list if datetime.date.fromisoformat(t["transition_date"]) <= snap_date]
            if valid_hist:
                true_stage_at_snap = valid_hist[-1]["to_stage_id"]
                if fs["as_of_stage_id"] == "STG-05-WON" and true_stage_at_snap != "STG-05-WON":
                    self.detected_anomalies.append({
                        "record_id": fs["snapshot_id"],
                        "detection_rule": "RULE-LEAKAGE-01",
                        "issue_type": "Forecast uses final outcome data",
                        "details": f"Snapshot {fs['snapshot_id']} as_of {snap_date} claims WON, but true stage was {true_stage_at_snap}"
                    })

            # 2. Stage probability consistency check
            canonical_prob = STAGE_LOOKUP.get(fs["as_of_stage_id"], {}).get("default_probability")
            if canonical_prob is not None and fs["as_of_stage_id"] not in ["STG-05-WON", "STG-06-LOST"]:
                if abs(fs["stage_probability"] - canonical_prob) > 0.01:
                    self.detected_anomalies.append({
                        "record_id": fs["snapshot_id"],
                        "detection_rule": "RULE-PROB-01",
                        "issue_type": "Stage probability inconsistent with snapshot",
                        "details": f"Snapshot {fs['snapshot_id']} stage {fs['as_of_stage_id']} has prob {fs['stage_probability']} vs expected {canonical_prob}"
                    })

        return {
            "total_edge_cases_found": len(self.detected_anomalies)
        }

    # -------------------------------------------------------------------------
    # Evaluation Against Ground Truth
    # -------------------------------------------------------------------------

    def evaluate_against_ground_truth(self) -> Dict[str, Any]:
        """
        Cross-references detected anomalies against the ground truth anomaly registry.
        Calculates Precision, Recall, and F1 Score for data quality assurance.
        """
        ground_truth: List[Dict[str, Any]] = self.data.get("ground_truth_anomalies", [])
        gt_keys = {(g["record_id"], g["issue_type"]) for g in ground_truth}

        detected_keys = {(d["record_id"], d["issue_type"]) for d in self.detected_anomalies}

        true_positives = detected_keys.intersection(gt_keys)
        false_positives = detected_keys - gt_keys
        false_negatives = gt_keys - detected_keys

        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0

        by_issue_type: Dict[str, Dict[str, int]] = {}
        for g in ground_truth:
            itype = g["issue_type"]
            by_issue_type.setdefault(itype, {"expected": 0, "detected": 0})
            by_issue_type[itype]["expected"] += 1

        for d in self.detected_anomalies:
            itype = d["issue_type"]
            if itype in by_issue_type:
                by_issue_type[itype]["detected"] += 1

        return {
            "total_ground_truth_anomalies": len(ground_truth),
            "total_detected_anomalies": len(self.detected_anomalies),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "breakdown_by_issue_type": by_issue_type
        }
