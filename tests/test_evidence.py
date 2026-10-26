from datetime import datetime
import json

import pytest

from weather_tracker import cli
from weather_tracker.evidence import Evidence
from weather_tracker.readings import Targets
from weather_tracker.sources import parse_forecast, parse_nws

TARGETS = Targets(datetime.fromisoformat("2026-10-25T06:00:00-04:00"))


@pytest.mark.parametrize("source, fixture", [
    ("weather.com", "weather"), ("AccuWeather", "accuweather"),
    ("WTAE", "wtae"), ("NWS", "nws"),
])
def test_index_links_real_screenshots_to_dates_values_and_sheet_timestamp(page, fixture_html, tmp_path, source, fixture):
    page.set_content(fixture_html(fixture))
    reading = parse_nws(page, TARGETS) if source == "NWS" else parse_forecast(page, source, TARGETS)
    evidence = Evidence(TARGETS, root=tmp_path)
    evidence.record(page, source, 1, reading, TARGETS.observed_at, reading.error)
    evidence.finish_source(reading)
    data = json.loads((evidence.path / "manifest.json").read_text())
    entry = data["sources"][source]
    assert entry["collected_at"] == "2026-10-25T06:00:00-04:00"
    assert entry["sheet_date"] == ("2026-10-24" if source == "NWS" else "2026-10-25")
    record = entry["attempts"][0]
    assert record["capture_errors"] == []
    assert set(record["days"]) == ({"2026-10-24"} if source == "NWS" else {"2026-10-26", "2026-10-30"})
    assert set(record["screenshots"]) == ({"page", "climate-report"} if source == "NWS" else {"page", "2026-10-26", "2026-10-30"})
    index = (evidence.path / "README.md").read_text()
    for relative in record["screenshots"].values():
        assert (evidence.path / relative).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert f"]({relative})" in index
    assert source in index and entry["collected_at"] in index
    assert Evidence(TARGETS, root=tmp_path).path != evidence.path


def test_retry_evidence_retains_partial_reading_and_captures_failed_attempts(browser, fixture_html, monkeypatch, tmp_path):
    evidence = Evidence(TARGETS, root=tmp_path)
    monkeypatch.setattr(cli, "URLS", {"weather.com": cli.URLS["weather.com"]})
    calls = 0

    def source(page, name, targets):
        nonlocal calls
        calls += 1
        page.set_content(fixture_html("weather"))
        if calls > 1:
            raise RuntimeError("provider-private-details")
        page.locator('a[href*="/hourbyhour/day-"]').filter(has_text="Fri 30").evaluate("el => el.remove()")
        return parse_forecast(page, name, targets)

    monkeypatch.setattr(cli, "collect_source", source)
    with browser.new_context() as context:
        results = cli.collect_all(context, TARGETS, sleep=lambda _: None, jitter=lambda: 0, evidence=evidence)
    assert results[0].available and results[0].error
    data = json.loads((evidence.path / "manifest.json").read_text())["sources"]["weather.com"]
    assert data["collected_at"] == results[0].observed_at.isoformat(timespec="seconds")
    assert data["selected_attempts"] == {"2026-10-26": 1}
    assert len(data["attempts"]) == 3
    for record in data["attempts"]:
        assert (evidence.path / record["screenshots"]["page"]).is_file()
    assert data["attempts"][1]["days"] == {}
    assert "provider-private-details" not in (evidence.path / "README.md").read_text()


def test_screenshot_failure_is_reported_without_losing_reading(page, fixture_html, monkeypatch, tmp_path, capsys):
    page.set_content(fixture_html("weather"))
    reading = parse_forecast(page, "weather.com", TARGETS)
    evidence = Evidence(TARGETS, root=tmp_path)
    original_screenshot = page.screenshot
    calls = 0

    def fail(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private screenshot detail")
        return original_screenshot(**kwargs)

    monkeypatch.setattr(page, "screenshot", fail)
    evidence.record(page, "weather.com", 1, reading, TARGETS.observed_at, None)
    evidence.finish_source(reading)
    data = json.loads((evidence.path / "manifest.json").read_text())["sources"]["weather.com"]["attempts"][0]
    assert data["capture_errors"] == ["page"]
    assert data["days"]["2026-10-26"]["low_f"] == "47"
    assert "could not capture page screenshot" in capsys.readouterr().out
    assert "private screenshot detail" not in (evidence.path / "README.md").read_text()
