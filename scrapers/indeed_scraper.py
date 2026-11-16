#!/usr/bin/env python3
"""
Indeed India scraper — architecture version.
- Incremental (skips known job IDs without fetching detail pages)
- Auto-restarts Chrome if it dies mid-run
- Skips CAPTCHA-blocked URLs and notifies — never halts the whole run
- Per-portal try/except — one failure doesn't kill others
"""
import argparse
import asyncio
import hashlib
import os
import random
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.db import JobDatabase
from core.browser import BrowserManager
from core.notifier import Notifier
from core.retry import retry
from core.indeed_taxonomy import (
    clean, now,
    classify_entry_level, classify_career_level, classify_role_relevance,
    classify_role_family, technologies_from_description,
    clean_description_for_extraction, extract_description_from_body,
)

PORTAL = "Indeed"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROFILE = os.path.expanduser("~/indeed_gap_finder_chrome_profile")
DEFAULT_CDP_PORT = 9222

TARGET_DISCOVERED = 500
MAX_DISCOVERY_PAGES = 10
MAX_DETAIL_ATTEMPTS = 500
BLOCK_RECOVERY_ATTEMPTS = 2

SEARCH_MANIFEST = [
    {"discovery_family": "SDE",     "mode": "Fresher Query", "search_url": "https://in.indeed.com/jobs?q=sde+fresher&l=India&from=searchOnHP&vjk=9495519b08aad2d5"},
    {"discovery_family": "SDE",     "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=sde&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09"},
    {"discovery_family": "Software Developer", "mode": "Fresher Query", "search_url": "https://in.indeed.com/jobs?q=software+developer+fresher&l=India&from=searchOnDesktopSerp&vjk=add10afaee68003b"},
    {"discovery_family": "Software Developer", "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=software+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=e77f827aaf550f04"},
    {"discovery_family": "Software Engineer",  "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Software+Engineer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=e77f827aaf550f04"},
    {"discovery_family": "Software Engineer",  "mode": "Fresher Query", "search_url": "https://in.indeed.com/jobs?q=software+engineer+fresher&l=India&from=searchOnDesktopSerp&vjk=e77f827aaf550f04"},
    {"discovery_family": "Graduate Developer","mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Graduate+Software+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba"},
    {"discovery_family": "Junior Developer",   "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Junior+Software+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba"},
    {"discovery_family": "Trainee Engineer",   "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Trainee+Software+Engineer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=b2e46de2c73da3ba"},
    {"discovery_family": "Java Developer",     "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Java+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09"},
    {"discovery_family": "Python Developer",   "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Python+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=7a577c18954a7b09"},
    {"discovery_family": "Full Stack",         "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Full+Stack+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=fc67b785774cc6a7"},
    {"discovery_family": "Frontend",           "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=Frontend+Developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=cccb6badd86f6ae9"},
    {"discovery_family": "Backend",            "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=backend+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=2f7491780401a6cf"},
    {"discovery_family": "MERN Stack",         "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=mern+stack+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=c4283c69c96b2cf0"},
    {"discovery_family": "React Developer",    "mode": "Fresher Filter","search_url": "https://in.indeed.com/jobs?q=react+developer&l=India&sc=0kf%3Aattr%287EQCZ%29%3B&from=searchOnDesktopSerp&vjk=c4283c69c96b2cf0"},
]


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def fake_id(jk):
    if not jk or not jk or not __import__("re").fullmatch(r"[a-z0-9]{16}", jk.lower()):
        return True
    return False


def jk_from_href(href):
    import re
    m = re.search(r"[?&]jk=([A-Za-z0-9]{16})", href or "")
    return m.group(1) if m else ""


def job_url(jk):
    return f"https://in.indeed.com/viewjob?jk={jk}"


async def _txt(locator):
    try:
        if await locator.count():
            return clean(await locator.first.inner_text(timeout=2500))
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────
# Search-page access check
# ─────────────────────────────────────────────────────────

