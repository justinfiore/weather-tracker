"""Screenshot evidence and a date/source/value index for each browser run."""

from datetime import datetime
import json
from pathlib import Path
import tempfile

from playwright.sync_api import TimeoutError as BrowserTimeout

from weather_tracker.readings import EASTERN, Targets
from weather_tracker.sources import ROWS, URLS


class Evidence:
    def __init__(self, targets: Targets, root=Path(".amp/in/artifacts/collections")):
        date_directory = Path(root) / str(targets.today)
        date_directory.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(
            prefix=targets.observed_at.strftime("%H%M%S.%f%z-"), dir=date_directory,
        ))
        self.targets = targets
        self.data = {"collection_date": str(targets.today), "started_at": targets.observed_at.isoformat(), "sources": {}}

    def record(self, page, source, attempt, reading, observed_at, error):
        record = {
            "attempt": attempt,
            "observed_at": (observed_at or datetime.now(EASTERN)).isoformat(timespec="seconds"),
            "requested_url": URLS[source], "resolved_url": page.url,
            "error": error, "days": {}, "screenshots": {}, "capture_errors": [],
        }
        entry = self.data["sources"].setdefault(source, {"attempts": [], "selected_attempts": {}})
        entry["attempts"].append(record)
        directory = self.path / source / f"attempt-{attempt}"
        directory.mkdir(parents=True, exist_ok=True)

        def screenshot(name, target):
            try:
                path = directory / f"{name}.png"
                target(path)
                record["screenshots"][name] = path.relative_to(self.path).as_posix()
            except Exception:
                record["capture_errors"].append(name)
                print(f"{source}: warning — could not capture {name} screenshot")

        if source == "weather.com":
            menu = page.get_by_role("button", name="Overflow Menu Horizontal More", exact=True)
            try:
                if menu.count() and menu.get_attribute("aria-expanded", timeout=1000) == "true":
                    menu.click(timeout=5000)
            except Exception:
                record["capture_errors"].append("dismiss-menu")
        elif source == "AccuWeather":
            try:
                page.locator('[aria-label="privacy banner"]').wait_for(timeout=3000)
            except BrowserTimeout:
                pass
            else:
                try:
                    page.get_by_role("button", name="Customize Settings", exact=True).click(timeout=5000)
                    page.get_by_role("button", name="Reject All", exact=True).click(timeout=5000)
                    page.locator("#ketch-modal").get_by_role("button", name="Accept", exact=True).click(timeout=5000)
                    page.locator("#ketch-modal").wait_for(state="hidden", timeout=5000)
                except Exception:
                    record["capture_errors"].append("dismiss-privacy")
            try:
                # Server-rendered cards exist before the loading screen clears.
                page.wait_for_function("Array.from(document.querySelectorAll('.daily-wrapper')).every(el => getComputedStyle(el).opacity === '1')", timeout=10000)
            except BrowserTimeout:
                record["capture_errors"].append("forecast-still-loading")
        screenshot("page", lambda path: page.screenshot(path=path, animations="disabled", timeout=15000))
        if source == "NWS":
            screenshot("climate-report", lambda path: page.locator(ROWS[source]).screenshot(path=path, timeout=5000))
        if reading is not None:
            for day, values in reading.days.items():
                if not values.available:
                    continue
                date = str(day)
                record["days"][date] = {
                    "native_unit": values.high.native_unit,
                    "high_f": str(values.high.f), "high_c": str(values.high.c),
                    "low_f": str(values.low.f), "low_c": str(values.low.c),
                }
                entry["selected_attempts"][date] = attempt
                if source == "NWS":
                    continue
                rows = page.locator(ROWS[source])
                label = day.strftime({"weather.com": "%a %d", "AccuWeather": "%-m/%-d", "WTAE": "%B %-d"}[source])
                row = rows.filter(has=page.get_by_text(label, exact=True))

                def card(path):
                    # Center the row above floating video players; screenshot's
                    # default scrolling leaves already-visible rows obscured.
                    row.first.evaluate("async el => { el.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'}); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }")
                    page.screenshot(path=path, animations="disabled", timeout=15000)

                screenshot(date, card)

    def finish_source(self, reading):
        entry = self.data["sources"][reading.source]
        entry["collected_at"] = reading.observed_at.isoformat(timespec="seconds") if reading.available else None
        entry["sheet_date"] = str(self.targets.previous if reading.source == "NWS" else self.targets.today)
        entry["error"] = reading.error
        (self.path / "manifest.json").write_text(json.dumps(self.data, indent=2) + "\n")
        lines = [
            f"# Collection evidence — {self.targets.today}", "",
            f"Run started: {self.targets.observed_at.isoformat(timespec='seconds')} (America/New_York)", "",
            "These are observed readings, not confirmation of a Sheets write. The collector fills only blank cells.",
            "Match the sheet's site, row date, and Collected At timestamp to this index. A later rerun may observe different values.",
            "For retries, selected attempts identify the image used for each target date; the sheet timestamp is the first successful read.", "",
        ]
        for source, details in self.data["sources"].items():
            lines += [f"## {source}", "", f"Sheet row: {details['sheet_date']}; Collected At (Eastern): {details['collected_at'] or 'none'}", "",
                      f"Result: {details['error'] or 'ok'}", ""]
            for record in details["attempts"]:
                lines += [f"### Attempt {record['attempt']} — {record['observed_at']}", "",
                          f"Page: {record['resolved_url']}", ""]
                for date, values in record["days"].items():
                    selected = details["selected_attempts"][date] == record["attempt"]
                    lines.append(f"- {date}: high {values['high_f']}°F / {values['high_c']}°C; low {values['low_f']}°F / {values['low_c']}°C; native {values['native_unit']}; {'selected' if selected else 'superseded by retry'}")
                lines += [f"- [{name}]({path})" for name, path in record["screenshots"].items()]
                if record["error"]:
                    lines.append(f"- Source error: {record['error']}")
                if record["capture_errors"]:
                    lines.append("- Screenshot capture failed: " + ", ".join(record["capture_errors"]))
                lines.append("")
        (self.path / "README.md").write_text("\n".join(lines))
