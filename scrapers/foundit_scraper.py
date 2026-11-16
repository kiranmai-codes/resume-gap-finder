#!/usr/bin/env python3
"""
Foundit scraper — architecture version.
- Incremental (DB-driven)
- Auto-restart on Chrome death
- Notifies on CAPTCHA / errors / summary
- Never crashes the caller
"""
import argparse, asyncio, hashlib, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.db import JobDatabase
from core.browser import BrowserManager
from core.notifier import Notifier
from core.retry import retry

PORTAL = "Foundit"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_PROFILE = os.path.expanduser("~/foundit_gap_finder_chrome_profile")
DEFAULT_CDP_PORT = 9223
TRACKING_KEYS = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","source","src","ref","referrer","clickid","click_id"}
DEFAULT_SEARCH_URLS = [
    {"discovery_family":"Software Developer","mode":"Fresher Query","search_url":"https://www.foundit.in/search/software-developer-jobs?query=software%20developer&queryEntity=Software%20Developer%3ADESIGNATION&experienceRanges=0~0&experience=0&queryDerived=true"},
    {"discovery_family":"Software Engineer","mode":"Fresher Query","search_url":"https://www.foundit.in/search/software-engineer-jobs?query=software%20engineer&queryEntity=Software%20Engineer%3ADESIGNATION&experienceRanges=0~0&experience=0&queryDerived=true"},
]


def clean(v):
    if v is None: return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def canonical_url(url):
    if not url: return ""
    p = urlparse(url)
    host = p.netloc.lower().replace("www.", "")
    path = re.sub(r"/+", "/", p.path).rstrip("/") or "/"
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in TRACKING_KEYS]
    return urlunparse(("https", host, path, "", urlencode(q, doseq=True), ""))


def job_id_from_url(url):
    """Extract job ID from canonical Foundit URL (last numeric segment)."""
    if not url: return ""
    m = re.search(r"-(\d{5,})(?:/|$)", urlparse(url).path)
    return m.group(1) if m else hashlib.md5(url.encode()).hexdigest()[:12]


def looks_like_job_url(url):
    if not url: return False
    p = urlparse(url)
    return ("foundit" in p.netloc.lower()
            and any(m in p.path.lower() for m in ["/job/","/jobs/","/job-detail","/job-details"]))


def looks_like_search_url(url):
    return "/search/" in urlparse(url).path.lower() if url else False


async def extract_candidates(page):
    return await page.evaluate("""
    () => { const out=[]; const seen=new Set();
      for (const a of document.querySelectorAll('a[href]')) {
        const href=a.href||'', text=(a.innerText||a.textContent||'').trim(), h=href.toLowerCase();
        if (!h.includes('foundit')) continue;
        if (!(h.includes('/job/')||h.includes('/jobs/')||h.includes('/job-detail')||h.includes('/job-details'))) continue;
        const key=href.split('#')[0]; if(seen.has(key)) continue; seen.add(key);
        out.push({href, anchor_text:text});
      } return out;
    }
    """)


@retry(max_attempts=3, delay=2, backoff=2, exceptions=(PlaywrightTimeoutError,), context="Foundit search page")
async def load_search_page(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)


