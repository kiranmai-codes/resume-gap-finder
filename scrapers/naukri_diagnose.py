#!/usr/bin/env python3
"""Diagnostic — visits one Naukri search page, saves screenshot + HTML."""
import argparse
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = ("https://www.naukri.com/software-developer-jobs-in-india"
       "?k=software%20developer&l=india&experience=0")
OUT = Path("outputs/naukri_diagnostic")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(Path(".naukri_diagnostic_profile").resolve()),
            headless=not args.headed,
            viewport={"width": 1440, "height": 900})
        page = browser.pages[0] if browser.pages else browser.new_page()

        print(f"Loading: {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        print("Waiting 10s for JS to render...")
        page.wait_for_timeout(10000)

        # Save screenshot
        page.screenshot(path=str(OUT / "naukri_page.png"), full_page=True)
        print(f"Screenshot: {OUT / 'naukri_page.png'}")

        # Save HTML
        html = page.content()
        (OUT / "naukri_page.html").write_text(html, encoding="utf-8")
        print(f"HTML: {OUT / 'naukri_page.html'} ({len(html):,} bytes)")

        # Diagnose
        title = page.title()
        print(f"\nPage title: {title}")

        checks = {
            "a[href*='job-listings']": page.locator("a[href*='job-listings']").count(),
            "div.srp-jobtuple-wrapper": page.locator("div.srp-jobtuple-wrapper").count(),
            "article.jobTuple": page.locator("article.jobTuple").count(),
            "div.cust-job-tuple": page.locator("div.cust-job-tuple").count(),
            "a.title": page.locator("a.title").count(),
            "h2 a": page.locator("h2 a").count(),
            "[class*='jobTuple']": page.locator("[class*='jobTuple']").count(),
            "[class*='tuple']": page.locator("[class*='tuple']").count(),
            "[data-job-id]": page.locator("[data-job-id]").count(),
        }
        print("\nSelector counts:")
        for sel, n in checks.items():
            flag = " ✓" if n > 0 else ""
            print(f"  {n:5d}  {sel}{flag}")

        body = page.locator("body").inner_text()[:800]
        print("\nPage text preview (first 800 chars):")
        print(body)

        browser.close()
        print(f"\n✅ Diagnostic saved. Share the screenshot + the selector counts above.")


if __name__ == "__main__":
    main()