async def wait_for_search_access(page, max_wait_seconds=180):
    interval = 5
    checks = max(1, max_wait_seconds // interval)
    login_signals = ["sign in to continue", "log in to continue", "please sign in",
                     "please log in", "sign in to view", "log in to view"]
    block_signals = ["verify you are human", "captcha", "unusual traffic",
                     "security check", "additional verification required"]

    for check in range(checks + 1):
        try:
            cards = await page.locator("a[data-jk]").count()
            if cards == 0:
                cards = await page.locator("[data-jk]").count()
            if cards > 0:
                return "accessible", cards

            body = clean(await page.locator("body").inner_text(timeout=5000)).lower()
            if any(s in body for s in block_signals):
                return "verification", 0
            if any(s in body for s in login_signals):
                if check < checks:
                    await asyncio.sleep(interval)
                    continue
                return "login_timeout", 0

            if check < checks:
                await asyncio.sleep(interval)
                continue
            return "no_results", 0
        except Exception:
            if check < checks:
                await asyncio.sleep(interval)
                continue
            return "error", 0
    return "error", 0


# ─────────────────────────────────────────────────────────
# Card collection
# ─────────────────────────────────────────────────────────

async def collect_search_jobs(page):
    jobs = {}
    anchors = await page.locator("a[data-jk]").all()
    for a in anchors:
        try:
            jk = clean(await a.get_attribute("data-jk")) or jk_from_href(
                await a.get_attribute("href"))
            title = clean(await a.inner_text())
            if fake_id(jk) or not title:
                continue
            if title.lower() in {"date", "1", "2", "3"}:
                continue
            card = a.locator("xpath=ancestor::*[self::li or self::article][1]")
            company = location = salary = card_text = ""
            if await card.count():
                company = await _txt(card.locator(
                    "[data-testid='company-name'], .companyName, [class*='companyName']"))
                location = await _txt(card.locator(
                    "[data-testid='text-location'], .companyLocation, [class*='companyLocation']"))
                salary = await _txt(card.locator(
                    "[data-testid='attribute_snippet_testid'], [class*='salary-snippet']"))
                card_text = await _txt(card)
            jobs[jk] = {
                "job_id": jk, "job_url": job_url(jk), "job_title": title,
                "company_name": company, "location": location, "salary": salary,
                "search_card_text": card_text,
            }
        except Exception:
            continue
    return list(jobs.values())


# ─────────────────────────────────────────────────────────
# Detail scraping
# ─────────────────────────────────────────────────────────

@retry(max_attempts=2, delay=3, backoff=2, exceptions=(PlaywrightTimeoutError,),
       context="Indeed detail")
async def _load_detail(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)


async def scrape_detail(page, job):
    """Returns dict. Never raises. Handles blocked/unavailable/empty gracefully."""
    result = {
        **job,
        "source_portal": PORTAL,
        "description": "", "clean_description": "", "raw_text": "",
        "scrape_status": "error", "scrape_error": "",
        "entry_level_status": "", "entry_level_reason": "",
        "career_level": "", "experience_min_years": "", "experience_max_years": "",
        "role_relevance": "", "role_relevance_reason": "",
        "role_family": "", "role_family_source": "", "role_family_confidence": "",
        "scraped_at": now(),
    }
    try:
        await _load_detail(page, job["job_url"])
        await asyncio.sleep(random.uniform(2, 4))

        body_raw = await page.locator("body").inner_text(timeout=10000)
        body = clean(body_raw)
        low = body.lower()

        if any(x in low for x in ["verify you are human", "captcha", "unusual traffic",
                                   "security check", "additional verification required"]):
            result["scrape_status"] = "blocked"
            result["scrape_error"] = "Indeed verification"
            return result

        if any(x in low for x in ["this job has expired", "job has expired",
                                   "this job is no longer available",
                                   "we can't find this page", "page not found", "job not found"]):
            result["scrape_status"] = "unavailable"
            result["scrape_error"] = "Expired or removed"
            return result

        description = ""
        for selector in ["#jobDescriptionText",
                         "[data-testid='jobsearch-JobComponent-description']",
                         ".jobsearch-jobDescriptionText",
                         "[class*='jobDescriptionText']"]:
            try:
                loc = page.locator(selector)
                if await loc.count():
                    value = clean(await loc.first.inner_text(timeout=2500))
                    if len(value) >= 150 and value.lower() not in {
                            "full job description", "job description", "about the job"}:
                        description = value
                        break
            except Exception:
                pass

        if not description:
            description = extract_description_from_body(body_raw)

        for sel in ["h1", "[data-testid='jobsearch-JobComponent-title']",
                    "[class*='jobsearch-JobInfoHeader-title']"]:
            t = await _txt(page.locator(sel))
            if t:
                result["job_title"] = t
                break

        company = await _txt(page.locator(
            "[data-testid='inlineHeader-companyName'], "
            "[data-testid='company-name'], [class*='jobsearch-InlineCompanyRating']"))
        location = await _txt(page.locator(
            "[data-testid='inlineHeader-companyLocation'], [data-testid='text-location']"))
        if company:
            result["company_name"] = company
        if location:
            result["location"] = location

        result["description"] = description
        result["clean_description"] = clean_description_for_extraction(description)
        result["raw_text"] = body

        result["entry_level_status"], result["entry_level_reason"] = classify_entry_level(
            result["job_title"], result["clean_description"], result["search_card_text"])
        (result["career_level"], _, _, _,
         result["experience_min_years"], result["experience_max_years"]) = classify_career_level(
            result["job_title"], result["clean_description"], result["search_card_text"])
        result["role_relevance"], result["role_relevance_reason"] = classify_role_relevance(
            result["job_title"], result["clean_description"], result["search_card_text"])
        (result["role_family"], result["role_family_source"],
         result["role_family_confidence"]) = classify_role_family(
            result["job_title"], result["clean_description"])

        if len(description) >= 150:
            result["scrape_status"] = "success"
        elif len(body) >= 500:
            result["scrape_status"] = "partial"
            result["scrape_error"] = "Short description"
        else:
            result["scrape_status"] = "empty"
            result["scrape_error"] = "Very little usable text"
    except Exception as e:
        result["scrape_status"] = "error"
        result["scrape_error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return result


# ─────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────

async def scrape(notifier, target=TARGET_DISCOVERED):
    t0 = time.time()
    stats = {"new": 0, "skipped": 0, "blocked": 0, "errors": 0}

    db = JobDatabase(str(Path(__file__).resolve().parent.parent / "jobs.db"))
    known_ids = db.get_job_ids(PORTAL)
    notifier.info(f"{PORTAL}: {len(known_ids)} known job IDs in DB")

    browser = BrowserManager(
        chrome_path=DEFAULT_CHROME, profile_dir=DEFAULT_PROFILE,
        cdp_port=DEFAULT_CDP_PORT, notifier=notifier)
    await browser.start()

    all_jobs = []
    captured_jk = set()

    try:
        for source_idx, row in enumerate(SEARCH_MANIFEST, 1):
            if stats["new"] >= target:
                break
            search_url = row["search_url"]
            family = row.get("discovery_family", "")
            notifier.info(f"[{source_idx}/{len(SEARCH_MANIFEST)}] {family}")

            # Load first search page
            await browser.ensure_alive()
            page = await browser.get_page()
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(3, 5))
            except Exception as e:
                notifier.warn(f"{PORTAL} {family} navigation failed: {e}")
                stats["errors"] += 1
                continue

            access_state, _ = await wait_for_search_access(page, max_wait_seconds=60)
            if access_state == "verification":
                notifier.warn(f"{PORTAL} {family}: CAPTCHA — skipping this search")
                stats["blocked"] += 1
                continue
            if access_state in {"login_timeout", "no_results", "error"}:
                notifier.warn(f"{PORTAL} {family}: {access_state} — skipping")
                stats["errors"] += 1
                continue

            # Iterate pages
            for pn in range(1, MAX_DISCOVERY_PAGES + 1):
                if stats["new"] >= target:
                    break
                found = await collect_search_jobs(page)
                if not found:
                    break

                new_count = 0
                for job in found:
                    if stats["new"] >= target:
                        break
                    jk = job["job_id"]
                    if jk in captured_jk or jk in known_ids:
                        stats["skipped"] += 1
                        continue
                    captured_jk.add(jk)

                    await browser.ensure_alive()
                    page = await browser.get_page()
                    detail = await scrape_detail(page, job)
                    all_jobs.append(detail)

                    if detail["scrape_status"] == "blocked":
                        stats["blocked"] += 1
                        notifier.warn(f"{PORTAL} blocked on: {job['job_title'][:60]}")
                        continue

                    if (detail["scrape_status"] == "success"
                            and len(detail["description"]) >= 150):
                        inserted = db.insert_job({
                            "source_portal": PORTAL,
                            "source_job_id": jk,
                            "job_title": detail["job_title"],
                            "company_name": detail["company_name"],
                            "location": detail["location"],
                            "description": detail["description"],
                            "discovery_family": family,
                        })
                        if inserted:
                            stats["new"] += 1
                            known_ids.add(jk)
                            new_count += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["errors"] += 1
                    await asyncio.sleep(random.uniform(2, 4))

                # Next page
                try:
                    next_btn = None
                    for sel in ["[aria-label='Next Page']", "a[aria-label='Next Page']",
                                "a[data-testid='pagination-page-next']"]:
                        loc = page.locator(sel)
                        if await loc.count() and await loc.last.is_visible():
                            next_btn = loc.last
                            break
                    if not next_btn:
                        break
                    await next_btn.click()
                    await asyncio.sleep(random.uniform(3, 5))
                except Exception:
                    break

    finally:
        await browser.stop()
        db.close()

    out_dir = Path("outputs/indeed")
    out_dir.mkdir(parents=True, exist_ok=True)
    if all_jobs:
        pd.DataFrame(all_jobs).to_csv(
            out_dir / "indeed_scrape_snapshot.csv",
            index=False, encoding="utf-8-sig")

    stats["duration"] = time.time() - t0
    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=TARGET_DISCOVERED)
    args = ap.parse_args()

    notifier = Notifier()
    try:
        stats = await scrape(notifier, target=args.target)
        notifier.run_summary(
            PORTAL, new=stats["new"], skipped=stats["skipped"],
            errors=stats["errors"] + stats["blocked"],
            duration_sec=stats["duration"])
        return 0 if stats["new"] > 0 or stats["skipped"] > 0 else 1
    except Exception as e:
        notifier.error(f"{PORTAL} FATAL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
