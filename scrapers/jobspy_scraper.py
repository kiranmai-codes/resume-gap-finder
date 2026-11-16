#!/usr/bin/env python3
"""
JobSpy scraper — library-based, no browser.
- Aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter in one call
- Returns DataFrame → maps to standard schema → jobs.db
- Incremental (skips known URLs from DB)
- Proxies supported via config (required for LinkedIn/Indeed at scale)
"""
import argparse
import hashlib
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.db import JobDatabase
from core.notifier import Notifier

try:
    from jobspy import scrape_jobs
except ImportError:
    print("Missing dependency: python-jobspy")
    print("Install with: pip install python-jobspy")
    sys.exit(1)

PORTAL = "JobSpy"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "jobspy"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# JobSpy search profiles. Each row is a discovery channel.
MANIFEST = [
    {"discovery_family": "Software Developer Fresher", "search_term": "software developer fresher", "location": "India", "sites": ["indeed", "linkedin", "glassdoor"]},
    {"discovery_family": "Software Engineer Fresher",  "search_term": "software engineer fresher",  "location": "India", "sites": ["indeed", "linkedin", "glassdoor"]},
    {"discovery_family": "SDE Fresher",                "search_term": "sde fresher",                "location": "India", "sites": ["indeed", "linkedin"]},
    {"discovery_family": "Junior Developer",           "search_term": "junior software developer",  "location": "India", "sites": ["indeed", "linkedin", "glassdoor"]},
    {"discovery_family": "Graduate Trainee",           "search_term": "graduate software trainee",  "location": "India", "sites": ["indeed", "linkedin"]},
    {"discovery_family": "Java Developer",             "search_term": "java developer fresher",     "location": "India", "sites": ["indeed", "linkedin"]},
    {"discovery_family": "Python Developer",           "search_term": "python developer fresher",   "location": "India", "sites": ["indeed", "linkedin"]},
    {"discovery_family": "Full Stack",                 "search_term": "full stack developer fresher", "location": "India", "sites": ["indeed", "linkedin"]},
]

# Optional: residential proxy list. Leave empty for low-volume testing.
# Format: ["http://user:pass@host:port", ...]
PROXIES = []


def clean(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def job_id_from_row(row):
    """Extract a stable ID from the JobSpy row.

    Prefers the platform's own ID from the URL:
    - Indeed: jk=...
    - LinkedIn: /jobs/view/<id>
    - Glassdoor: jobListingId=...
    Falls back to md5(url) if no ID is parseable.
    """
    url = clean(row.get("job_url", ""))
    site = clean(row.get("site", "")).lower()

    if "indeed" in site or "indeed.com" in url:
        m = re.search(r"[?&]jk=([a-zA-Z0-9]+)", url)
        if m:
            return m.group(1)
    if "linkedin" in site or "linkedin.com" in url:
        m = re.search(r"/jobs/view/(\d+)", url)
        if m:
            return m.group(1)
    if "glassdoor" in site or "glassdoor" in url:
        m = re.search(r"jobListingId=(\d+)", url)
        if m:
            return m.group(1)

    return hashlib.md5(url.encode("utf-8")).hexdigest()[:16] if url else ""


def location_from_row(row):
    city = clean(row.get("city", ""))
    state = clean(row.get("state", ""))
    if city and state:
        return f"{city}, {state}"
    return city or state or "India"


def scrape(notifier, target=200, results_wanted=25, hours_old=72):
    t0 = time.time()
    stats = {"new": 0, "skipped": 0, "errors": 0, "blocked": 0}

    db = JobDatabase(str(Path(__file__).resolve().parent.parent / "jobs.db"))
    known_ids = db.get_job_ids(PORTAL)
    notifier.info(f"{PORTAL}: {len(known_ids)} known job IDs in DB")

    all_rows = []

    for idx, profile in enumerate(MANIFEST, 1):
        if stats["new"] >= target:
            break
        label = profile["discovery_family"]
        notifier.info(f"[{idx}/{len(MANIFEST)}] {label}")

        try:
            df = scrape_jobs(
                site_name=profile["sites"],
                search_term=profile["search_term"],
                location=profile["location"],
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="India",
                fetch_description=True,
                proxies=PROXIES if PROXIES else None,
            )
        except Exception as e:
            notifier.warn(f"{PORTAL} {label}: scrape failed ({type(e).__name__}: {e})")
            stats["errors"] += 1
            continue

        if df is None or len(df) == 0:
            notifier.info(f"{PORTAL} {label}: 0 results")
            continue

        notifier.info(f"{PORTAL} {label}: {len(df)} results from {profile['sites']}")

        for _, row in df.iterrows():
            if stats["new"] >= target:
                break

            jid = job_id_from_row(row)
            if not jid:
                stats["errors"] += 1
                continue

            if jid in known_ids:
                stats["skipped"] += 1
                continue

            description = clean(row.get("description", ""))
            if len(description) < 150:
                stats["skipped"] += 1
                continue

            title = clean(row.get("title", ""))
            company = clean(row.get("company", ""))

            # Skip obvious non-entry-level titles early (cheap pre-filter)
            if re.search(r"\b(senior|lead|principal|staff|manager|architect|director)\b",
                         title, re.I):
                stats["skipped"] += 1
                continue

            inserted = db.insert_job({
                "source_portal": PORTAL,
                "source_job_id": jid,
                "job_title": title,
                "company_name": company,
                "location": location_from_row(row),
                "description": description,
                "discovery_family": label,
            })

            if inserted:
                stats["new"] += 1
                known_ids.add(jid)
                all_rows.append({
                    "source_job_id": jid,
                    "site": clean(row.get("site", "")),
                    "job_title": title,
                    "company_name": company,
                    "location": location_from_row(row),
                    "job_url": clean(row.get("job_url", "")),
                    "description_length": len(description),
                    "discovery_family": label,
                })
            else:
                stats["skipped"] += 1

    db.close()

    # Snapshot CSV for auditability
    if all_rows:
        pd.DataFrame(all_rows).to_csv(
            OUTPUT_DIR / f"jobspy_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
            index=False, encoding="utf-8-sig")

    stats["duration"] = time.time() - t0
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--results-per-search", type=int, default=25)
    ap.add_argument("--hours-old", type=int, default=72)
    args = ap.parse_args()

    notifier = Notifier()
    try:
        stats = scrape(
            notifier,
            target=args.target,
            results_wanted=args.results_per_search,
            hours_old=args.hours_old,
        )
        notifier.run_summary(
            PORTAL,
            new=stats["new"],
            skipped=stats["skipped"],
            errors=stats["errors"] + stats["blocked"],
            duration_sec=stats["duration"],
        )
        return 0 if stats["new"] > 0 or stats["skipped"] > 0 else 1
    except Exception as e:
        notifier.error(f"{PORTAL} FATAL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
