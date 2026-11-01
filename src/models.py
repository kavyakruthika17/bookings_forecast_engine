"""
Data models and dataclasses for all 10 core entities plus GroundTruth anomalies.
Ensures strong typing, serialization to dictionary, and strict validation.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any


@dataclass
class TerritoryRecord:
    territory_id: str
    territory_name: str
    region: str
    segment: str
    currency: str
    target_growth_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SalesRepRecord:
    rep_id: str
    name: str
    email: str
    role: str
    territory_id: str
    hire_date: str
    base_quota: float
    tenure_months: int
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AccountRecord:
    account_id: str
    account_name: str
    industry: str
    territory_id: str
    primary_rep_id: str
    annual_revenue: float
    employee_count: int
    tier: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StageRecord:
    stage_id: str
    stage_order: int
    stage_name: str
    default_probability: float
    is_closed: bool
    is_won: bool
    target_duration_days: int
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunityRecord:
    opportunity_id: str
    account_id: str
    rep_id: str
    territory_id: str
    product_family: str
    deal_type: str
    lead_source: str
    amount: float
    currency: str
    amount_usd: float
    created_date: str
    expected_close_date: str
    actual_close_date: Optional[str]
    current_stage_id: str
    status: str
    deal_age_days: int
    slippage_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StageHistoryRecord:
    stage_history_id: str
    opportunity_id: str
    from_stage_id: Optional[str]
    to_stage_id: str
    transition_date: str
    days_in_previous_stage: int
    changed_by_rep_id: str
    transition_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActivityRecord:
    activity_id: str
    opportunity_id: str
    rep_id: str
    activity_type: str
    activity_date: str
    duration_minutes: int
    sentiment_score: float
    outcome: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuotaRecord:
    quota_id: str
    rep_id: str
    fiscal_quarter: str
    quota_amount: float
    effective_start_date: str
    effective_end_date: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HistoricalBookingRecord:
    booking_id: str
    opportunity_id: str
    account_id: str
    rep_id: str
    territory_id: str
    booked_date: str
    fiscal_quarter: str
    booking_amount: float
    currency: str
    booking_type: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForecastSnapshotRecord:
    snapshot_id: str
    snapshot_date: str
    opportunity_id: str
    as_of_stage_id: str
    as_of_amount: float
    as_of_close_date: str
    deal_age_days: int
    activity_count_last_30d: int
    stage_probability: float
    weighted_amount: float
    forecast_category: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundTruthAnomalyRecord:
    anomaly_id: str
    record_id: str
    entity_type: str
    issue_type: str
    description: str
    injected_field: str
    expected_clean_value: str
    observed_corrupt_value: str
    detection_rule: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
