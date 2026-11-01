"""
Configuration module for the Enterprise Bookings Forecasting Engine.
Contains domain constants, canonical stage definitions, scenario parameters,
fixed random seeds, currency exchange rates, and scale presets.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Fixed deterministic default seed
DEFAULT_RANDOM_SEED = 20261022

# Canonical Sales Stages
STAGES: List[Dict] = [
    {
        "stage_id": "STG-01-PROSPECT",
        "stage_order": 1,
        "stage_name": "Prospecting",
        "default_probability": 0.10,
        "is_closed": False,
        "is_won": False,
        "target_duration_days": 15,
        "description": "Initial qualification, lead inquiry, and need identification"
    },
    {
        "stage_id": "STG-02-DISCOV",
        "stage_order": 2,
        "stage_name": "Discovery",
        "default_probability": 0.25,
        "is_closed": False,
        "is_won": False,
        "target_duration_days": 20,
        "description": "Scoping requirements, pain-point analysis, stakeholder mapping"
    },
    {
        "stage_id": "STG-03-PROP",
        "stage_order": 3,
        "stage_name": "Proposal",
        "default_probability": 0.50,
        "is_closed": False,
        "is_won": False,
        "target_duration_days": 30,
        "description": "Formal proposal, technical architecture, and preliminary quote presented"
    },
    {
        "stage_id": "STG-04-NEGOT",
        "stage_order": 4,
        "stage_name": "Negotiation",
        "default_probability": 0.75,
        "is_closed": False,
        "is_won": False,
        "target_duration_days": 20,
        "description": "Contract redlining, legal/procurement review, pricing finalization"
    },
    {
        "stage_id": "STG-05-WON",
        "stage_order": 5,
        "stage_name": "Closed Won",
        "default_probability": 1.00,
        "is_closed": True,
        "is_won": True,
        "target_duration_days": 0,
        "description": "Contract fully executed, PO issued, booking confirmed"
    },
    {
        "stage_id": "STG-06-LOST",
        "stage_order": 6,
        "stage_name": "Closed Lost",
        "default_probability": 0.00,
        "is_closed": True,
        "is_won": False,
        "target_duration_days": 0,
        "description": "Deal abandoned, lost to competitor, or cancelled by prospect"
    }
]

STAGE_LOOKUP = {s["stage_id"]: s for s in STAGES}

# Canonical Market Segments and Regions
REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]

# FX Rates to USD (Fixed baseline for deterministic normalization)
FX_RATES: Dict[str, float] = {
    "USD": 1.00,
    "EUR": 1.08,
    "GBP": 1.28,
    "SGD": 0.75
}

# Master Territory Definitions
TERRITORIES: List[Dict] = [
    {"territory_id": "TERR-001", "territory_name": "North America - Enterprise East", "region": "North America", "segment": "Enterprise", "currency": "USD", "target_growth_rate": 0.18},
    {"territory_id": "TERR-002", "territory_name": "North America - Enterprise West", "region": "North America", "segment": "Enterprise", "currency": "USD", "target_growth_rate": 0.22},
    {"territory_id": "TERR-003", "territory_name": "North America - Mid-Market Central", "region": "North America", "segment": "Mid-Market", "currency": "USD", "target_growth_rate": 0.15},
    {"territory_id": "TERR-004", "territory_name": "North America - Commercial SMB", "region": "North America", "segment": "SMB", "currency": "USD", "target_growth_rate": 0.12},
    {"territory_id": "TERR-005", "territory_name": "EMEA - UK & Ireland Enterprise", "region": "EMEA", "segment": "Enterprise", "currency": "GBP", "target_growth_rate": 0.16},
    {"territory_id": "TERR-006", "territory_name": "EMEA - DACH & Northern Europe", "region": "EMEA", "segment": "Enterprise", "currency": "EUR", "target_growth_rate": 0.14},
    {"territory_id": "TERR-007", "territory_name": "EMEA - Southern Europe Mid-Market", "region": "EMEA", "segment": "Mid-Market", "currency": "EUR", "target_growth_rate": 0.11},
    {"territory_id": "TERR-008", "territory_name": "APAC - ANZ & ASEAN Enterprise", "region": "APAC", "segment": "Enterprise", "currency": "SGD", "target_growth_rate": 0.25},
    {"territory_id": "TERR-009", "territory_name": "APAC - Growth Commercial", "region": "APAC", "segment": "Mid-Market", "currency": "USD", "target_growth_rate": 0.20},
    {"territory_id": "TERR-010", "territory_name": "LATAM - Strategic Accounts", "region": "LATAM", "segment": "Enterprise", "currency": "USD", "target_growth_rate": 0.17},
]

# Product Catalog
PRODUCT_FAMILIES = [
    "Cloud Platform",
    "Data & Analytics",
    "Security Suite",
    "AI & Automation"
]

# Account Industries & Tiers
INDUSTRIES = [
    "Technology",
    "Healthcare",
    "Financial Services",
    "Manufacturing",
    "Retail",
    "Energy"
]

ACCOUNT_TIERS = ["Strategic", "Tier-1", "Tier-2", "Tier-3"]

# Sales Roles
SALES_ROLES = [
    "Account Executive",
    "Senior AE",
    "Enterprise AE",
    "Sales Manager"
]

# Deal Types & Lead Sources
DEAL_TYPES = ["New Logo", "Expansion", "Renewal"]
LEAD_SOURCES = ["Inbound", "Outbound Rep", "Partner Referral", "Event"]

# Activity Types & Weights for Rep Engagement Scoring
ACTIVITY_WEIGHTS: Dict[str, float] = {
    "Call": 1.0,
    "Email": 0.5,
    "Demo": 3.0,
    "Executive Meeting": 4.5,
    "Technical Evaluation": 4.0
}

# Quarters in scope (8 Quarters: 2025Q1 through 2026Q4)
QUARTERS = [
    "2025Q1", "2025Q2", "2025Q3", "2025Q4",
    "2026Q1", "2026Q2", "2026Q3", "2026Q4"
]

QUARTER_DATE_RANGES: Dict[str, Tuple[str, str]] = {
    "2025Q1": ("2025-01-01", "2025-03-31"),
    "2025Q2": ("2025-04-01", "2025-06-30"),
    "2025Q3": ("2025-07-01", "2025-09-30"),
    "2025Q4": ("2025-10-01", "2025-12-31"),
    "2026Q1": ("2026-01-01", "2026-03-31"),
    "2026Q2": ("2026-04-01", "2026-06-30"),
    "2026Q3": ("2026-07-01", "2026-09-30"),
    "2026Q4": ("2026-10-01", "2026-12-31"),
}

# Monthly Snapshot Dates across 8 quarters (24 snapshots)
MONTHLY_SNAPSHOT_DATES = [
    "2025-01-31", "2025-02-28", "2025-03-31",
    "2025-04-30", "2025-05-31", "2025-06-30",
    "2025-07-31", "2025-08-31", "2025-09-30",
    "2025-10-31", "2025-11-30", "2025-12-31",
    "2026-01-31", "2026-02-28", "2026-03-31",
    "2026-04-30", "2026-05-31", "2026-06-30",
    "2026-07-31", "2026-08-31", "2026-09-30",
    "2026-10-31"  # Current reference cutoff date
]

# Scale Presets
@dataclass
class ScaleConfig:
    name: str
    num_reps: int
    num_accounts: int
    num_opportunities: int
    num_snapshots: int
    anomalies_per_type: int

SCALE_PRESETS = {
    "starter": ScaleConfig(
        name="starter",
        num_reps=200,
        num_accounts=200,
        num_opportunities=2000,
        num_snapshots=12,
        anomalies_per_type=5
    ),
    "full": ScaleConfig(
        name="full",
        num_reps=2000,
        num_accounts=2000,
        num_opportunities=20000,
        num_snapshots=22,
        anomalies_per_type=20
    )
}

# Required Edge Case Types
EDGE_CASE_TYPES = [
    "Forecast uses final outcome data",
    "Stage probability inconsistent with snapshot",
    "Duplicate opportunity counted",
    "Close date before creation",
    "Currency totals mixed"
]

# Uncertainty Scenario Parameters
SCENARIO_CONFIGS = {
    "base": {
        "conversion_multiplier": 1.00,
        "slippage_hazard_multiplier": 1.00,
        "deal_duration_factor": 1.00,
        "description": "Baseline empirical historical transition and activity rates"
    },
    "bull": {
        "conversion_multiplier": 1.15,
        "slippage_hazard_multiplier": 0.75,
        "deal_duration_factor": 0.88,
        "description": "Macro tailwinds, expedited procurement, +15% win rate lift, -25% slippage"
    },
    "bear": {
        "conversion_multiplier": 0.75,
        "slippage_hazard_multiplier": 1.40,
        "deal_duration_factor": 1.25,
        "description": "Budget freeze, delayed decision making, -25% win rate drop, +40% slippage"
    }
}
