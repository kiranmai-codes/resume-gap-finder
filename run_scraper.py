#!/usr/bin/env python3
"""Runs all scrapers sequentially. Designed for cron/launchd."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.lock import ScraperLock
from core.notifier import Notifier

async def run_jobspy():
    from scrapers.jobspy_scraper import scrape
    from core.notifier import Notifier
    return scrape(Notifier(), target=100)

async def run_foundit():
    from scrapers.foundit_scraper import main as foundit_main
    # Foundit's main() takes args via sys.argv — but for orchestrator,
    # we bypass argparse and call scrape() directly
    from scrapers.foundit_scraper import scrape, DEFAULT_SEARCH_URLS
    import pandas as pd
    manifest_path = Path("foundit_v1_3_manifest.csv")
    manifest = pd.read_csv(manifest_path).fillna("").to_dict("records") \
               if manifest_path.exists() else DEFAULT_SEARCH_URLS
    return await scrape(manifest, "outputs/foundit", Notifier())


async def run_indeed():
    from scrapers.indeed_scraper import scrape
    from core.notifier import Notifier
    return await scrape(Notifier(), target=100)


async def run_naukri():
    from scrapers.naukri_scraper import scrape
    from core.notifier import Notifier
    return await scrape(Notifier(), target=100)




async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--foundit", action="store_true")
    ap.add_argument("--indeed", action="store_true")
    ap.add_argument("--naukri", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    notifier = Notifier()
    lock = ScraperLock(".scraper.lock")
    if not lock.acquire():
        notifier.warn("Another scraper is already running — exiting")
        return 1

    try:
        targets = []
        if args.all or args.jobspy:  targets.append(("JobSpy", run_jobspy))
        if args.all or args.foundit: targets.append(("Foundit", run_foundit))
        if args.all or args.indeed:  targets.append(("Indeed",  run_indeed))
        if args.all or args.naukri:  targets.append(("Naukri",  run_naukri))

        failures = 0
        for name, runner in targets:
            try:
                notifier.info(f"--- Starting {name} ---")
                await runner()
            except Exception as e:
                failures += 1
                notifier.error(f"{name} crashed: {type(e).__name__}: {e}")

        if not args.quiet:
            if failures == 0:
                notifier.success("All scrapers finished without crashes")
            else:
                notifier.error(f"{failures}/{len(targets)} scrapers crashed")
        return 0 if failures == 0 else 1
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
