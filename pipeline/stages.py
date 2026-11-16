"""The 16-stage benchmark pipeline. Each stage is auditable.

Every stage:
  - Takes a DataFrame
  - Returns (passing_df, rejected_df, stats_dict)
  - Saves passing and rejected to outputs/pipeline/

Steps 9-13 are atomic: technologies_from_description() emits all five
attributes (normalized name, evidence, requirement type, context) per row.
Splitting them would require 5 passes over the same text.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.indeed_taxonomy import (
    clean,
    classify_entry_level,
    classify_career_level,
    classify_role_relevance,
    classify_role_family,
    clean_description_for_extraction,
    technologies_from_description,
)
from pipeline.dedup import run_cross_portal_dedup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "pipeline"
OUT.mkdir(parents=True, exist_ok=True)


def _save(df, name):
    if df is not None and len(df):
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")


# ─────────────────────────────────────────────────────────────
# Stage 1 — Canonicalize
# ─────────────────────────────────────────────────────────────
def stage_01_canonicalize(df):
    out = df.copy()
    out["job_title"] = out["job_title"].fillna("").map(clean)
    out["company_name"] = out["company_name"].fillna("").map(clean)
    out["location"] = out["location"].fillna("").map(clean)
    out["description"] = out["description"].fillna("").map(clean)
    stats = {"in": len(df), "out": len(out), "dropped": 0}
    _save(out, "01_canonicalized")
    return out, pd.DataFrame(), stats


# ─────────────────────────────────────────────────────────────
# Stage 2 — Deduplicate (fuzzy, cross-portal)
# ─────────────────────────────────────────────────────────────
def stage_02_deduplicate(df):
    portals = {p: g for p, g in df.groupby("source_portal")}
    unified, audit = run_cross_portal_dedup(portals, similarity_threshold=0.90)
    stats = {"in": len(df), "out": len(unified), "dropped": len(df) - len(unified)}
    _save(unified, "02_deduplicated")
    _save(audit, "02_rejected_duplicates")
    return unified, audit, stats


# ─────────────────────────────────────────────────────────────
# Stage 3 — Entry-Level Gate (two-tier)
# ─────────────────────────────────────────────────────────────
SOFTWARE_TITLE_HINTS = [
    r"\bsoftware\s+(?:engineer|developer|programmer|trainee)\b",
    r"\b(?:junior|jr\.?|associate|graduate|trainee)\s+"
    r"(?:software|developer|engineer|programmer)\b",
    r"\b(?:application|app|web|mobile|android|ios)\s+(?:developer|engineer)\b",
    r"\b(?:full[\s-]?stack|front[\s-]?end|back[\s-]?end|mean|mern)\s+"
    r"(?:developer|engineer|programmer)\b",
    r"\b(?:python|java|javascript|typescript|react|node|angular|vue|php|"
    r"golang|rust|kotlin|swift|ruby|dotnet|\.net)\s+(?:developer|engineer)\b",
    r"\b(?:developer|engineer|programmer)\b",
    r"\bsde\b",
]

DISQUALIFYING_TITLE_HINTS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b",
    r"\bstaff\b", r"\barchitect\b", r"\bmanager\b", r"\bdirector\b",
]


def _tier_for(title, description):
    title_low = clean(title).lower()
    if any(re.search(p, title_low) for p in DISQUALIFYING_TITLE_HINTS):
        return "rejected", "Senior/lead/principal/management title"

    base, base_reason = classify_entry_level(title, description, "")
    if base == "confirmed_entry_level":
        return "confirmed", base_reason
    if base == "not_entry_level":
        return "rejected", base_reason
    if not any(re.search(p, title_low) for p in SOFTWARE_TITLE_HINTS):
        return "rejected", "Title not a software role"
    return "probable", "Software title, no explicit experience requirement"


def stage_03_entry_gate(df):
    rows = []
    for _, r in df.iterrows():
        desc = clean_description_for_extraction(r["description"])
        tier, reason = _tier_for(r["job_title"], desc)
        rows.append({"__tier": tier, "__tier_reason": reason,
                     "__clean_desc": desc})
    enriched = pd.concat([df.reset_index(drop=True),
                          pd.DataFrame(rows)], axis=1)

    passing = enriched[enriched["__tier"] != "rejected"].copy()
    rejected = enriched[enriched["__tier"] == "rejected"].copy()

    stats = {"in": len(df), "out": len(passing), "dropped": len(rejected),
             "confirmed": int((passing["__tier"] == "confirmed").sum()),
             "probable": int((passing["__tier"] == "probable").sum())}
    _save(passing.drop(columns=["__clean_desc"]), "03_entry_gate_passing")
    _save(rejected.drop(columns=["__clean_desc"]), "03_entry_gate_rejected")
    return passing, rejected, stats


# ─────────────────────────────────────────────────────────────
# Stage 4 — Role Relevance
# ─────────────────────────────────────────────────────────────
def stage_04_role_relevance(df):
    rows = []
    for _, r in df.iterrows():
        rel, reason = classify_role_relevance(r["job_title"], r["__clean_desc"], "")
        rows.append({"__role_rel": rel, "__role_rel_reason": reason})
    enriched = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)

    passing = enriched[enriched["__role_rel"] == "target_role_relevant"].copy()
    rejected = enriched[enriched["__role_rel"] != "target_role_relevant"].copy()
    stats = {"in": len(df), "out": len(passing), "dropped": len(rejected),
             "adjacent": int((rejected["__role_rel"] == "target_role_adjacent").sum()),
             "irrelevant": int((rejected["__role_rel"] == "target_role_irrelevant").sum())}
    _save(passing.drop(columns=["__clean_desc"]), "04_role_relevance_passing")
    _save(rejected.drop(columns=["__clean_desc"]), "04_role_relevance_rejected")
    return passing, rejected, stats


# ─────────────────────────────────────────────────────────────
# Stage 5 — Content Quality
# ─────────────────────────────────────────────────────────────
def stage_05_content_quality(df):
    out = df.copy()
    out["__content_ok"] = out["__clean_desc"].str.len() >= 150
    passing = out[out["__content_ok"]].copy()
    rejected = out[~out["__content_ok"]].copy()
    stats = {"in": len(df), "out": len(passing), "dropped": len(rejected),
             "reason": "description < 150 chars"}
    _save(passing.drop(columns=["__clean_desc", "__content_ok"]),
          "05_content_passing")
    _save(rejected.drop(columns=["__clean_desc", "__content_ok"]),
          "05_content_rejected")
    return passing, rejected, stats


# ─────────────────────────────────────────────────────────────
# Stage 6 — Career Level (annotate, DO NOT filter)
# ─────────────────────────────────────────────────────────────
def stage_06_career_level(df):
    rows = []
    for _, r in df.iterrows():
        lvl, _src, conf, reason, exp_min, exp_max = classify_career_level(
            r["job_title"], r["__clean_desc"], "")
        rows.append({"__career_level": lvl, "__career_conf": conf,
                     "__career_reason": reason, "__exp_min": exp_min,
                     "__exp_max": exp_max})
    enriched = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    stats = {"in": len(df), "out": len(enriched), "dropped": 0,
             "distribution": enriched["__career_level"].value_counts().to_dict()}
    _save(enriched.drop(columns=["__clean_desc"]), "06_career_level")
    return enriched, pd.DataFrame(), stats


# ─────────────────────────────────────────────────────────────
# Stage 7 — Experience Check (drop conflicts)
# ─────────────────────────────────────────────────────────────
CONFLICT_PATTERNS = [
    r"\bat\s+least\s+(?:one|1)\s+year(?:s)?\b",
    r"\bminimum\s+(?:of\s+)?(?:one|1)\s+year(?:s)?\b",
    r"\b(?:one|1)\s+years?\s+of\s+(?:professional\s+)?experience\b",
    r"\b(?:one|1)\s*\+\s*years?\s+of\s+(?:professional\s+)?experience\b",
]


def stage_07_experience_check(df):
    out = df.copy()
    out["__exp_conflict"] = out["__clean_desc"].apply(
        lambda t: any(re.search(p, t, re.I) for p in CONFLICT_PATTERNS))
    passing = out[~out["__exp_conflict"]].copy()
    rejected = out[out["__exp_conflict"]].copy()
    stats = {"in": len(df), "out": len(passing), "dropped": len(rejected),
             "reason": "explicit 1+ years conflicts with zero-exp gate"}
    _save(passing.drop(columns=["__clean_desc", "__exp_conflict"]),
          "07_experience_passing")
    _save(rejected.drop(columns=["__clean_desc", "__exp_conflict"]),
          "07_experience_rejected")
    return passing, rejected, stats


# ─────────────────────────────────────────────────────────────
# Stage 8 — Role Family (drop Unclear)
# ─────────────────────────────────────────────────────────────
def stage_08_role_family(df):
    rows = []
    for _, r in df.iterrows():
        fam, _src, conf = classify_role_family(r["job_title"], r["__clean_desc"])
        rows.append({"__role_family": fam, "__role_family_conf": conf})
    enriched = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    passing = enriched[enriched["__role_family"] != "Unclear"].copy()
    rejected = enriched[enriched["__role_family"] == "Unclear"].copy()
    stats = {"in": len(df), "out": len(passing), "dropped": len(rejected),
             "distribution": passing["__role_family"].value_counts().to_dict()}
    _save(passing.drop(columns=["__clean_desc"]), "08_role_family_passing")
    _save(rejected.drop(columns=["__clean_desc"]), "08_role_family_rejected")
    return passing, rejected, stats


# ─────────────────────────────────────────────────────────────
# Stages 9-13 — Technology Extraction + Normalization + Evidence
#                + Requirement Type + Context (atomic)
# ─────────────────────────────────────────────────────────────
def stages_09_13_technology(df):
    rows = []
    for _, job in df.iterrows():
        techs = technologies_from_description(
            job["__clean_desc"], job["job_title"], job["__role_family"])
        for t in techs:
            rows.append({
                "source_portal": job["source_portal"],
                "source_job_id": job["source_job_id"],
                "job_title": job["job_title"],
                "company_name": job["company_name"],
                "role_family": job["__role_family"],
                # Step 9: technology, Step 10: normalized, Step 11: evidence,
                # Step 12: requirement_type, Step 13: context
                **t,
            })
    tech_df = pd.DataFrame(rows)
    stats = {"in_jobs": len(df), "out_jobs": len(df),
             "tech_rows": len(tech_df),
             "unique_technologies": int(tech_df["technology"].nunique())
             if len(tech_df) else 0}
    _save(tech_df, "09_13_technology")
    return df, tech_df, stats


# ─────────────────────────────────────────────────────────────
# Stage 14 — Benchmark (final eligible job set)
# ─────────────────────────────────────────────────────────────
def stage_14_benchmark(job_df, tech_df):
    # By this point, all gates have passed. Benchmark = the jobs we have.
    # Preserve the tier annotation.
    job_df_out = job_df.copy()

    # Dedupe tech rows per (job, technology) — keep highest requirement rank
    rank = {"mentioned": 1, "preferred": 2, "stack_required": 3, "required": 4}
    tech_df = tech_df.copy()
    tech_df["__rank"] = tech_df["requirement_type"].map(rank).fillna(0)
    tech_dedup = (
        tech_df
        .sort_values(["source_job_id", "technology", "__rank"],
                     ascending=[True, True, False])
        .drop_duplicates(["source_job_id", "technology"], keep="first")
        .drop(columns=["__rank"])
    )

    benchmark_ids = set(job_df_out["source_job_id"].astype(str))
    tech_dedup = tech_dedup[tech_dedup["source_job_id"].astype(str).isin(benchmark_ids)]

    stats = {"benchmark_jobs": len(job_df_out),
             "benchmark_tech_rows": len(tech_dedup),
             "confirmed": int((job_df_out["__tier"] == "confirmed").sum()),
             "probable": int((job_df_out["__tier"] == "probable").sum())}
    _save(job_df_out.drop(columns=["__clean_desc"]), "14_benchmark_jobs")
    _save(tech_dedup, "14_benchmark_technologies")
    return job_df_out, tech_dedup, stats


# ─────────────────────────────────────────────────────────────
# Stage 15 — Frequency + Stability (per role family)
# ─────────────────────────────────────────────────────────────
def _compute_freq(job_df, tech_df, n_boot=200):
    """Frequency + bootstrap stability for one job subset."""
    if len(tech_df) == 0 or len(job_df) == 0:
        return pd.DataFrame()

    denom = max(len(job_df), 1)

    base = tech_df.groupby("technology").agg(
        job_count=("source_job_id", "nunique"),
        required_count=("requirement_type", lambda s: (s == "required").sum()),
        stack_required_count=("requirement_type",
                              lambda s: (s == "stack_required").sum()),
        preferred_count=("requirement_type", lambda s: (s == "preferred").sum()),
    ).reset_index()
    base["job_share"] = base["job_count"] / denom
    base["benchmark_share"] = (base["required_count"] +
                               base["stack_required_count"]) / denom
    base["priority"] = base["benchmark_share"].apply(
        lambda x: "high" if x >= 0.30
        else ("medium" if x >= 0.15 else "low"))

    # Bootstrap stability
    rng = np.random.default_rng(42)
    job_ids = job_df["source_job_id"].astype(str).tolist()
    techs_by_job = (tech_df.groupby("source_job_id")["technology"]
                    .apply(set).to_dict())
    all_techs = tech_df["technology"].unique().tolist()

    samples = defaultdict(list)
    for _ in range(n_boot):
        drawn = rng.choice(job_ids, size=len(job_ids), replace=True)
        counts = defaultdict(set)
        for jid in drawn:
            for tech in techs_by_job.get(jid, set()):
                counts[tech].add(jid)
        for tech in all_techs:
            samples[tech].append(len(counts.get(tech, set())) / len(job_ids))

    stab = pd.DataFrame([
        {"technology": t,
         "boot_mean_share": float(np.mean(samples[t])),
         "boot_std": float(np.std(samples[t])),
         "boot_p05": float(np.percentile(samples[t], 5)),
         "boot_p95": float(np.percentile(samples[t], 95)),
         "stability_cv": (float(np.std(samples[t]) / np.mean(samples[t]))
                         if np.mean(samples[t]) > 0 else 1.0)}
        for t in all_techs
    ])
    stab["stability_tier"] = stab["stability_cv"].apply(
        lambda cv: "high" if cv < 0.15
        else ("medium" if cv < 0.30 else "low"))

    return (base.merge(stab, on="technology", how="left")
            .sort_values(["benchmark_share", "job_share", "job_count"],
                         ascending=[False, False, False]))


def stage_15_frequency_stability(job_df, tech_df, n_boot=200, min_sample=10):
    """Produces a frequency+stability table per role family + overall.

    Returns:
        freq_dict: {"overall": DataFrame, "<Family>": DataFrame, ...}
        extra:     empty DataFrame
        stats:     summary
    """
    freq_dict = {}

    # Overall benchmark
    overall = _compute_freq(job_df, tech_df, n_boot)
    freq_dict["overall"] = overall

    # Per role family — only those with enough sample
    skipped = []
    for family in sorted(job_df["__role_family"].unique()):
        family_jobs = job_df[job_df["__role_family"] == family]
        n = len(family_jobs)
        if n < min_sample:
            skipped.append((family, n))
            continue

        family_ids = set(family_jobs["source_job_id"].astype(str))
        family_tech = tech_df[
            tech_df["source_job_id"].astype(str).isin(family_ids)]

        if len(family_tech) == 0:
            skipped.append((family, n))
            continue

        freq_dict[family] = _compute_freq(family_jobs, family_tech, n_boot)

    # Save all tables
    for key, df in freq_dict.items():
        safe_key = key.replace("/", "_").replace(" ", "_").lower()
        _save(df, f"15_freq_{safe_key}")

    # Also save a role-family summary
    summary_rows = []
    for family, freq in freq_dict.items():
        if family == "overall":
            continue
        top = freq.head(5)
        summary_rows.append({
            "role_family": family,
            "n_jobs": int((job_df["__role_family"] == family).sum()),
            "top_technologies": ", ".join(
                f"{t} ({s*100:.0f}%)"
                for t, s in zip(top["technology"], top["benchmark_share"])),
        })
    summary_df = pd.DataFrame(summary_rows)
    if len(summary_df):
        _save(summary_df, "15_role_family_summary")

    stats = {
        "families_reported": len(freq_dict) - 1,
        "families_skipped": len(skipped),
        "skipped": [f"{f}(n={n})" for f, n in skipped],
        "overall_techs": len(overall),
    }
    return freq_dict, pd.DataFrame(), stats


# ─────────────────────────────────────────────────────────────
# Stage 16 — Resume Gap Finder artifact (per role family)
# ─────────────────────────────────────────────────────────────
def stage_16_resume_gap_artifact(job_df, freq_dict):
    role_freq = (job_df.groupby("__role_family", dropna=False)
                 .size().reset_index(name="job_count"))
    role_freq["job_share"] = role_freq["job_count"] / max(len(job_df), 1)

    # Build per-family sub-artifacts
    role_technologies = {}
    role_meta = {}
    for family, freq in freq_dict.items():
        if family == "overall":
            continue
        role_technologies[family] = freq[[
            "technology", "job_count", "job_share", "benchmark_share",
            "priority", "stability_tier"
        ]].to_dict(orient="records")
        role_meta[family] = {
            "n_jobs": int((job_df["__role_family"] == family).sum()),
            "n_technologies": len(freq),
        }

    artifact = {
        "benchmark_size": int(len(job_df)),
        "confirmed_tier": int((job_df["__tier"] == "confirmed").sum()),
        "probable_tier": int((job_df["__tier"] == "probable").sum()),
        "unique_companies": int(job_df["company_name"].nunique()),
        "portal_distribution": (
            job_df.groupby("source_portal").size().to_dict()),
        "role_family_distribution": role_freq.to_dict(orient="records"),

        # Overall benchmark (backward-compatible shape)
        "technologies": freq_dict["overall"][[
            "technology", "job_count", "job_share", "benchmark_share",
            "priority", "stability_tier"
        ]].to_dict(orient="records"),

        # Role-family-specific tables
        "role_technologies": role_technologies,
        "role_meta": role_meta,
    }

    path = OUT / "16_resume_gap_artifact.json"
    with open(path, "w") as f:
        json.dump(artifact, f, indent=2)

    stats = {
        "artifact_path": str(path),
        "overall_techs": len(artifact["technologies"]),
        "role_families": len(role_technologies),
    }
    return freq_dict, pd.DataFrame(), stats
