from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from weather_tracker.readings import Daily, Reading, Targets, Temperature
from weather_tracker.sheets import HEADERS, SheetError, update_sheet

TARGETS = Targets(datetime.fromisoformat("2026-10-25T06:00:00-04:00"))


def daily(high="69.4", low="45"):
    return Daily(Temperature.from_native(high, "F"), Temperature.from_native(low, "F"))


def readings():
    results = [
        Reading("weather.com", TARGETS.observed_at, {TARGETS.tomorrow: daily(), TARGETS.five_day: daily("72", "52")}),
        Reading("AccuWeather", TARGETS.observed_at, {TARGETS.tomorrow: daily("68", "43")}),
        Reading("WTAE", TARGETS.observed_at, {}, "failed"),
        Reading("NWS", TARGETS.observed_at, {TARGETS.previous: daily("63", "39")}),
    ]
    for index, result in enumerate(results, 1):
        result.observed_at += timedelta(seconds=index, microseconds=123456)
    return results


class MemorySheet:
    """Small Sheets protocol fake; assertions use final sheet cells, not mocks."""

    def __init__(self):
        self.rows = []
        self.columns = 26
        self.row_count = 1
        self.fail = False

    def get(self, **kwargs):
        if self.fail:
            raise RuntimeError("private provider detail")
        snapshot = {"sheets": [{"properties": {"sheetId": 0, "title": "Daily",
                                               "gridProperties": {"columnCount": self.columns, "rowCount": self.row_count}},
                                "data": [{"rowData": [{"values": deepcopy(row)} for row in self.rows]}]}]}
        return SimpleNamespace(execute=lambda: snapshot)

    def batchUpdate(self, *, body, **kwargs):
        def execute():
            for request in body["requests"]:
                if "appendDimension" in request:
                    dimension = request["appendDimension"]
                    if dimension["dimension"] == "COLUMNS":
                        self.columns += dimension["length"]
                    else:
                        self.row_count += dimension["length"]
                    continue
                update = request["updateCells"]
                r, c = update["start"]["rowIndex"], update["start"]["columnIndex"]
                assert r < self.row_count and c < self.columns
                while len(self.rows) <= r:
                    self.rows.append([])
                while len(self.rows[r]) <= c:
                    self.rows[r].append({})
                cell = deepcopy(update["rows"][0]["values"][0])
                value = next(iter(cell["userEnteredValue"].values()))
                cell["formattedValue"] = str(value)
                self.rows[r][c] = cell
            return {}
        return SimpleNamespace(execute=execute)

    def values(self, index):
        row = self.rows[index]
        return [next(iter(cell.get("userEnteredValue", {}).values()), "") for cell in row] + [""] * (len(HEADERS) - len(row))


def test_forecasts_actuals_partial_failure_and_blank_only_rerun():
    sheet = MemorySheet()
    assert update_sheet(sheet, "test", "Daily", TARGETS, readings()) == ["2026-10-24", "2026-10-25"]
    assert sheet.values(0) == HEADERS
    yesterday, today = sheet.values(1), sheet.values(2)
    assert yesterday == ["2026-10-24"] + [""] * 27 + [63, 17, 39, 4] + ["", "", "", "2026-10-25T06:00:04-04:00"]
    assert today[0:10] == ["2026-10-25", 69.4, 20.8, 45, 7, 72, 22, 52, 11, "2026-10-30"]
    assert today[10:14] == [68, 20, 43, 6]
    assert today[14:32] == [""] * 18
    assert today[32:36] == ["2026-10-25T06:00:01-04:00", "2026-10-25T06:00:02-04:00", "", ""]
    assert sheet.rows[2][1]["userEnteredFormat"]["numberFormat"]["pattern"] == "0.0"
    assert sheet.rows[2][2]["userEnteredFormat"]["numberFormat"]["pattern"] == "0.0"
    assert sheet.rows[2][3]["userEnteredFormat"]["numberFormat"]["pattern"] == "0"

    # Existing numeric zero and a formula displaying blank are still filled cells.
    sheet.rows[2][1] = {"userEnteredValue": {"numberValue": 0}, "formattedValue": "0"}
    sheet.rows[2][2] = {"userEnteredValue": {"formulaValue": '=IF(TRUE,"",1)'}, "formattedValue": ""}
    sheet.rows[2][3] = {"userEnteredValue": {"stringValue": ""}, "formattedValue": ""}
    repeated = readings()
    for result in repeated:
        result.observed_at += timedelta(hours=1)
    repeated[2].days[TARGETS.tomorrow] = daily("66", "41")
    assert update_sheet(sheet, "test", "Daily", TARGETS, repeated) == ["2026-10-25"]
    assert len(sheet.rows) == 3
    assert sheet.values(2)[1:3] == [0, '=IF(TRUE,"",1)']
    assert sheet.values(2)[3] == 45
    assert sheet.values(2)[19:23] == [66, 19, 41, 5]
    assert sheet.values(2)[32:36] == ["2026-10-25T06:00:01-04:00", "2026-10-25T06:00:02-04:00", "2026-10-25T07:00:03-04:00", ""]
    assert sheet.values(1)[35] == "2026-10-25T06:00:04-04:00"
    assert update_sheet(sheet, "test", "Daily", TARGETS, repeated) == []


def test_legacy_headers_extend_without_moving_data_and_timestamps_use_eastern():
    sheet = MemorySheet()
    update_sheet(sheet, "test", "Daily", TARGETS, readings())
    for row in sheet.rows:
        del row[32:]
    before = deepcopy(sheet.rows)
    results = readings()
    results[0].observed_at = datetime.fromisoformat("2026-10-25T23:12:43.987654+00:00")
    update_sheet(sheet, "test", "Daily", TARGETS, results)
    assert sheet.values(0) == HEADERS
    assert HEADERS[32:] == [f"{source} Collected At (Eastern)" for source in ("weather.com", "AccuWeather", "WTAE", "NWS")]
    assert all(row[:32] == old for row, old in zip(sheet.rows, before))
    assert sheet.values(2)[32] == "2026-10-25T19:12:43-04:00"


def test_all_failed_writes_nothing():
    sheet = MemorySheet()
    assert update_sheet(sheet, "test", "Daily", TARGETS, []) == []
    assert sheet.rows == []
    assert sheet.columns == 26


def test_unavailable_and_incompatible_sheet_write_nothing():
    sheet = MemorySheet()
    sheet.fail = True
    with pytest.raises(SheetError, match="test, tab Daily"):
        update_sheet(sheet, "test", "Daily", TARGETS, readings())
    assert sheet.rows == []
    sheet.fail = False
    sheet.rows = [[{"userEnteredValue": {"stringValue": "Unrelated data"}, "formattedValue": "Unrelated data"}]]
    before = deepcopy(sheet.rows)
    with pytest.raises(SheetError, match="headers"):
        update_sheet(sheet, "test", "Daily", TARGETS, readings())
    assert sheet.rows == before
