import hashlib
import re

import pandas as pd
from difflib import SequenceMatcher

from pipeline.schema import standardize_schema


def normalize_text(text):
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def generate_id(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_similar(text1, text2, threshold=0.90):
    if not text1 or not text2:
        return False
    # Cheap length gate — skip expensive comparison if lengths differ wildly
    if abs(len(text1) - len(text2)) / max(len(text1), len(text2)) > 0.3:
        return False
    return SequenceMatcher(None, text1, text2).ratio() >= threshold


def run_cross_portal_dedup(dataframes_dict: dict, similarity_threshold=0.90):
    """
    dataframes_dict: {"Naukri": df, "Indeed": df, "Foundit": df}
    Returns: (unified_df, audit_df)
    """
    all_jobs = []
    for portal, df in dataframes_dict.items():
        if df is None or len(df) == 0:
            continue
        all_jobs.append(standardize_schema(df, portal))

    if not all_jobs:
        return pd.DataFrame(), pd.DataFrame()

    master_df = pd.concat(all_jobs, ignore_index=True)

    master_df["norm_company"] = master_df["company_name"].apply(normalize_text)
    master_df["norm_title"] = master_df["job_title"].apply(normalize_text)
    master_df["norm_desc"] = master_df["description"].apply(normalize_text)
    master_df["block_key"] = master_df["norm_company"] + "||" + master_df["norm_title"]

    canonical_records = []
    duplicate_audit = []

    for block_key, group in master_df.groupby("block_key"):
        # Single job in this block → trivially unique
        if len(group) == 1:
            record = group.iloc[0].to_dict()
            record["all_portals"] = record["source_portal"]
            record["canonical_id"] = generate_id(
                block_key + "||" + record["norm_desc"][:200]
            )
            canonical_records.append(record)
            continue

        processed = set()
        for i in range(len(group)):
            if i in processed:
                continue
            primary = group.iloc[i]
            processed.add(i)
            portals = [primary["source_portal"]]

            for j in range(i + 1, len(group)):
                if j in processed:
                    continue
                compare = group.iloc[j]

                if primary["source_portal"] == compare["source_portal"]:
                    # Same portal: exact ID match only
                    match = (
                        primary["source_job_id"] == compare["source_job_id"]
                    )
                else:
                    match = is_similar(
                        primary["norm_desc"],
                        compare["norm_desc"],
                        similarity_threshold,
                    )

                if match:
                    processed.add(j)
                    portals.append(compare["source_portal"])
                    duplicate_audit.append(
                        {
                            "kept_id": primary["source_job_id"],
                            "kept_portal": primary["source_portal"],
                            "dropped_id": compare["source_job_id"],
                            "dropped_portal": compare["source_portal"],
                            "company": primary["company_name"],
                            "title": primary["job_title"],
                        }
                    )

            record = primary.to_dict()
            record["all_portals"] = " || ".join(sorted(set(portals)))
            record["canonical_id"] = generate_id(
                block_key + "||" + record["norm_desc"][:200]
            )
            canonical_records.append(record)

    final_df = pd.DataFrame(canonical_records).drop(
        columns=["norm_company", "norm_title", "block_key", "norm_desc"],
        errors="ignore",
    )
    return final_df, pd.DataFrame(duplicate_audit)
