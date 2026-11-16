#!/usr/bin/env python3
"""
Naukri scraper — architecture version.
- Uses real Chrome (CDP), not headless — Naukri serves empty pages to headless
- 8s wait + scroll for JS render (diagnostic-confirmed selectors)
- Incremental: skips known job IDs from DB without fetching detail
- Saves to jobs.db + V9-compatible CSVs for V10
"""
import argparse
import asyncio
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.db import JobDatabase
from core.browser import BrowserManager
from core.notifier import Notifier
from core.retry import retry

PORTAL = "Naukri"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROFILE = str(Path(__file__).resolve().parent.parent / ".naukri_scraper_profile")
DEFAULT_CDP_PORT = 9224
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "naukri_v9"
MAX_PAGES_PER_URL = 10

MANIFEST = [
    ("generic", "Generic SD Fresher", "https://www.naukri.com/software-developer-jobs-in-india?k=software%20developer&l=india&experience=0"),
    ("generic", "Generic SE Fresher", "https://www.naukri.com/software-engineer-jobs-in-india?k=software%20engineer&l=india&experience=0"),
    ("backend", "Backend", "https://www.naukri.com/backend-developer-jobs-in-india?k=backend%20developer&l=india&experience=0"),
    ("frontend", "Frontend", "https://www.naukri.com/frontend-developer-jobs-in-india?k=frontend%20developer&l=india&experience=0"),
    ("full_stack", "Full Stack", "https://www.naukri.com/full-stack-developer-jobs-in-india?k=full%20stack%20developer&l=india&experience=0"),
    ("mobile", "Android/Mobile", "https://www.naukri.com/android-developer-mobile-developer-jobs-in-india?k=android%20developer%2C%20mobile%20developer&l=india&experience=0"),
    ("technology", "Java", "https://www.naukri.com/java-developer-jobs-in-india?k=java%20developer&l=india&experience=0"),
    ("technology", "Python", "https://www.naukri.com/python-developer-jobs-in-india?k=python%20developer&l=india&experience=0"),
    ("technology", ".NET", "https://www.naukri.com/dot-net-developer-jobs-in-india?k=.net%20developer&l=india&experience=0"),
    ("technology", "PHP", "https://www.naukri.com/php-developer-jobs-in-india?k=php%20developer&l=india&experience=0"),
    ("trainee", "Software Trainee", "https://www.naukri.com/software-trainee-jobs-in-india?k=software%20trainee&l=india&experience=0"),
    ("trainee", "Graduate Trainee", "https://www.naukri.com/graduate-trainee-jobs-in-india?k=graduate%20trainee&l=india&experience=0"),
    ("graduation_year", "2026 Graduates", "https://www.naukri.com/2026-jobs-in-india?k=2026&l=india&experience=0"),
]