async def scrape_detail(page, candidate, provenance):
    """Returns dict of job fields. Never raises."""
    job_url = canonical_url(candidate.get("href", ""))
    jid = job_id_from_url(job_url)
    result = {
        "source_portal": PORTAL,
        "source_job_id": jid,
        "job_url": job_url,
        "job_title": clean(candidate.get("anchor_text", "")),
        "company_name": "", "location": "", "description": "",
        "scrape_status": "unknown", "scrape_error": "",
        "discovery_family": provenance.get("discovery_family", ""),
        "search_url": provenance.get("search_url", ""),
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(1500)
        body = clean(await page.locator("body").inner_text(timeout=10000))

        # Anti-CAPTCHA check
        low = body.lower()
        if any(x in low for x in ["verify you are human", "captcha",
                                   "unusual traffic", "access denied"]):
            result["scrape_status"] = "blocked"
            result["scrape_error"] = "CAPTCHA detected"
            return result

        # Title
        for sel in ["h1", "[data-testid*='job-title']", "[class*='job-title']", "main h1"]:
            try:
                t = clean(await page.locator(sel).first.text_content(timeout=2000))
                if t: result["job_title"] = t; break
            except Exception: pass

        # Description
        desc = ""
        for sel in ["[data-testid*='job-description']", "[class*='job-description']",
                    "[class*='JobDescription']", "article", "main"]:
            try:
                t = clean(await page.locator(sel).first.inner_text(timeout=2500))
                if len(t) >= 150: desc = t; break
            except Exception: pass
        if not desc and len(body) >= 500: desc = body
        result["description"] = desc

        # Company + location from header segment (V1.3 logic preserved)
        title = result["job_title"]
        m = re.search(re.escape(title), body, re.I) if title else None
        if m:
            segment = re.split(r"\s+Job Description\b", body[m.end():], maxsplit=1, flags=re.I)[0]
            exp = re.search(
                r"\b(?:Fresher|\d+\s*(?:-|–|to)\s*\d+\s*Years|\d+\s*\+\s*Years|\d+\s*Years)\b",
                segment, re.I)
            if exp:
                result["company_name"] = clean(segment[:exp.start()])
                tail = segment[exp.end():]
                stop = re.search(
                    r"\s+(?:Early Applicant|Quick Apply|Save|Apply Now|Apply|Posted\b|Login\b)",
                    tail, re.I)
                header_tail = clean(tail[:stop.start()] if stop else tail)
                sal = re.match(
                    r"(₹\s*[^\s].*?\s+LPA|₹\s*[^\s].*?(?:month|year)|Not Disclosed|\$\s*[^\s]+)",
                    header_tail, re.I)
                result["location"] = clean(header_tail[sal.end():] if sal else header_tail)

        result["scrape_status"] = "success" if len(desc) >= 150 else "partial"
        if result["scrape_status"] == "partial":
            result["scrape_error"] = "Short description"
    except PlaywrightTimeoutError as e:
        result["scrape_status"] = "timeout"
        result["scrape_error"] = str(e)[:300]
    except Exception as e:
        result["scrape_status"] = "error"
        result["scrape_error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return result


async def scrape(manifest, output_dir, notifier, target=200, max_pages=10):
    """Main scrape loop. Returns dict of stats."""
    t0 = time.time()
    stats = {"new": 0, "skipped": 0, "errors": 0, "captcha": 0}

    db = JobDatabase(str(Path(__file__).resolve().parent.parent / "jobs.db"))
    known_ids = db.get_job_ids(PORTAL)
    notifier.info(f"{PORTAL}: {len(known_ids)} known job IDs in DB")

    browser = BrowserManager(
        chrome_path=DEFAULT_CHROME,
        profile_dir=DEFAULT_PROFILE,
        cdp_port=DEFAULT_CDP_PORT,
        notifier=notifier,
    )
    await browser.start()

    all_jobs = []
    try:
        page = await browser.get_page()
        for row in manifest:
            if stats["new"] >= target:
                break
            search_url = row["search_url"]
            family_seen = set()

            for pn in range(1, max_pages + 1):
                if stats["new"] >= target:
                    break
                url = search_url + ("&" if "?" in search_url else "?") + f"page={pn}" if pn > 1 else search_url

                try:
                    await load_search_page(page, url)
                    candidates = await extract_candidates(page)
                except Exception as e:
                    notifier.warn(f"{PORTAL} search page {pn} failed: {e}")
                    stats["errors"] += 1
                    break

                urls = {canonical_url(c["href"]) for c in candidates
                        if not looks_like_search_url(canonical_url(c["href"]))}
                new_urls = urls - family_seen

                if not new_urls:
                    notifier.info(f"{PORTAL} page {pn}: no new candidates — stopping")
                    break

                # Incremental: skip candidates whose ID is already known
                for c in candidates:
                    url_c = canonical_url(c.get("href", ""))
                    if not url_c or url_c in family_seen:
                        continue
                    jid = job_id_from_url(url_c)
                    if jid in known_ids:
                        stats["skipped"] += 1
                        continue

                    await browser.ensure_alive()
                    page = await browser.get_page()
                    job = await scrape_detail(page, c, row)
                    all_jobs.append(job)

                    if job["scrape_status"] == "blocked":
                        stats["captcha"] += 1
                        notifier.warn(
                            f"{PORTAL} CAPTCHA on {url_c} — skipping this candidate"
                        )
                        continue

                    if job["scrape_status"] == "success" and len(job["description"]) >= 150:
                        inserted = db.insert_job({
                            "source_portal": PORTAL,
                            "source_job_id": job["source_job_id"],
                            "job_title": job["job_title"],
                            "company_name": job["company_name"],
                            "location": job["location"],
                            "description": job["description"],
                            "discovery_family": job["discovery_family"],
                        })
                        if inserted:
                            stats["new"] += 1
                            known_ids.add(jid)
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["errors"] += 1

                    await asyncio.sleep(0.5)

                family_seen |= urls
                # Early stop: if page is 100% known, next pages likely too
                if new_urls and len(new_urls) < len(urls) * 0.2:
                    notifier.info(f"{PORTAL} page {pn}: >80% known — stopping this family")
                    break
    finally:
        await browser.stop()
        db.close()

    # Save CSV snapshot for auditability
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if all_jobs:
        pd.DataFrame(all_jobs).to_csv(
            output_dir / "foundit_scrape_snapshot.csv",
            index=False, encoding="utf-8-sig")

    stats["duration"] = time.time() - t0
    return stats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="foundit_v1_3_manifest.csv")
    ap.add_argument("--output-dir", default="outputs/foundit")
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--max-pages", type=int, default=10)
    args = ap.parse_args()

    notifier = Notifier()

    if Path(args.manifest).exists():
        manifest = pd.read_csv(args.manifest).fillna("").to_dict("records")
    else:
        manifest = DEFAULT_SEARCH_URLS

    try:
        stats = await scrape(manifest, args.output_dir, notifier,
                             target=args.target, max_pages=args.max_pages)
        notifier.run_summary(
            PORTAL,
            new=stats["new"], skipped=stats["skipped"],
            errors=stats["errors"] + stats["captcha"],
            duration_sec=stats["duration"],
        )
        # Exit code 0 if any progress, 1 if total failure
        return 0 if stats["new"] > 0 or stats["skipped"] > 0 else 1
    except Exception as e:
        notifier.error(f"{PORTAL} FATAL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
