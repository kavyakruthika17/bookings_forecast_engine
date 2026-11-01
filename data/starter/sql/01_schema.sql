-- ============================================================================
-- Enterprise Bookings Forecasting Schema DDL
-- ============================================================================

CREATE TABLE IF NOT EXISTS stages (
    stage_id VARCHAR(16) PRIMARY KEY,
    stage_order INTEGER NOT NULL UNIQUE,
    stage_name VARCHAR(32) NOT NULL UNIQUE,
    default_probability DECIMAL(3,2) NOT NULL,
    is_closed BOOLEAN NOT NULL,
    is_won BOOLEAN NOT NULL,
    target_duration_days INTEGER NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS territories (
    territory_id VARCHAR(16) PRIMARY KEY,
    territory_name VARCHAR(64) NOT NULL UNIQUE,
    region VARCHAR(32) NOT NULL,
    segment VARCHAR(32) NOT NULL,
    currency CHAR(3) NOT NULL,
    target_growth_rate DECIMAL(5,4) NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_reps (
    rep_id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    role VARCHAR(32) NOT NULL,
    territory_id VARCHAR(16) NOT NULL REFERENCES territories(territory_id),
    hire_date DATE NOT NULL,
    base_quota DECIMAL(12,2) NOT NULL,
    tenure_months INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id VARCHAR(16) PRIMARY KEY,
    account_name VARCHAR(128) NOT NULL,
    industry VARCHAR(32) NOT NULL,
    territory_id VARCHAR(16) NOT NULL REFERENCES territories(territory_id),
    primary_rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    annual_revenue DECIMAL(14,2) NOT NULL,
    employee_count INTEGER NOT NULL,
    tier VARCHAR(16) NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS quotas (
    quota_id VARCHAR(32) PRIMARY KEY,
    rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    fiscal_quarter CHAR(6) NOT NULL,
    quota_amount DECIMAL(12,2) NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id VARCHAR(24) NOT NULL,
    account_id VARCHAR(16) NOT NULL REFERENCES accounts(account_id),
    rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    territory_id VARCHAR(16) NOT NULL REFERENCES territories(territory_id),
    product_family VARCHAR(32) NOT NULL,
    deal_type VARCHAR(16) NOT NULL,
    lead_source VARCHAR(32) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    amount_usd DECIMAL(12,2) NOT NULL,
    created_date DATE NOT NULL,
    expected_close_date DATE NOT NULL,
    actual_close_date DATE,
    current_stage_id VARCHAR(16) NOT NULL REFERENCES stages(stage_id),
    status VARCHAR(16) NOT NULL,
    deal_age_days INTEGER NOT NULL,
    slippage_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_histories (
    stage_history_id VARCHAR(36) PRIMARY KEY,
    opportunity_id VARCHAR(24) NOT NULL,
    from_stage_id VARCHAR(16) REFERENCES stages(stage_id),
    to_stage_id VARCHAR(16) NOT NULL REFERENCES stages(stage_id),
    transition_date DATE NOT NULL,
    days_in_previous_stage INTEGER NOT NULL,
    changed_by_rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    transition_reason TEXT
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id VARCHAR(20) PRIMARY KEY,
    opportunity_id VARCHAR(24) NOT NULL,
    rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    activity_type VARCHAR(32) NOT NULL,
    activity_date DATE NOT NULL,
    duration_minutes INTEGER NOT NULL,
    sentiment_score DECIMAL(3,2) NOT NULL,
    outcome VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS historical_bookings (
    booking_id VARCHAR(24) PRIMARY KEY,
    opportunity_id VARCHAR(24) NOT NULL,
    account_id VARCHAR(16) NOT NULL REFERENCES accounts(account_id),
    rep_id VARCHAR(16) NOT NULL REFERENCES sales_reps(rep_id),
    territory_id VARCHAR(16) NOT NULL REFERENCES territories(territory_id),
    booked_date DATE NOT NULL,
    fiscal_quarter CHAR(6) NOT NULL,
    booking_amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    booking_type VARCHAR(24) NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    snapshot_id VARCHAR(32) PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    opportunity_id VARCHAR(24) NOT NULL,
    as_of_stage_id VARCHAR(16) NOT NULL REFERENCES stages(stage_id),
    as_of_amount DECIMAL(12,2) NOT NULL,
    as_of_close_date DATE NOT NULL,
    deal_age_days INTEGER NOT NULL,
    activity_count_last_30d INTEGER NOT NULL,
    stage_probability DECIMAL(3,2) NOT NULL,
    weighted_amount DECIMAL(12,2) NOT NULL,
    forecast_category VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS ground_truth_anomalies (
    anomaly_id VARCHAR(24) PRIMARY KEY,
    record_id VARCHAR(36) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    issue_type VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    injected_field VARCHAR(32) NOT NULL,
    expected_clean_value TEXT NOT NULL,
    observed_corrupt_value TEXT NOT NULL,
    detection_rule VARCHAR(32) NOT NULL
);
