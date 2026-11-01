"""
Data Exporter for Enterprise Bookings Forecasting.
Exports relational datasets to:
- CSV files (with standard headers and quoting)
- JSON files (records format)
- SQL DDL Schema and INSERT Seed Statements
Computes SHA-256 cryptographic checksums for manifest integrity and reproducibility verification.
"""

import os
import csv
import json
import hashlib
from typing import Dict, List, Any


class DataExporter:
    """
    Handles file serialization into CSV, JSON, and SQL formats,
    along with metadata manifest generation and checksum verification.
    """

    def __init__(self, data: Dict[str, List[Dict[str, Any]]], output_dir: str):
        self.data = data
        self.output_dir = output_dir
        self.csv_dir = os.path.join(output_dir, "csv")
        self.json_dir = os.path.join(output_dir, "json")
        self.sql_dir = os.path.join(output_dir, "sql")

        os.makedirs(self.csv_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.sql_dir, exist_ok=True)

    def export_all(self) -> Dict[str, Any]:
        """Exports all entities to CSV, JSON, SQL and generates cryptographic manifest."""
        manifest: Dict[str, Any] = {
            "tables": {},
            "generated_files": []
        }

        sql_schema_path = os.path.join(self.sql_dir, "01_schema.sql")
        sql_seeds_path = os.path.join(self.sql_dir, "02_seeds.sql")

        # Generate SQL Schema
        self._write_sql_schema(sql_schema_path)
        manifest["generated_files"].append({
            "path": sql_schema_path,
            "type": "SQL_SCHEMA",
            "sha256": self._compute_file_sha256(sql_schema_path)
        })

        sql_seed_file = open(sql_seeds_path, "w", encoding="utf-8")
        sql_seed_file.write("-- Enterprise Bookings Forecasting Seed Data\nBEGIN TRANSACTION;\n\n")

        for table_name, rows in self.data.items():
            if not rows:
                continue

            fieldnames = list(rows[0].keys())

            # 1. Export CSV
            csv_path = os.path.join(self.csv_dir, f"{table_name}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            csv_hash = self._compute_file_sha256(csv_path)

            # 2. Export JSON
            json_path = os.path.join(self.json_dir, f"{table_name}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)

            json_hash = self._compute_file_sha256(json_path)

            # 3. Append to SQL seeds
            self._append_sql_inserts(sql_seed_file, table_name, rows)

            manifest["tables"][table_name] = {
                "row_count": len(rows),
                "csv_file": csv_path,
                "csv_sha256": csv_hash,
                "json_file": json_path,
                "json_sha256": json_hash,
            }

        sql_seed_file.write("COMMIT;\n")
        sql_seed_file.close()

        sql_seeds_hash = self._compute_file_sha256(sql_seeds_path)
        manifest["generated_files"].append({
            "path": sql_seeds_path,
            "type": "SQL_SEEDS",
            "sha256": sql_seeds_hash
        })

        # Write manifest.json
        manifest_path = os.path.join(self.output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def _compute_file_sha256(self, filepath: str) -> str:
        """Computes SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _write_sql_schema(self, filepath: str):
        """Writes ANSI SQL DDL statements for all core entities."""
        ddl = """-- ============================================================================
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
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ddl)

    def _append_sql_inserts(self, f, table_name: str, rows: List[Dict[str, Any]]):
        """Writes bulk INSERT statements for a table."""
        if not rows:
            return

        cols = list(rows[0].keys())
        cols_str = ", ".join(cols)

        # Batch in groups of 500
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            val_clauses = []
            for r in batch:
                formatted_vals = []
                for c in cols:
                    v = r[c]
                    if v is None:
                        formatted_vals.append("NULL")
                    elif isinstance(v, bool):
                        formatted_vals.append("TRUE" if v else "FALSE")
                    elif isinstance(v, (int, float)):
                        formatted_vals.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        formatted_vals.append(f"'{escaped}'")
                val_clauses.append(f"({', '.join(formatted_vals)})")

            f.write(f"INSERT INTO {table_name} ({cols_str}) VALUES\n")
            f.write(",\n".join(val_clauses))
            f.write(";\n\n")
