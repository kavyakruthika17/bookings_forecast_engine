"""
Synthetic Data Generator for Enterprise Bookings Forecasting.
Generates master data first, followed by dependent event and transaction data,
computes all derived metrics deterministically, and injects labelled anomalies
into a separate ground truth repository.
"""

import copy
import datetime
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

from src.config import (
    DEFAULT_RANDOM_SEED,
    STAGES,
    STAGE_LOOKUP,
    TERRITORIES,
    PRODUCT_FAMILIES,
    INDUSTRIES,
    ACCOUNT_TIERS,
    SALES_ROLES,
    DEAL_TYPES,
    LEAD_SOURCES,
    FX_RATES,
    ACTIVITY_WEIGHTS,
    QUARTERS,
    QUARTER_DATE_RANGES,
    MONTHLY_SNAPSHOT_DATES,
    SCALE_PRESETS,
    ScaleConfig,
    EDGE_CASE_TYPES
)
from src.models import (
    TerritoryRecord,
    SalesRepRecord,
    AccountRecord,
    StageRecord,
    OpportunityRecord,
    StageHistoryRecord,
    ActivityRecord,
    QuotaRecord,
    HistoricalBookingRecord,
    ForecastSnapshotRecord,
    GroundTruthAnomalyRecord
)


class BookingsDataGenerator:
    """
    Deterministic synthetic data generator producing relational enterprise pipeline
    and bookings data across 8 fiscal quarters.
    """

    def __init__(self, seed: int = DEFAULT_RANDOM_SEED, scale: str = "starter", custom_scale: Optional[ScaleConfig] = None):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        if custom_scale:
            self.scale_config = custom_scale
        else:
            self.scale_config = SCALE_PRESETS.get(scale, SCALE_PRESETS["starter"])

        # Generated data containers
        self.territories: List[TerritoryRecord] = []
        self.sales_reps: List[SalesRepRecord] = []
        self.accounts: List[AccountRecord] = []
        self.stages: List[StageRecord] = []
        self.opportunities: List[OpportunityRecord] = []
        self.stage_histories: List[StageHistoryRecord] = []
        self.activities: List[ActivityRecord] = []
        self.quotas: List[QuotaRecord] = []
        self.historical_bookings: List[HistoricalBookingRecord] = []
        self.forecast_snapshots: List[ForecastSnapshotRecord] = []
        self.ground_truth_anomalies: List[GroundTruthAnomalyRecord] = []

        self._anomaly_counter = 0

    def generate_all(self) -> Dict[str, Any]:
        """
        Executes parent-first data generation pipeline and injects edge cases.
        """
        # Step 1: Master / Reference Data
        self._generate_stages()
        self._generate_territories()
        self._generate_sales_reps()
        self._generate_accounts()
        self._generate_quotas()

        # Step 2: Dependent Transactions, Events & Histories
        self._generate_opportunities_and_histories()
        self._generate_activities()
        self._generate_historical_bookings()
        self._generate_forecast_snapshots()

        # Step 3: Inject Labelled Anomalies (Separated in Ground Truth)
        self._inject_edge_cases()

        return {
            "stages": [s.to_dict() for s in self.stages],
            "territories": [t.to_dict() for t in self.territories],
            "sales_reps": [r.to_dict() for r in self.sales_reps],
            "accounts": [a.to_dict() for a in self.accounts],
            "quotas": [q.to_dict() for q in self.quotas],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "stage_histories": [sh.to_dict() for sh in self.stage_histories],
            "activities": [act.to_dict() for act in self.activities],
            "historical_bookings": [b.to_dict() for b in self.historical_bookings],
            "forecast_snapshots": [f.to_dict() for f in self.forecast_snapshots],
            "ground_truth_anomalies": [g.to_dict() for g in self.ground_truth_anomalies],
        }

    # -------------------------------------------------------------------------
    # Master / Reference Table Generation
    # -------------------------------------------------------------------------

    def _generate_stages(self):
        """Generates canonical sales stage records."""
        self.stages = [
            StageRecord(
                stage_id=s["stage_id"],
                stage_order=s["stage_order"],
                stage_name=s["stage_name"],
                default_probability=s["default_probability"],
                is_closed=s["is_closed"],
                is_won=s["is_won"],
                target_duration_days=s["target_duration_days"],
                description=s["description"]
            )
            for s in STAGES
        ]

    def _generate_territories(self):
        """Generates master sales territory definitions."""
        self.territories = [
            TerritoryRecord(
                territory_id=t["territory_id"],
                territory_name=t["territory_name"],
                region=t["region"],
                segment=t["segment"],
                currency=t["currency"],
                target_growth_rate=t["target_growth_rate"]
            )
            for t in TERRITORIES
        ]

    def _generate_sales_reps(self):
        """Generates sales representatives assigned across territories."""
        first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Sam", "Chris", "Pat",
                       "Daniel", "Emma", "Liam", "Olivia", "Noah", "Ava", "Sophia", "Lucas", "Mia", "Ethan"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
                      "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore"]

        num_reps = self.scale_config.num_reps
        num_territories = len(self.territories)

        base_date = datetime.date(2026, 10, 31)
        min_hire_date = datetime.date(2019, 1, 1)

        for i in range(1, num_reps + 1):
            rep_id = f"REP-{i:06d}"
            fname = first_names[int(self.rng.integers(0, len(first_names)))]
            lname = last_names[int(self.rng.integers(0, len(last_names)))]
            name = f"{fname} {lname}"
            email = f"{fname.lower()}.{lname.lower()}_{i}@enterprise-sales.internal"

            role_idx = self.rng.choice(len(SALES_ROLES), p=[0.45, 0.30, 0.15, 0.10])
            role = SALES_ROLES[role_idx]

            territory = self.territories[i % num_territories]
            territory_id = territory.territory_id

            # Hire date within 2019-01-01 to 2026-06-30
            days_offset = int(self.rng.integers(0, (datetime.date(2026, 6, 30) - min_hire_date).days))
            hire_date = min_hire_date + datetime.timedelta(days=days_offset)
            tenure_months = max(1, (base_date.year - hire_date.year) * 12 + (base_date.month - hire_date.month))

            # Base annual quota scaled by role and segment
            segment_multiplier = {"Enterprise": 1.5, "Mid-Market": 1.0, "SMB": 0.6}[territory.segment]
            role_base = {"Account Executive": 600000.0, "Senior AE": 900000.0, "Enterprise AE": 1400000.0, "Sales Manager": 2000000.0}[role]
            base_quota = round(role_base * segment_multiplier, 2)

            status = "Active" if self.rng.random() < 0.95 else ("On Leave" if self.rng.random() < 0.6 else "Terminated")

            self.sales_reps.append(
                SalesRepRecord(
                    rep_id=rep_id,
                    name=name,
                    email=email,
                    role=role,
                    territory_id=territory_id,
                    hire_date=hire_date.isoformat(),
                    base_quota=base_quota,
                    tenure_months=tenure_months,
                    status=status
                )
            )

    def _generate_accounts(self):
        """Generates customer accounts linked to territories and assigned sales reps."""
        num_accounts = self.scale_config.num_accounts
        num_territories = len(self.territories)
        num_reps = len(self.sales_reps)

        account_prefixes = ["Apex", "Quantum", "Vertex", "Horizon", "Strata", "Aero", "Pulse", "Nexus",
                            "Summit", "Beacon", "Sol", "Vanguard", "Synergy", "Optima", "Pinnacle"]
        account_suffixes = ["Technologies", "Holdings", "Global", "Systems", "Health", "Capital",
                            "Logistics", "Enterprises", "Industries", "Solutions", "Networks", "Energy"]

        min_create_date = datetime.date(2020, 1, 1)

        for i in range(1, num_accounts + 1):
            account_id = f"ACC-{i:06d}"
            prefix = account_prefixes[int(self.rng.integers(0, len(account_prefixes)))]
            suffix = account_suffixes[int(self.rng.integers(0, len(account_suffixes)))]
            account_name = f"{prefix} {suffix} {i:04d}"

            industry = str(self.rng.choice(INDUSTRIES))
            territory = self.territories[i % num_territories]
            territory_id = territory.territory_id

            # Assign a rep from the same territory if available
            territory_reps = [r for r in self.sales_reps if r.territory_id == territory_id]
            if territory_reps:
                primary_rep_id = territory_reps[i % len(territory_reps)].rep_id
            else:
                primary_rep_id = self.sales_reps[i % num_reps].rep_id

            # Account tier, revenue and employees
            tier = str(self.rng.choice(ACCOUNT_TIERS, p=[0.10, 0.25, 0.40, 0.25]))
            if tier == "Strategic":
                annual_revenue = round(float(self.rng.uniform(100e6, 2e9)), 2)
                employee_count = int(self.rng.integers(5000, 75000))
            elif tier == "Tier-1":
                annual_revenue = round(float(self.rng.uniform(25e6, 100e6)), 2)
                employee_count = int(self.rng.integers(1000, 5000))
            elif tier == "Tier-2":
                annual_revenue = round(float(self.rng.uniform(5e6, 25e6)), 2)
                employee_count = int(self.rng.integers(250, 1000))
            else:
                annual_revenue = round(float(self.rng.uniform(1e6, 5e6)), 2)
                employee_count = int(self.rng.integers(20, 250))

            days_offset = int(self.rng.integers(0, (datetime.date(2024, 10, 31) - min_create_date).days))
            created_at = min_create_date + datetime.timedelta(days=days_offset)

            self.accounts.append(
                AccountRecord(
                    account_id=account_id,
                    account_name=account_name,
                    industry=industry,
                    territory_id=territory_id,
                    primary_rep_id=primary_rep_id,
                    annual_revenue=annual_revenue,
                    employee_count=employee_count,
                    tier=tier,
                    created_at=created_at.isoformat()
                )
            )

    def _generate_quotas(self):
        """Generates quarterly quotas across 8 quarters for each active sales rep."""
        quarter_weights = {
            "2025Q1": 0.20, "2025Q2": 0.24, "2025Q3": 0.22, "2025Q4": 0.34,
            "2026Q1": 0.21, "2026Q2": 0.25, "2026Q3": 0.23, "2026Q4": 0.36
        }

        for rep in self.sales_reps:
            annual_quota = rep.base_quota
            for quarter, (q_start, q_end) in QUARTER_DATE_RANGES.items():
                quota_id = f"QUOTA-{rep.rep_id}-{quarter}"
                weight = quarter_weights[quarter]
                quarter_quota = round(annual_quota * (weight / 1.0), 2)

                self.quotas.append(
                    QuotaRecord(
                        quota_id=quota_id,
                        rep_id=rep.rep_id,
                        fiscal_quarter=quarter,
                        quota_amount=quarter_quota,
                        effective_start_date=q_start,
                        effective_end_date=q_end
                    )
                )

    # -------------------------------------------------------------------------
    # Dependent Event & Transaction Generation
    # -------------------------------------------------------------------------

    def _generate_opportunities_and_histories(self):
        """
        Generates opportunities with realistic lifecycle trajectories, stage histories,
        seasonality, deal slippage, and temporal consistency.
        """
        num_opps = self.scale_config.num_opportunities
        num_accounts = len(self.accounts)
        territory_map = {t.territory_id: t for t in self.territories}
        account_map = {a.account_id: a for a in self.accounts}

        min_opp_date = datetime.date(2024, 11, 1)
        max_opp_date = datetime.date(2026, 10, 31)
        total_days = (max_opp_date - min_opp_date).days

        stage_sequence = ["STG-01-PROSPECT", "STG-02-DISCOV", "STG-03-PROP", "STG-04-NEGOT"]

        for i in range(1, num_opps + 1):
            opp_id = f"OPP-2026-{i:06d}"
            account = self.accounts[int(self.rng.integers(0, num_accounts))]
            territory = territory_map[account.territory_id]
            rep_id = account.primary_rep_id

            product_family = str(self.rng.choice(PRODUCT_FAMILIES))
            deal_type = str(self.rng.choice(DEAL_TYPES, p=[0.55, 0.30, 0.15]))
            lead_source = str(self.rng.choice(LEAD_SOURCES, p=[0.40, 0.30, 0.20, 0.10]))

            # Calibrated lognormal deal size by segment
            segment = territory.segment
            if segment == "Enterprise":
                mean_log, sigma = np.log(250000), 0.65
            elif segment == "Mid-Market":
                mean_log, sigma = np.log(75000), 0.50
            else:  # SMB
                mean_log, sigma = np.log(20000), 0.45

            raw_amount = float(self.rng.lognormal(mean_log, sigma))
            amount = round(max(5000.0, min(raw_amount, 2000000.0)), 2)
            currency = territory.currency
            fx_rate = FX_RATES[currency]
            amount_usd = round(amount * fx_rate, 2)

            # Opportunity creation date
            acc_created = datetime.date.fromisoformat(account.created_at)
            start_date_bound = max(min_opp_date, acc_created)
            avail_days = max(1, (max_opp_date - start_date_bound).days)
            created_date = start_date_bound + datetime.timedelta(days=int(self.rng.integers(0, avail_days)))

            # Planned duration and expected close date
            standard_cycle_days = int(self.rng.normal(65, 18))
            standard_cycle_days = max(20, min(standard_cycle_days, 150))
            expected_close_date = created_date + datetime.timedelta(days=standard_cycle_days)

            # Deal Slippage Simulation (25% probability of close date slipping)
            slippage_count = 0
            if self.rng.random() < 0.25:
                slip_days = int(self.rng.choice([30, 45, 60, 90]))
                expected_close_date += datetime.timedelta(days=slip_days)
                slippage_count += 1
                if self.rng.random() < 0.30:  # Multi-slippage
                    expected_close_date += datetime.timedelta(days=30)
                    slippage_count += 1

            # Simulate stage progression history
            curr_date = created_date
            history_records: List[StageHistoryRecord] = []
            prev_stage_id: Optional[str] = None

            # Determine progression depth
            # Probability of winning is ~28% overall, lost is ~47%, still open ~25%
            seasonality_boost = 0.08 if expected_close_date.month in [10, 11, 12] else 0.0
            p_won_target = 0.26 + seasonality_boost

            outcome_roll = self.rng.random()
            if outcome_roll < p_won_target:
                final_state = "WON"
            elif outcome_roll < (p_won_target + 0.48):
                final_state = "LOST"
            else:
                final_state = "OPEN"

            current_stage_idx = 0
            actual_close_date: Optional[str] = None
            is_closed = False

            # Initial creation stage history
            hist_id_0 = f"STG-{opp_id}-001"
            first_stage = stage_sequence[0]
            history_records.append(
                StageHistoryRecord(
                    stage_history_id=hist_id_0,
                    opportunity_id=opp_id,
                    from_stage_id=None,
                    to_stage_id=first_stage,
                    transition_date=created_date.isoformat(),
                    days_in_previous_stage=0,
                    changed_by_rep_id=rep_id,
                    transition_reason="Opportunity Initial Qualification"
                )
            )

            # Traverse stages
            for step_idx in range(1, len(stage_sequence)):
                stage_cfg = STAGE_LOOKUP[stage_sequence[step_idx - 1]]
                duration_in_stage = max(3, int(self.rng.normal(stage_cfg["target_duration_days"], 5)))
                next_date = curr_date + datetime.timedelta(days=duration_in_stage)

                if next_date > max_opp_date:
                    # Still open at cutoff
                    break

                # Check if deal is lost midway
                if final_state == "LOST" and step_idx >= int(self.rng.integers(1, 4)):
                    is_closed = True
                    hist_id = f"STG-{opp_id}-{len(history_records)+1:03d}"
                    history_records.append(
                        StageHistoryRecord(
                            stage_history_id=hist_id,
                            opportunity_id=opp_id,
                            from_stage_id=stage_sequence[step_idx - 1],
                            to_stage_id="STG-06-LOST",
                            transition_date=next_date.isoformat(),
                            days_in_previous_stage=duration_in_stage,
                            changed_by_rep_id=rep_id,
                            transition_reason=str(self.rng.choice(["Budget Cut", "Competitor Selected", "No Project Authority", "Timing Delayed"]))
                        )
                    )
                    actual_close_date = next_date.isoformat()
                    current_stage_id = "STG-06-LOST"
                    break

                # Advance to next open stage
                hist_id = f"STG-{opp_id}-{len(history_records)+1:03d}"
                history_records.append(
                    StageHistoryRecord(
                        stage_history_id=hist_id,
                        opportunity_id=opp_id,
                        from_stage_id=stage_sequence[step_idx - 1],
                        to_stage_id=stage_sequence[step_idx],
                        transition_date=next_date.isoformat(),
                        days_in_previous_stage=duration_in_stage,
                        changed_by_rep_id=rep_id,
                        transition_reason="Pipeline Milestone Achieved"
                    )
                )
                curr_date = next_date
                current_stage_idx = step_idx
            else:
                # Reached end of sequence (Negotiation)
                if not is_closed:
                    last_stage_cfg = STAGE_LOOKUP["STG-04-NEGOT"]
                    closing_duration = max(5, int(self.rng.normal(last_stage_cfg["target_duration_days"], 6)))
                    terminal_date = curr_date + datetime.timedelta(days=closing_duration)

                    if terminal_date <= max_opp_date:
                        is_closed = True
                        actual_close_date = terminal_date.isoformat()
                        if final_state == "WON":
                            current_stage_id = "STG-05-WON"
                            hist_id = f"STG-{opp_id}-{len(history_records)+1:03d}"
                            history_records.append(
                                StageHistoryRecord(
                                    stage_history_id=hist_id,
                                    opportunity_id=opp_id,
                                    from_stage_id="STG-04-NEGOT",
                                    to_stage_id="STG-05-WON",
                                    transition_date=terminal_date.isoformat(),
                                    days_in_previous_stage=closing_duration,
                                    changed_by_rep_id=rep_id,
                                    transition_reason="Contract Signed - Deal Won"
                                )
                            )
                        else:
                            current_stage_id = "STG-06-LOST"
                            hist_id = f"STG-{opp_id}-{len(history_records)+1:03d}"
                            history_records.append(
                                StageHistoryRecord(
                                    stage_history_id=hist_id,
                                    opportunity_id=opp_id,
                                    from_stage_id="STG-04-NEGOT",
                                    to_stage_id="STG-06-LOST",
                                    transition_date=terminal_date.isoformat(),
                                    days_in_previous_stage=closing_duration,
                                    changed_by_rep_id=rep_id,
                                    transition_reason="Contract Redlines Abandoned"
                                )
                            )
                    else:
                        current_stage_id = "STG-04-NEGOT"

            if not is_closed:
                current_stage_id = stage_sequence[current_stage_idx]

            # Determine status
            if current_stage_id == "STG-05-WON":
                status = "Won"
            elif current_stage_id == "STG-06-LOST":
                status = "Lost"
            else:
                status = "Open"
                actual_close_date = None

            # Calculate deal age
            end_calc_date = datetime.date.fromisoformat(actual_close_date) if actual_close_date else max_opp_date
            deal_age_days = max(0, (end_calc_date - created_date).days)

            opp_rec = OpportunityRecord(
                opportunity_id=opp_id,
                account_id=account.account_id,
                rep_id=rep_id,
                territory_id=territory.territory_id,
                product_family=product_family,
                deal_type=deal_type,
                lead_source=lead_source,
                amount=amount,
                currency=currency,
                amount_usd=amount_usd,
                created_date=created_date.isoformat(),
                expected_close_date=expected_close_date.isoformat(),
                actual_close_date=actual_close_date,
                current_stage_id=current_stage_id,
                status=status,
                deal_age_days=deal_age_days,
                slippage_count=slippage_count
            )

            self.opportunities.append(opp_rec)
            self.stage_histories.extend(history_records)

    def _generate_activities(self):
        """
        Generates realistic interaction events (Calls, Emails, Demos, Exec Meetings)
        logged against open and completed opportunities.
        """
        activity_counter = 1
        act_types = list(ACTIVITY_WEIGHTS.keys())
        outcomes = ["Completed", "Rescheduled", "No Show"]

        for opp in self.opportunities:
            opp_created = datetime.date.fromisoformat(opp.created_date)
            opp_end = datetime.date.fromisoformat(opp.actual_close_date) if opp.actual_close_date else datetime.date(2026, 10, 31)
            duration_days = max(1, (opp_end - opp_created).days)

            # Activity frequency depends on deal size and segment
            if opp.amount_usd > 200000:
                num_acts = int(self.rng.integers(6, 18))
            elif opp.amount_usd > 50000:
                num_acts = int(self.rng.integers(3, 10))
            else:
                num_acts = int(self.rng.integers(1, 6))

            # Simulate stale deals (10% of deals have zero activity after the first 10 days)
            is_stale = (self.rng.random() < 0.10) and (opp.status == "Open")
            if is_stale:
                num_acts = 1

            for _ in range(num_acts):
                act_id = f"ACT-{activity_counter:07d}"
                activity_counter += 1

                act_type = str(self.rng.choice(act_types, p=[0.40, 0.35, 0.12, 0.08, 0.05]))
                duration = int(self.rng.choice([15, 30, 45, 60, 90]))

                # Date of activity within lifespan
                day_offset = int(self.rng.integers(0, min(15 if is_stale else duration_days, duration_days)))
                act_date = opp_created + datetime.timedelta(days=day_offset)

                # Sentiment score: won deals trend positive, lost trend neutral/negative
                if opp.status == "Won":
                    sentiment = round(float(np.clip(self.rng.normal(0.60, 0.25), -1.0, 1.0)), 2)
                elif opp.status == "Lost":
                    sentiment = round(float(np.clip(self.rng.normal(-0.20, 0.35), -1.0, 1.0)), 2)
                else:
                    sentiment = round(float(np.clip(self.rng.normal(0.25, 0.30), -1.0, 1.0)), 2)

                outcome = str(self.rng.choice(outcomes, p=[0.88, 0.08, 0.04]))

                self.activities.append(
                    ActivityRecord(
                        activity_id=act_id,
                        opportunity_id=opp.opportunity_id,
                        rep_id=opp.rep_id,
                        activity_type=act_type,
                        activity_date=act_date.isoformat(),
                        duration_minutes=duration,
                        sentiment_score=sentiment,
                        outcome=outcome
                    )
                )

    def _generate_historical_bookings(self):
        """
        Creates historical bookings for confirmed Closed Won opportunities.
        Guarantees 1:1 join integrity with won deals.
        """
        bkg_counter = 1
        for opp in self.opportunities:
            if opp.current_stage_id == "STG-05-WON" and opp.actual_close_date:
                close_dt = datetime.date.fromisoformat(opp.actual_close_date)
                quarter = f"{close_dt.year}Q{(close_dt.month - 1) // 3 + 1}"

                bkg_id = f"BKG-{close_dt.year}-{bkg_counter:06d}"
                bkg_counter += 1

                booking_type = f"{opp.deal_type} ARR"

                self.historical_bookings.append(
                    HistoricalBookingRecord(
                        booking_id=bkg_id,
                        opportunity_id=opp.opportunity_id,
                        account_id=opp.account_id,
                        rep_id=opp.rep_id,
                        territory_id=opp.territory_id,
                        booked_date=opp.actual_close_date,
                        fiscal_quarter=quarter,
                        booking_amount=opp.amount_usd,
                        currency="USD",
                        booking_type=booking_type
                    )
                )

    def _generate_forecast_snapshots(self):
        """
        Snapshots pipeline state at periodic fixed freeze dates across the 8 quarters.
        Reconstructs the exact state of deals as of snapshot date without future leakage.
        """
        # Build quick stage transition lookup: opp_id -> list of transitions sorted by date
        history_by_opp: Dict[str, List[StageHistoryRecord]] = {}
        for sh in self.stage_histories:
            history_by_opp.setdefault(sh.opportunity_id, []).append(sh)

        for opp_id in history_by_opp:
            history_by_opp[opp_id].sort(key=lambda x: x.transition_date)

        # Build activity lookup: (opp_id, date)
        activities_by_opp: Dict[str, List[datetime.date]] = {}
        for act in self.activities:
            activities_by_opp.setdefault(act.opportunity_id, []).append(
                datetime.date.fromisoformat(act.activity_date)
            )

        snapshot_dates = MONTHLY_SNAPSHOT_DATES[:self.scale_config.num_snapshots]
        snap_counter = 1

        for snap_date_str in snapshot_dates:
            snap_date = datetime.date.fromisoformat(snap_date_str)

            for opp in self.opportunities:
                opp_created = datetime.date.fromisoformat(opp.created_date)
                if opp_created > snap_date:
                    # Deal did not exist yet at this snapshot
                    continue

                # Find stage as of snapshot date
                transitions = history_by_opp.get(opp.opportunity_id, [])
                valid_transitions = [t for t in transitions if datetime.date.fromisoformat(t.transition_date) <= snap_date]

                if not valid_transitions:
                    continue

                latest_trans = valid_transitions[-1]
                as_of_stage_id = latest_trans.to_stage_id

                # Only snapshot deals that are OPEN as of snapshot date
                stage_cfg = STAGE_LOOKUP[as_of_stage_id]
                if stage_cfg["is_closed"]:
                    continue

                # As of deal age
                deal_age_days = (snap_date - opp_created).days

                # Activity count in last 30 days
                opp_act_dates = activities_by_opp.get(opp.opportunity_id, [])
                window_start = snap_date - datetime.timedelta(days=30)
                acts_30d = sum(1 for d in opp_act_dates if window_start <= d <= snap_date)

                stage_prob = stage_cfg["default_probability"]
                as_of_amount = opp.amount_usd
                weighted_amount = round(as_of_amount * stage_prob, 2)

                # Forecast category
                if stage_prob >= 0.75:
                    category = "Commit"
                elif stage_prob >= 0.50:
                    category = "Best Case"
                else:
                    category = "Pipeline"

                snap_id = f"FCST-{snap_date_str}-{snap_counter:06d}"
                snap_counter += 1

                self.forecast_snapshots.append(
                    ForecastSnapshotRecord(
                        snapshot_id=snap_id,
                        snapshot_date=snap_date_str,
                        opportunity_id=opp.opportunity_id,
                        as_of_stage_id=as_of_stage_id,
                        as_of_amount=as_of_amount,
                        as_of_close_date=opp.expected_close_date,
                        deal_age_days=deal_age_days,
                        activity_count_last_30d=acts_30d,
                        stage_probability=stage_prob,
                        weighted_amount=weighted_amount,
                        forecast_category=category
                    )
                )

    # -------------------------------------------------------------------------
    # Edge Cases & Labelled Anomaly Injection (Step 5 & 7)
    # -------------------------------------------------------------------------

    def _inject_edge_cases(self):
        """
        Injects the 5 required domain edge cases into copies or records,
        preserving original truth inside the separate ground_truth_anomalies repository.
        """
        k = self.scale_config.anomalies_per_type

        # 1. Forecast uses final outcome data (Lookahead bias leakage)
        # Select snapshots of open deals that eventually WON in the future, and prematurely mark them WON in snapshot.
        won_opp_ids = {o.opportunity_id for o in self.opportunities if o.current_stage_id == "STG-05-WON"}
        candidate_snaps_1 = [
            s for s in self.forecast_snapshots
            if s.opportunity_id in won_opp_ids and s.as_of_stage_id in ["STG-02-DISCOV", "STG-03-PROP"]
        ]
        target_snaps_1 = candidate_snaps_1[:k]
        for s in target_snaps_1:
            clean_stage = s.as_of_stage_id
            clean_prob = s.stage_probability
            # Corrupt record
            s.as_of_stage_id = "STG-05-WON"
            s.stage_probability = 1.00
            s.weighted_amount = s.as_of_amount
            s.forecast_category = "Closed"

            self._record_anomaly(
                record_id=s.snapshot_id,
                entity_type="ForecastSnapshot",
                issue_type="Forecast uses final outcome data",
                description="Snapshot incorporates final outcome Closed Won stage prematurely before actual close timestamp",
                injected_field="as_of_stage_id",
                expected_clean_value=f"{clean_stage}|{clean_prob}",
                observed_corrupt_value="STG-05-WON|1.00",
                detection_rule="RULE-LEAKAGE-01"
            )

        # 2. Stage probability inconsistent with snapshot
        # Take snapshot records and set stage_probability to an inconsistent/fabricated value
        candidate_snaps_2 = [
            s for s in self.forecast_snapshots
            if s.as_of_stage_id == "STG-04-NEGOT" and s not in target_snaps_1
        ]
        target_snaps_2 = candidate_snaps_2[:k]
        for s in target_snaps_2:
            clean_prob = s.stage_probability
            corrupt_prob = 0.20  # Inconsistent with Negotiation default 0.75
            s.stage_probability = corrupt_prob
            s.weighted_amount = round(s.as_of_amount * corrupt_prob, 2)

            self._record_anomaly(
                record_id=s.snapshot_id,
                entity_type="ForecastSnapshot",
                issue_type="Stage probability inconsistent with snapshot",
                description="Opportunity in Negotiation stage assigned an invalid 20% probability instead of standard 75%",
                injected_field="stage_probability",
                expected_clean_value=str(clean_prob),
                observed_corrupt_value=str(corrupt_prob),
                detection_rule="RULE-PROB-01"
            )

        # 3. Duplicate opportunity counted
        # Duplicate an opportunity record in pipeline snapshots or duplicate opportunity ID
        candidate_opps_3 = [o for o in self.opportunities if o.status == "Open"][:k]
        for opp in candidate_opps_3:
            # Clone opportunity record with duplicate ID
            dup_opp = copy.deepcopy(opp)
            self.opportunities.append(dup_opp)

            self._record_anomaly(
                record_id=opp.opportunity_id,
                entity_type="Opportunity",
                issue_type="Duplicate opportunity counted",
                description="Duplicate opportunity record injected with identical opportunity_id causing double-counting",
                injected_field="opportunity_id",
                expected_clean_value="UNIQUE",
                observed_corrupt_value=f"DUPLICATE_{opp.opportunity_id}",
                detection_rule="RULE-DUP-01"
            )

        # 4. Close date before creation
        # Opportunity has expected_close_date or actual_close_date set before created_date
        candidate_opps_4 = [
            o for o in self.opportunities if o.opportunity_id not in [x.opportunity_id for x in candidate_opps_3]
        ][:k]
        for opp in candidate_opps_4:
            clean_date = opp.expected_close_date
            created_dt = datetime.date.fromisoformat(opp.created_date)
            corrupt_date = (created_dt - datetime.timedelta(days=30)).isoformat()
            opp.expected_close_date = corrupt_date

            self._record_anomaly(
                record_id=opp.opportunity_id,
                entity_type="Opportunity",
                issue_type="Close date before creation",
                description="Expected close date chronologically precedes opportunity creation date",
                injected_field="expected_close_date",
                expected_clean_value=clean_date,
                observed_corrupt_value=corrupt_date,
                detection_rule="RULE-CHRONO-01"
            )

        # 5. Currency totals mixed
        # Foreign currency deal (EUR/GBP) has its local amount written directly into amount_usd without FX conversion
        candidate_opps_5 = [
            o for o in self.opportunities
            if o.currency in ["EUR", "GBP"] and o not in candidate_opps_3 and o not in candidate_opps_4
        ][:k]
        for opp in candidate_opps_5:
            clean_amount_usd = opp.amount_usd
            corrupt_amount_usd = opp.amount  # 1:1 mapping ignoring FX rate!
            opp.amount_usd = corrupt_amount_usd

            self._record_anomaly(
                record_id=opp.opportunity_id,
                entity_type="Opportunity",
                issue_type="Currency totals mixed",
                description=f"Local {opp.currency} amount aggregated directly as USD without applying FX exchange rate multiplier",
                injected_field="amount_usd",
                expected_clean_value=str(clean_amount_usd),
                observed_corrupt_value=str(corrupt_amount_usd),
                detection_rule="RULE-CURRENCY-01"
            )

    def _record_anomaly(
        self,
        record_id: str,
        entity_type: str,
        issue_type: str,
        description: str,
        injected_field: str,
        expected_clean_value: str,
        observed_corrupt_value: str,
        detection_rule: str
    ):
        """Appends a labelled ground-truth anomaly entry."""
        self._anomaly_counter += 1
        anom_id = f"ANOM-{self._anomaly_counter:06d}"
        self.ground_truth_anomalies.append(
            GroundTruthAnomalyRecord(
                anomaly_id=anom_id,
                record_id=record_id,
                entity_type=entity_type,
                issue_type=issue_type,
                description=description,
                injected_field=injected_field,
                expected_clean_value=expected_clean_value,
                observed_corrupt_value=observed_corrupt_value,
                detection_rule=detection_rule
            )
        )
