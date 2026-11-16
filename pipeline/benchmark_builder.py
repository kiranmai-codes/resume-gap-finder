#!/usr/bin/env python3
"""
Unified benchmark builder — reads jobs.db, classifies every portal with one
classifier, produces the entry-level SDE benchmark.

Answers: "What does the entry-level SDE market in India actually require?"

Outputs (to outputs/benchmark/):
  - eligible_jobs.csv         — job-level, filtered to benchmark-eligible
  - manual_review_jobs.csv    — job-level, ambiguous cases
  - technology_frequency.csv  — tech-level, ranked by share of eligible jobs
  - role_family_frequency.csv — role-level distribution
  - summary.json              — one-line overview
"""
import json
import re
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import JobDatabase
from core.indeed_taxonomy import (
    clean,
    classify_entry_level,
    classify_career_level,
    classify_role_relevance,
    classify_role_family,
    clean_description_for_extraction,
    technologies_from_description,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "jobs.db"
OUT_DIR = ROOT / "outputs" / "benchmark"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# V10-style experience-conflict detection
# Catches "0-X years" postings that ALSO say "at least 1 year" somewhere.
# The indeed_taxonomy entry gate handles numeric forms; these handle word forms.
# ─────────────────────────────────────────────────────────────
CONFLICTING_EXPERIENCE_PATTERNS = [
    r"\bat\s+least\s+(?:one|1)\s+year(?:s)?\b",
    r"\bminimum\s+(?:of\s+)?(?:one|1)\s+year(?:s)?\b",
    r"\b(?:one|1)\s+years?\s+of\s+(?:professional\s+)?experience\b",
    r"\b(?:one|1)\s*\+\s*years?\s+of\s+(?:professional\s+)?experience\b",
]


def detect_experience_conflict(description):
    text = (description or "").lower()
    for p in CONFLICTING_EXPERIENCE_PATTERNS:
        if re.search(p, text, re.I):
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Per-job classification
# ─────────────────────────────────────────────────────────────
def classify_one_job(row):
    title = clean(row["job_title"])
    desc = clean(row["description"])
    desc_clean = clean_description_for_extraction(desc)

    entry_status, entry_reason = classify_entry_level(title, desc_clean, "")
    (career_level, _career_src, career_conf, career_reason,
     exp_min, exp_max) = classify_career_level(title, desc_clean, "")
    role_rel, role_reason = classify_role_relevance(title, desc_clean, "")
    role_family, role_src, role_conf = classify_role_family(title, desc_clean)
    conflict = detect_experience_conflict(desc_clean)

    # Benchmark eligibility: all gates must pass
    eligible = (
        entry_status == "confirmed_entry_level"
        and career_level == "early_career"
        and role_rel == "target_role_relevant"
        and not conflict
        and len(desc_clean) >= 150
    )

    # Decide review bucket for ineligible jobs
    review_reason = ""
    if eligible:
        review_reason = ""
    elif entry_status == "ambiguous":
        review_reason = "entry_level_ambiguous"
    elif entry_status == "not_entry_level":
        review_reason = f"not_entry_level: {entry_reason}"
    elif conflict:
        review_reason = "experience_conflict"
    elif role_rel == "target_role_irrelevant":
        review_reason = "role_irrelevant"
    elif role_rel == "target_role_adjacent":
        review_reason = "role_adjacent"
    elif career_level != "early_career":
        review_reason = f"career_level: {career_level}"
    elif len(desc_clean) < 150:
        review_reason = "content_too_short"

    return {
        "eligible": eligible,
        "review_reason": review_reason,
        "entry_status": entry_status,
        "entry_reason": entry_reason,
        "career_level": career_level,
        "career_confidence": career_conf,
        "career_reason": career_reason,
        "exp_min": exp_min,
        "exp_max": exp_max,
        "role_relevance": role_rel,
        "role_reason": role_reason,
        "role_family": role_family,
        "role_family_confidence": role_conf,
        "experience_conflict": conflict,
        "clean_description": desc_clean,
    }


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    print("📦 Loading jobs.db...")
    db = JobDatabase(str(DB_PATH))
    df = db.export_to_dataframe()
    db.close()

    if df.empty:
        print("❌ DB is empty — run scrapers first.")
        return

    print(f"Loaded {len(df)} jobs")
    print(df["source_portal"].value_counts().to_string())
    print()

    # Classify every job
    print("🔍 Classifying all jobs with unified classifier...")
    classifications = df.apply(classify_one_job, axis=1)
    cls_df = pd.DataFrame(list(classifications))

    # Build enriched frame
    enriched = pd.concat([df, cls_df], axis=1)

    eligible = enriched[enriched["eligible"]].copy()
    manual = enriched[~enriched["eligible"]].copy()

    print(f"✅ Eligible: {len(eligible)} / {len(enriched)}")
    print(f"   Manual review: {len(manual)}")
    print()

    # ─── Technology extraction (only on eligible jobs) ───
    print("🔧 Extracting technologies from eligible jobs...")
    tech_rows = []
    for _, job in eligible.iterrows():
        techs = technologies_from_description(
            job["clean_description"],
            job["job_title"],
            job["role_family"],
        )
        for tech in techs:
            # Only count as "benchmark-relevant" if required or stack_required
            tech_rows.append({
                "source_portal": job["source_portal"],
                "source_job_id": job["source_job_id"],
                "job_title": job["job_title"],
                "company_name": job["company_name"],
                "role_family": job["role_family"],
                **tech,
            })

    tech_df = pd.DataFrame(tech_rows)

    # ─── Technology frequency (job-level denominator) ───
    if len(tech_df):
        # One row per (job, technology) — dedup by requirement rank
        rank = {"mentioned": 1, "preferred": 2, "stack_required": 3, "required": 4}
        tech_df["_rank"] = tech_df["requirement_type"].map(rank).fillna(0)
        tech_df_dedup = (
            tech_df
            .sort_values(["source_job_id", "technology", "_rank"],
                         ascending=[True, True, False])
            .drop_duplicates(["source_job_id", "technology"], keep="first")
            .drop(columns=["_rank"])
        )

        denominator = len(eligible)

        tech_freq = (
            tech_df_dedup
            .groupby("technology", dropna=False)
            .agg(
                job_count=("source_job_id", "nunique"),
                required_count=("requirement_type",
                                lambda s: (s == "required").sum()),
                stack_required_count=("requirement_type",
                                     lambda s: (s == "stack_required").sum()),
                preferred_count=("requirement_type",
                                 lambda s: (s == "preferred").sum()),
            )
            .reset_index()
        )
        tech_freq["job_share"] = tech_freq["job_count"] / denominator
        tech_freq["benchmark_share"] = (
            (tech_freq["required_count"] + tech_freq["stack_required_count"])
            / denominator
        )
        tech_freq["priority"] = tech_freq["benchmark_share"].apply(
            lambda x: "high" if x >= 0.30
            else ("medium" if x >= 0.15 else "low")
        )
        tech_freq = tech_freq.sort_values(
            ["benchmark_share", "job_share", "job_count"],
            ascending=[False, False, False],
        )
    else:
        tech_freq = pd.DataFrame()
        tech_df_dedup = pd.DataFrame()

    # ─── Role-family frequency ───
    role_freq = (
        eligible
        .groupby("role_family", dropna=False)
        .agg(job_count=("source_job_id", "nunique"))
        .reset_index()
        .sort_values("job_count", ascending=False)
    )
    role_freq["job_share"] = role_freq["job_count"] / max(len(eligible), 1)

    # ─── Cross-portal coverage (per eligible job) ───
    portal_coverage = (
        eligible
        .groupby("source_portal")
        .size()
        .reset_index(name="eligible_jobs")
        .sort_values("eligible_jobs", ascending=False)
    )

    # ─── Manual-review reason breakdown ───
    review_breakdown = (
        manual["review_reason"]
        .value_counts()
        .reset_index()
    )
    review_breakdown.columns = ["reason", "count"]

    # ─── Write outputs ───
    eligible_out_cols = [
        "source_portal", "source_job_id", "job_title", "company_name",
        "location", "role_family", "career_level", "career_confidence",
        "role_relevance", "entry_status", "experience_conflict",
        "exp_min", "exp_max", "discovery_family",
    ]
    eligible[[c for c in eligible_out_cols if c in eligible.columns]].to_csv(
        OUT_DIR / "eligible_jobs.csv", index=False, encoding="utf-8-sig")

    manual_out_cols = eligible_out_cols + ["review_reason", "entry_reason",
                                            "role_reason", "career_reason"]
    manual[[c for c in manual_out_cols if c in manual.columns]].to_csv(
        OUT_DIR / "manual_review_jobs.csv", index=False, encoding="utf-8-sig")

    if len(tech_freq):
        tech_freq.to_csv(
            OUT_DIR / "technology_frequency.csv",
            index=False, encoding="utf-8-sig")

    role_freq.to_csv(
        OUT_DIR / "role_family_frequency.csv",
        index=False, encoding="utf-8-sig")

    summary = {
        "total_jobs_in_db": int(len(df)),
        "eligible_jobs": int(len(eligible)),
        "manual_review_jobs": int(len(manual)),
        "eligibility_rate": round(len(eligible) / len(df), 4) if len(df) else 0,
        "unique_eligible_companies": int(eligible["company_name"].nunique()),
        "portal_distribution": portal_coverage.to_dict(orient="records"),
        "role_family_distribution": role_freq.head(10).to_dict(orient="records"),
        "top_10_technologies": (
            tech_freq.head(10)[["technology", "job_share", "benchmark_share",
                                "priority"]].to_dict(orient="records")
            if len(tech_freq) else []
        ),
        "manual_review_breakdown": review_breakdown.to_dict(orient="records"),
    }
    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # ─── Print ───
    print()
    print("=" * 72)
    print("BENCHMARK SUMMARY")
    print("=" * 72)
    print(f"Total jobs in DB:         {len(df)}")
    print(f"Eligible for benchmark:   {len(eligible)} ({len(eligible)/len(df):.1%})")
    print(f"Manual review:            {len(manual)}")
    print(f"Unique companies:         {eligible['company_name'].nunique()}")
    print()
    print("Portal distribution of eligible jobs:")
    print(portal_coverage.to_string(index=False))
    print()
    print("Top 15 required technologies:")
    if len(tech_freq):
        print(tech_freq.head(15)[
            ["technology", "job_count", "benchmark_share", "priority"]
        ].to_string(index=False))
    print()
    print("Top 5 role families:")
    print(role_freq.head(5).to_string(index=False))
    print()
    print(f"📁 Outputs written to: {OUT_DIR}")
    for f in OUT_DIR.glob("*.csv"):
        print(f"   - {f.name}")
    print(f"   - summary.json")


if __name__ == "__main__":
    main()