TECHNOLOGY_ALIASES = {
    "Python": [r"\bpython\b"], "Java": [r"\bjava\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b"],
    "TypeScript": [r"\btypescript\b", r"\bts\b"],
    "C++": [r"\bc\+\+\b", r"\bcpp\b"],
    "C": [r"(?<![A-Za-z0-9+#])c(?!\+\+|#)(?![A-Za-z0-9])"],
    "C#": [r"\bc#\b", r"\bc sharp\b"],
    ".NET": [r"\.net\b", r"\bdot net\b"],
    "ASP.NET": [r"\basp\.net\b", r"\basp net\b"],
    "PHP": [r"\bphp\b"], "Ruby": [r"\bruby\b"],
    "Go": [r"\bgolang\b", r"\bgo language\b"],
    "Kotlin": [r"\bkotlin\b"], "Swift": [r"\bswift\b"], "Rust": [r"\brust\b"],
    "SQL": [r"\bsql\b"], "MySQL": [r"\bmysql\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b"],
    "Oracle": [r"\boracle(?: database| db)?\b"],
    "SQL Server": [r"\bsql server\b", r"\bmssql\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo db\b"],
    "Redis": [r"\bredis\b"],
    "React": [r"\breact(?:\.js|js)?\b"], "Angular": [r"\bangular(?:\.js|js)?\b"],
    "Vue.js": [r"\bvue(?:\.js|js)?\b"], "Node.js": [r"\bnode(?:\.js|js)?\b"],
    "HTML": [r"\bhtml5?\b"], "CSS": [r"\bcss3?\b"],
    "jQuery": [r"\bjquery\b"], "Bootstrap": [r"\bbootstrap\b"],
    "Django": [r"\bdjango\b"], "Flask": [r"\bflask\b"],
    "FastAPI": [r"\bfastapi\b"], "Spring": [r"\bspring\b"],
    "Spring Boot": [r"\bspring boot\b"], "Laravel": [r"\blaravel\b"],
    "REST API": [r"\brest(?:ful)?\s+apis?\b"], "GraphQL": [r"\bgraphql\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"], "Azure": [r"\bazure\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b"], "Docker": [r"\bdocker\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Jenkins": [r"\bjenkins\b"], "Git": [r"\bgit\b"], "Linux": [r"\blinux\b"],
    "Agile": [r"\bagile\b"], "Scrum": [r"\bscrum\b"],
    "Machine Learning": [r"\bmachine learning\b"],
    "Data Structures": [r"\bdata structures?\b"],
    "Algorithms": [r"\balgorithms?\b"],
    "OOP": [r"\boop\b", r"\bobject[- ]oriented\b"],
}


def clean(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def normalize_job_url(url):
    if not url:
        return ""
    from urllib.parse import urlparse, urlunparse
    p = urlparse(url)
    return urlunparse(("https", "www.naukri.com", p.path, "", "", ""))


def classify_entry_level(title, description):
    text = f"{title} {description}".lower()
    title_low = title.lower()
    if re.search(r"\b(senior|lead|principal|staff|manager|architect)\b", title_low):
        return "not_entry_level"
    if re.search(r"\b(fresher|entry[- ]level|0 years|0-1 years|0-2 years|"
                 r"graduate trainee|intern|recent graduate|campus)\b", text):
        return "confirmed_entry_level"
    min_exp = None
    m = re.search(r"\b(\d+)\s*(?:-|–|to)\s*\d+\s*years?\b", text)
    if m:
        min_exp = int(m.group(1))
    if min_exp is not None and min_exp > 0:
        return "not_entry_level"
    if re.search(r"\b(?:minimum|at least)\s*[1-9]\d*\s*years?\b", text):
        return "not_entry_level"
    return "ambiguous"


def classify_role_family(title):
    t = title.lower()
    if re.search(r"\b(machine learning|ml|ai)\b", t): return "AI / ML"
    if re.search(r"\bdata\s+(?:engineer|scientist|analyst)\b", t): return "Data Engineering"
    if re.search(r"\b(devops|sre|site reliability)\b", t): return "DevOps / Infrastructure"
    if re.search(r"\b(qa|test|sdet|automation engineer)\b", t): return "QA / Testing"
    if re.search(r"\b(android|ios|mobile)\s+(developer|engineer)\b", t): return "Mobile"
    if re.search(r"\b(embedded|firmware)\b", t): return "Embedded"
    if re.search(r"\bfront[\s-]?end\b", t): return "Frontend"
    if re.search(r"\bback[\s-]?end\b", t): return "Backend"
    if re.search(r"\bfull[\s-]?stack\b", t): return "Full Stack"
    if re.search(r"\b(software|application|programmer)\b", t): return "General Software Development"
    return "Unclear"


def extract_techs(text):
    found = []
    text_low = text.lower()
    for tech, patterns in TECHNOLOGY_ALIASES.items():
        for p in patterns:
            if re.search(p, text_low, re.I):
                found.append(tech)
                break
    return found


async def extract_card_data(page):
    """Extract jobs from a loaded search page. Uses diagnostic-confirmed selectors."""
    jobs = []
    try:
        wrappers = await page.locator("div.srp-jobtuple-wrapper").all()
    except Exception:
        wrappers = []
    if not wrappers:
        try:
            wrappers = await page.locator("div.cust-job-tuple").all()
        except Exception:
            wrappers = []

    for card in wrappers:
        try:
            job_id = clean(await card.get_attribute("data-job-id"))
            if not job_id:
                continue

            title_loc = card.locator("a.title, h2 a")
            if await title_loc.count() == 0:
                continue
            title = clean(await title_loc.first.inner_text())
            href = await title_loc.first.get_attribute("href") or ""
            if not title or not href:
                continue

            company = ""
            comp_loc = card.locator("a.comp-name, [class*='comp-name']")
            if await comp_loc.count():
                company = clean(await comp_loc.first.inner_text())

            location = ""
            loc_loc = card.locator(".locWdth, [class*='locWdth']")
            if await loc_loc.count():
                location = clean(await loc_loc.first.inner_text())

            snippet = ""
            desc_loc = card.locator(".job-desc, [class*='job-desc']")
            if await desc_loc.count():
                snippet = clean(await desc_loc.first.inner_text())

            jobs.append({
                "source_job_id": job_id,
                "job_title": title,
                "job_url": normalize_job_url(href) or href,
                "company_name": company,
                "location": location,
                "card_snippet": snippet,
            })
        except Exception:
            continue
    return jobs


@retry(max_attempts=2, delay=3, exceptions=(PlaywrightTimeoutError,), context="Naukri detail")
async def _navigate_detail(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(3000)


async def scrape_detail(page, job):
    result = {
        "source_portal": PORTAL,
        "source_job_id": job["source_job_id"],
        "job_url": job["job_url"],
        "job_title": job["job_title"],
        "company_name": job["company_name"],
        "location": job["location"],
        "description": job.get("card_snippet", ""),
        "scrape_status": "unknown",
        "scrape_error": "",
        "discovery_family": "",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await _navigate_detail(page, job["job_url"])
        body = clean(await page.locator("body").inner_text(timeout=8000))
        low = body.lower()

        if any(x in low for x in ["captcha", "unusual traffic",
                                   "access denied", "blocked"]):
            result["scrape_status"] = "blocked"
            result["scrape_error"] = "CAPTCHA"
            return result

        for sel in ["h1.jd-header-title", "[class*='jd-header-title']", "h1"]:
            el = page.locator(sel)
            if await el.count():
                t = clean(await el.first.inner_text())
                if t and len(t) > 3:
                    result["job_title"] = t
                    break

        for sel in ["a.jd-header-comp-name", ".jd-header-comp-name",
                    "[class*='comp-name']"]:
            el = page.locator(sel)
            if await el.count():
                c = clean(await el.first.inner_text())
                if c:
                    result["company_name"] = c
                    break

        desc = ""
        for sel in ["section.job-desc", ".dang-inner-html",
                    "[class*='job-desc']"]:
            el = page.locator(sel)
            if await el.count():
                d = clean(await el.first.inner_text())
                if len(d) > 100:
                    desc = d
                    break

        if desc and len(desc) >= 150:
            result["description"] = desc
            result["scrape_status"] = "success"
        elif desc and len(desc) >= 100:
            result["description"] = desc
            result["scrape_status"] = "partial"
        elif len(result["description"]) >= 150:
            result["scrape_status"] = "partial"
            result["scrape_error"] = "Detail not found; using card snippet"
        else:
            result["scrape_status"] = "error"
            result["scrape_error"] = "Description too short"
    except Exception as e:
        result["scrape_status"] = "error"
        result["scrape_error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return result


async def find_next_page_url(page):
    try:
        for sel in ["a[aria-label='Next Page']", "a.next", "a:has-text('Next')",
                    "a[class*='next']"]:
            loc = page.locator(sel)
            if await loc.count():
                href = await loc.first.get_attribute("href")
                if href:
                    return normalize_job_url(href) or href
    except Exception:
        pass
    return None


async def scrape(notifier, target=200, max_pages=MAX_PAGES_PER_URL):
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

    try:
        for source_idx, (family, label, search_url) in enumerate(MANIFEST, 1):
            if stats["new"] >= target:
                break
            notifier.info(f"[{source_idx}/{len(MANIFEST)}] {label}")

            await browser.ensure_alive()
            page = await browser.get_page()

            try:
                await page.goto(search_url, wait_until="domcontentloaded",
                                timeout=45000)
                await page.wait_for_timeout(8000)
                for _ in range(3):
                    await page.mouse.wheel(0, 1500)
                    await page.wait_for_timeout(800)
            except Exception as e:
                notifier.warn(f"{PORTAL} {label}: navigation failed ({e})")
                stats["errors"] += 1
                continue

            current_url = search_url

            for pn in range(1, max_pages + 1):
                if stats["new"] >= target:
                    break

                cards = await extract_card_data(page)

                if not cards:
                    if pn == 1:
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        debug_path = OUTPUT_DIR / f"debug_{label.replace(' ', '_')}_p1.png"
                        try:
                            await page.screenshot(path=str(debug_path))
                            notifier.warn(
                                f"{PORTAL} {label}: 0 cards on page 1 — "
                                f"debug screenshot: {debug_path}")
                        except Exception:
                            pass
                    break

                for card in cards:
                    if stats["new"] >= target:
                        break
                    jid = card["source_job_id"]
                    if jid in known_ids:
                        stats["skipped"] += 1
                        continue

                    await browser.ensure_alive()
                    page = await browser.get_page()
                    detail = await scrape_detail(page, card)
                    detail["discovery_family"] = family
                    all_jobs.append(detail)

                    if detail["scrape_status"] == "blocked":
                        stats["blocked"] += 1
                        continue

                    if (detail["scrape_status"] in ("success", "partial")
                            and len(detail["description"]) >= 100):
                        inserted = db.insert_job({
                            "source_portal": PORTAL,
                            "source_job_id": jid,
                            "job_title": detail["job_title"],
                            "company_name": detail["company_name"],
                            "location": detail["location"],
                            "description": detail["description"],
                            "discovery_family": family,
                        })
                        if inserted:
                            stats["new"] += 1
                            known_ids.add(jid)
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["errors"] += 1

                    await asyncio.sleep(1.5)

                next_url = await find_next_page_url(page)
                if not next_url or next_url == current_url:
                    break
                current_url = next_url
                try:
                    await page.goto(next_url, wait_until="domcontentloaded",
                                    timeout=45000)
                    await page.wait_for_timeout(6000)
                except Exception:
                    break
    finally:
        await browser.stop()
        db.close()

    # CSV output for V10 backward compat
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if all_jobs:
        jobs_rows = []
        tech_rows = []
        for j in all_jobs:
            entry = classify_entry_level(j["job_title"], j["description"])
            family = classify_role_family(j["job_title"])
            career = "early_career" if entry == "confirmed_entry_level" else "unknown"
            jobs_rows.append({
                "source_job_id": j["source_job_id"],
                "job_title": j["job_title"],
                "company_name": j["company_name"],
                "location": j["location"],
                "description": j["description"],
                "entry_level_status": entry,
                "career_level": career,
                "role_family": family,
                "scrape_status": j["scrape_status"],
                "discovery_family": j.get("discovery_family", ""),
            })
            for tech in extract_techs(j["description"]):
                tech_rows.append({
                    "source_job_id": j["source_job_id"],
                    "job_title": j["job_title"],
                    "company_name": j["company_name"],
                    "technology": tech,
                    "technology_context": "General",
                    "role_family": family,
                    "requirement_type": "mentioned",
                    "benchmark_eligible": entry == "confirmed_entry_level",
                })

        pd.DataFrame(jobs_rows).to_csv(
            OUTPUT_DIR / "naukri_clean_jobs_v9.csv",
            index=False, encoding="utf-8-sig")
        pd.DataFrame(tech_rows).to_csv(
            OUTPUT_DIR / "naukri_technologies_v9.csv",
            index=False, encoding="utf-8-sig")
        notifier.info(f"{PORTAL}: wrote {len(jobs_rows)} jobs + {len(tech_rows)} tech rows to CSVs")

    stats["duration"] = time.time() - t0
    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_URL)
    args = ap.parse_args()

    notifier = Notifier()
    try:
        stats = await scrape(notifier, target=args.target,
                             max_pages=args.max_pages)
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
    sys.exit(asyncio.run(main()))
