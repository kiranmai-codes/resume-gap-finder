#!/usr/bin/env python3
"""Master pipeline: reads jobs.db → cross-portal dedup → unified benchmark."""

from pathlib import Path

import pandas as pd

from pipeline.db import JobDatabase
from pipeline.dedup import run_cross_portal_dedup

ROOT = Path(__file__).parent
DB_PATH = ROOT / "jobs.db"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)


def main():
    print("📦 Loading data from Database...")
    db = JobDatabase(str(DB_PATH))
    df = db.export_to_dataframe()
    db.close()

    if df.empty:
        print("⚠️  Database is empty. Run your scrapers first.")
        return

    print(f"Loaded {len(df)} raw records.")
    print(df["source_portal"].value_counts().to_string())

    portals_dict = {
        portal: group for portal, group in df.groupby("source_portal")
    }

    print("\n🔍 Running cross-portal fuzzy dedup...")
    unified_df, audit_df = run_cross_portal_dedup(
        portals_dict, similarity_threshold=0.90
    )

    unified_path = OUT_DIR / "unified_market_benchmark.csv"
    audit_path = OUT_DIR / "cross_portal_duplicate_audit.csv"
    unified_df.to_csv(unified_path, index=False, encoding="utf-8-sig")
    audit_df.to_csv(audit_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ Unified unique jobs: {len(unified_df)}")
    print(f"🔍 Cross-portal duplicates caught: {len(audit_df)}")
    print(f"📁 Saved: {unified_path}")
    print(f"📁 Saved: {audit_path}")

    if len(audit_df):
        print("\nSample duplicate catches:")
        print(audit_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
