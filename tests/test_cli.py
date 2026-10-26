from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace

import pytest

from weather_tracker import cli
from weather_tracker.readings import Reading
from weather_tracker.sources import ParseError
from test_sheets import MemorySheet, TARGETS, readings


def test_retries_continue_and_report_success(browser, monkeypatch, capsys):
    calls = {}
    waits = []
    instants = [datetime.fromisoformat(value) for value in ("2026-10-25T06:00:03-04:00", "2026-10-25T06:00:08-04:00")]
    clock = iter(instants)
    monkeypatch.setattr(cli, "datetime", SimpleNamespace(now=lambda timezone: next(clock)))

    def source(page, name, targets):
        calls[name] = calls.get(name, 0) + 1
        if name == "weather.com" and calls[name] == 1 or name == "WTAE":
            raise TimeoutError("provider detail")
        if name == "NWS":
            raise ParseError("Summary absent")
        return next(result for result in readings() if result.source == name)

    monkeypatch.setattr(cli, "collect_source", source)
    with browser.new_context() as context:
        results = cli.collect_all(context, TARGETS, sleep=waits.append, jitter=lambda: 0.25)
    assert [result.source for result in results if result.available] == ["weather.com", "AccuWeather"]
    assert [result.observed_at for result in results if result.available] == instants
    assert calls == {"weather.com": 2, "AccuWeather": 1, "WTAE": 3, "NWS": 2}
    assert waits == [2.25, 2.25, 8.25, 2.25]
    output = capsys.readouterr().out
    assert "weather.com: ok" in output
    assert "AccuWeather: ok" in output
    assert "WTAE: failed" in output
    assert "provider detail" not in output


@pytest.mark.parametrize("state, expected, message", [
    ("new", 0, "Date rows created or updated"),
    ("present", 0, "all collected values already present"),
    ("failed", 1, "every source failed"),
    ("unavailable", 1, "Could not open or update spreadsheet"),
])
def test_collect_command_exit_codes(browser, monkeypatch, capsys, tmp_path, state, expected, message):
    monkeypatch.chdir(tmp_path)
    sheet = MemorySheet()
    results = readings()
    if state == "present":
        cli.update_sheet(sheet, "test", "Daily", TARGETS, results)
    if state == "failed":
        results = [Reading("NWS", TARGETS.observed_at, {}, "Unavailable")]
    sheet.fail = state == "unavailable"
    monkeypatch.setenv("GOOGLE_SHEET_ID", "test")
    monkeypatch.setenv("GOOGLE_SHEET_TAB", "Daily")
    monkeypatch.setattr(cli.auth, "credentials", lambda: object())
    monkeypatch.setattr(cli, "Targets", lambda instant: TARGETS)
    monkeypatch.setattr(cli, "collect_all", lambda *args, **kwargs: results)
    # Share the fixture's Playwright runtime instead of nesting sync runtimes.
    instance = SimpleNamespace(new_context=browser.new_context, close=lambda: None)
    runtime = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: instance))
    monkeypatch.setattr(cli, "sync_playwright", lambda: nullcontext(runtime))

    class Service:
        def spreadsheets(self):
            return sheet

    monkeypatch.setattr(cli, "build", lambda *args, **kwargs: nullcontext(Service()))
    assert cli.main(["collect"]) == expected
    output = capsys.readouterr()
    assert message in output.out + output.err
    assert "private provider detail" not in output.err
    if expected == 1:
        assert sheet.rows == []


def test_auth_command_never_prints_token(monkeypatch, tmp_path, capsys):
    path = tmp_path / "token"
    path.write_text("do-not-print")
    monkeypatch.setattr(cli.auth, "authorize", lambda: path)
    assert cli.main(["auth"]) == 0
    output = capsys.readouterr().out
    assert str(path) in output
    assert "do-not-print" not in output
