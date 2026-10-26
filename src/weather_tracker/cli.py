"""One daily collection, with per-source retries and safe operator output."""

import argparse
from datetime import datetime
import random
import shutil
import sys
import time

from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright

from weather_tracker import auth
from weather_tracker.evidence import Evidence
from weather_tracker.readings import EASTERN, Reading, Targets
from weather_tracker.sheets import SheetError, update_sheet
from weather_tracker.sources import ParseError, URLS, collect_source


def collect_all(context, targets, *, sleep=time.sleep, jitter=random.random, evidence=None):
    results = []
    for source in URLS:
        result = Reading(source, targets.observed_at, {}, "Source unavailable")
        parse_failures = 0
        for attempt in range(3):
            candidate = None
            observed_at = None
            page = context.new_page()
            page.set_default_timeout(60000)
            try:
                candidate = collect_source(page, source, targets)
                if candidate.available:
                    observed_at = datetime.now(EASTERN)
                if candidate.available and not result.available:
                    result.observed_at = observed_at
                # Retain partial success if a later retry fails completely.
                result.days.update({day: value for day, value in candidate.days.items() if value.available})
                result.error = candidate.error
                if not result.error:
                    break
                parse_failures += 1
            except ParseError as error:
                result.error = str(error)
                parse_failures += 1
            except Exception:
                # Provider/transport exceptions may include URLs or credentials.
                result.error = "Page unavailable or did not finish rendering"
            finally:
                try:
                    if evidence is not None:
                        evidence.record(page, source, attempt + 1, candidate, observed_at, result.error)
                finally:
                    page.close()
            if parse_failures >= 2 or attempt == 2:
                break
            sleep((2, 8)[attempt] + jitter())
        status = "partial" if result.available and result.error else "ok" if result.available else "failed"
        print(f"{source}: {status}" + (f" — {result.error}" if result.error else ""))
        if evidence is not None:
            evidence.finish_source(result)
        results.append(result)
    if evidence is not None:
        print(f"Screenshot evidence: {evidence.path / 'README.md'}")
    return results


def collect(*, headed=False):
    import os

    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    tab = os.environ.get("GOOGLE_SHEET_TAB", "Daily")
    if not sheet_id:
        raise SheetError("GOOGLE_SHEET_ID is required")
    credentials = auth.credentials()
    targets = Targets(datetime.now(EASTERN))
    with sync_playwright() as p:
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        browser = p.chromium.launch(executable_path=chrome, headless=not headed)
        try:
            with browser.new_context(locale="en-US", timezone_id="America/New_York", viewport={"width": 1280, "height": 720}, device_scale_factor=2) as context:
                results = collect_all(context, targets, evidence=Evidence(targets))
        finally:
            browser.close()
    if not any(result.available for result in results):
        print("No rows written: every source failed", file=sys.stderr)
        return 1
    with build("sheets", "v4", credentials=credentials, cache_discovery=False) as service:
        changed = update_sheet(service.spreadsheets(), sheet_id, tab, targets, results)
    print("Date rows created or updated: " + ", ".join(changed) if changed else "No changes: all collected values already present")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect Pittsburgh forecasts and previous-day actuals into Google Sheets")
    commands = parser.add_subparsers(dest="command", required=True)
    collection = commands.add_parser("collect", help="Collect today's Eastern-date readings and fill blank sheet cells")
    collection.add_argument("--headed", action="store_true", help="Use visible Chrome; requires a graphical display")
    commands.add_parser("auth", help="Authorize the sheet owner with the Sheets-only OAuth scope")
    args = parser.parse_args(argv)
    try:
        if args.command == "auth":
            path = auth.authorize()
            print(f"Refresh token saved securely to {path}; import as project secret SHEETS_REFRESH_TOKEN, then delete the file")
            return 0
        return collect(headed=args.headed)
    except (auth.AuthError, SheetError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Collection failed; check browser installation and Sheets configuration", file=sys.stderr)
        return 1
