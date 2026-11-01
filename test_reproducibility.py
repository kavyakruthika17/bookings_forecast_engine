"""
Reproducibility Verification Suite.
Regenerates data twice from scratch with fixed seed 20261022,
computes cryptographic SHA-256 hashes of all generated tables,
and asserts identical row counts and byte-for-byte reproducibility.
"""

import sys
import json
import hashlib
from typing import Dict, Any, List

from src.generator import BookingsDataGenerator
from src.config import DEFAULT_RANDOM_SEED


def compute_table_sha256(rows: List[Dict[str, Any]]) -> str:
    """Computes SHA-256 digest of canonically serialized JSON rows."""
    serialized = json.dumps(rows, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def test_reproducibility(seed: int = DEFAULT_RANDOM_SEED, scale: str = "starter") -> bool:
    print("=" * 80)
    print(f"REPRODUCIBILITY VERIFICATION: Dual-Run Test (Seed: {seed}, Scale: {scale})")
    print("=" * 80)

    print("\n[Run 1/2] Initializing Generator and creating synthetic dataset...")
    gen1 = BookingsDataGenerator(seed=seed, scale=scale)
    data1 = gen1.generate_all()

    print("[Run 2/2] Initializing Fresh Generator and creating independent dataset...")
    gen2 = BookingsDataGenerator(seed=seed, scale=scale)
    data2 = gen2.generate_all()

    tables = list(data1.keys())
    all_match = True

    print(f"\n{'Table Name':<26} | {'Run 1 Rows':<10} | {'Run 2 Rows':<10} | {'Run 1 SHA-256 (Prefix)':<22} | {'Run 2 SHA-256 (Prefix)':<22} | {'Match':<5}")
    print("-" * 110)

    for table in tables:
        rows1 = data1[table]
        rows2 = data2[table]

        count1 = len(rows1)
        count2 = len(rows2)

        hash1 = compute_table_sha256(rows1)
        hash2 = compute_table_sha256(rows2)

        counts_equal = (count1 == count2)
        hashes_equal = (hash1 == hash2)
        table_match = counts_equal and hashes_equal

        if not table_match:
            all_match = False

        status = "PASS" if table_match else "FAIL"
        print(f"{table:<26} | {count1:<10} | {count2:<10} | {hash1[:20]}.. | {hash2[:20]}.. | {status:<5}")

    print("-" * 110)
    if all_match:
        print("\n>>> REPRODUCIBILITY RESULT: PERFECT MATCH (100% Deterministic across runs)")
    else:
        print("\n>>> REPRODUCIBILITY RESULT: MISMATCH DETECTED")

    return all_match


if __name__ == "__main__":
    success = test_reproducibility(seed=DEFAULT_RANDOM_SEED, scale="starter")
    sys.exit(0 if success else 1)
