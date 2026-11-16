#!/usr/bin/env python3
"""Run the 16-stage benchmark pipeline. Prints funnel. Saves all intermediate files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.db import JobDatabase
from pipeline.stages import (
    stage_01_canonicalize, stage_02_deduplicate, stage_03_entry_gate,
    stage_04_role_relevance, stage_05_content_quality, stage_06_career_level,
    stage_07_experience_check, stage_08_role_family,
    stages_09_13_technology, stage_14_benchmark,
    stage_15_frequency_stability, stage_16_resume_gap_artifact,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "jobs.db"


def main():
    print("📦 Loading jobs.db...")
    db = JobDatabase(str(DB_PATH))
    df = db.export_to_dataframe()
    db.close()

    if df.empty:
        print("❌ DB is empty — run scrapers first.")
        return 1

    print(f"   Loaded {len(df)} raw jobs")
    print(df["source_portal"].value_counts().to_string())
    print()

    funnel = []

    def run(n, name, fn, *args):
        print(f"▶  Stage {n:2d} — {name}")
        out_main, out_extra, stats = fn(*args)
        funnel.append({"stage": n, "name": name, **stats})
        keys = ", ".join(f"{k}={v}" for k, v in stats.items()
                         if k not in ("in", "out", "dropped"))
        print(f"   in={stats.get('in', '')} out={stats.get('out', '')} "
              f"dropped={stats.get('dropped', '')}  {keys}")
        return out_main, out_extra

    # 1
    df, _ = run(1, "Canonicalize", stage_01_canonicalize, df)

    # 2
    df, _ = run(2, "Deduplicate", stage_02_deduplicate, df)

    # 3
    df, _ = run(3, "Entry-Level Gate", stage_03_entry_gate, df)

    # 4
    df, _ = run(4, "Role Relevance", stage_04_role_relevance, df)

    # 5
    df, _ = run(5, "Content Quality", stage_05_content_quality, df)

    # 6
    df, _ = run(6, "Career Level", stage_06_career_level, df)

    # 7
    df, _ = run(7, "Experience Check", stage_07_experience_check, df)

    # 8
    df, _ = run(8, "Role Family", stage_08_role_family, df)

    # 9-13
    job_df, tech_df = run(9, "Technology Extraction + Context", stages_09_13_technology, df)

    # 14
    job_df, tech_df = run(14, "Benchmark", stage_14_benchmark, job_df, tech_df)

       # 15
    freq_dict, _ = run(15, "Frequency + Stability (per role family)",
                       stage_15_frequency_stability, job_df, tech_df)

    # 16
    run(16, "Resume Gap Artifact", stage_16_resume_gap_artifact,
        job_df, freq_dict)

    # ── Funnel report ──
    print()
    print("=" * 78)
    print("FUNNEL")
    print("=" * 78)
    print(f"{'stage':>5}  {'name':<36}  {'in':>5}  {'out':>5}  {'dropped':>7}")
    print("-" * 78)
    for row in funnel:
        print(f"{row['stage']:>5}  {row['name']:<36}  "
              f"{row.get('in', ''):>5}  {row.get('out', ''):>5}  "
              f"{row.get('dropped', ''):>7}")

    print()
    print("=" * 78)
    print("BENCHMARK")
    print("=" * 78)
    print(f"Benchmark jobs:           {len(job_df)}")
    print(f"  Confirmed tier:         {(job_df['__tier'] == 'confirmed').sum()}")
    print(f"  Probable tier:          {(job_df['__tier'] == 'probable').sum()}")
    print(f"Unique companies:         {job_df['company_name'].nunique()}")
    print()
    print("Top 15 technologies overall (with stability):")
    cols = ["technology", "job_count", "benchmark_share", "priority", "stability_tier"]
    print(freq_dict["overall"].head(15)[cols].to_string(index=False))

    print()
    print("Role-family top-5 technologies:")
    for family, freq in freq_dict.items():
        if family == "overall":
            continue
        n = int((job_df["__role_family"] == family).sum())
        top5 = freq.head(5)
        summary = ", ".join(
            f"{t} ({s*100:.0f}%)"
            for t, s in zip(top5["technology"], top5["benchmark_share"]))
        print(f"  {family:32s} (n={n:2d})  {summary}")

    print()
    print(f"📁 All intermediate files: {ROOT / 'outputs' / 'pipeline'}")
    for f in sorted((ROOT / "outputs" / "pipeline").glob("*.csv")):
        print(f"   - {f.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
