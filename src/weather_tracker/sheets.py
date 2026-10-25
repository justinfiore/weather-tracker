"""Blank-only, numeric Google Sheets updates for collection-date rows."""

from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import os

from weather_tracker.readings import EASTERN, FORECAST_SOURCES, Targets

FORECAST_COLUMNS = (
    "Next Day High (F)", "Next Day High (C)", "Next Day Low (F)", "Next Day Low (C)",
    "5-Day High (F)", "5-Day High (C)", "5-Day Low (F)", "5-Day Low (C)", "5-Day Date",
)
HEADERS = ["Date"] + [f"{source} {column}" for source in FORECAST_SOURCES for column in FORECAST_COLUMNS] + [
    "NWS Actual High (F)", "NWS Actual High (C)", "NWS Actual Low (F)", "NWS Actual Low (C)",
    *[f"{source} Collected At (Eastern)" for source in (*FORECAST_SOURCES, "NWS")],
]


class SheetError(RuntimeError):
    pass


@contextmanager
def _destination_lock(sheet_id, tab):
    # Serialize manual and scheduled writers in the same orb through read+write.
    key = hashlib.sha256(f"{sheet_id}/{tab}".encode()).hexdigest()
    fd = os.open(f"/tmp/weather-tracker-sheet-{key}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _values(day):
    return [day.high.f, day.high.c, day.low.f, day.low.c]


def update_sheet(api, sheet_id: str, tab: str, targets: Targets, readings) -> list[str]:
    """Return changed date rows. One atomic batch writes only previously blank cells.

    Do not run separate collector orbs against the same tab concurrently: Sheets
    has no compare-and-swap operation across a read and a batch update.
    """
    desired = {}
    for reading in readings:
        if reading.source in FORECAST_SOURCES:
            offset = 1 + FORECAST_SOURCES.index(reading.source) * 9
            for target, start in ((targets.tomorrow, offset), (targets.five_day, offset + 4)):
                day = reading.days.get(target)
                if day is not None and day.available:
                    row = desired.setdefault(str(targets.today), {})
                    row.update(enumerate(_values(day), start))
                    row[32 + FORECAST_SOURCES.index(reading.source)] = reading.observed_at.astimezone(EASTERN).isoformat(timespec="seconds")
                    if target == targets.five_day:
                        row[offset + 8] = str(target)
        elif reading.source == "NWS":
            day = reading.days.get(targets.previous)
            if day is not None and day.available:
                row = desired.setdefault(str(targets.previous), {})
                row.update(enumerate(_values(day), 28))
                row[35] = reading.observed_at.astimezone(EASTERN).isoformat(timespec="seconds")
    if not desired:
        return []
    try:
        with _destination_lock(sheet_id, tab):
            escaped_tab = "'" + tab.replace("'", "''") + "'"
            workbook = api.get(spreadsheetId=sheet_id, ranges=[escaped_tab], includeGridData=True).execute()
            sheet = next(sheet for sheet in workbook["sheets"] if sheet["properties"]["title"] == tab)
            sheet_number = sheet["properties"]["sheetId"]
            rows = sheet.get("data", [{}])[0].get("rowData", [])
            cells = [row.get("values", []) for row in rows]
            nonempty = lambda cell: any(value != "" for value in cell.get("userEnteredValue", cell.get("effectiveValue", {})).values())
            header_start = 0
            if cells and any(nonempty(cell) for cell in cells[0]):
                header = [cell.get("formattedValue", "") for cell in cells[0]]
                if header[:len(HEADERS)] == HEADERS and not any(header[len(HEADERS):]):
                    header_start = len(HEADERS)
                elif header[:32] == HEADERS[:32] and not any(header[32:]):
                    header_start = 32
                else:
                    raise SheetError("Tab headers do not match weather-tracker; use an empty tab")
            elif any(nonempty(cell) for row in cells[1:] for cell in row):
                raise SheetError("Tab has data without headers; use an empty tab")
            requests = []
            grid = sheet["properties"]["gridProperties"]
            if grid["columnCount"] < len(HEADERS):
                requests.append({"appendDimension": {"sheetId": sheet_number, "dimension": "COLUMNS",
                                                       "length": len(HEADERS) - grid["columnCount"]}})

            def write(row, col, value):
                cell = {"userEnteredValue": {"stringValue": value}}
                fields = "userEnteredValue"
                if isinstance(value, Decimal):
                    places = max(0, -value.as_tuple().exponent)
                    cell = {"userEnteredValue": {"numberValue": float(value)},
                            "userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0" + ("." + "0" * places if places else "")}}}
                    fields += ",userEnteredFormat.numberFormat"
                requests.append({"updateCells": {"start": {"sheetId": sheet_number, "rowIndex": row, "columnIndex": col},
                                                  "rows": [{"values": [cell]}], "fields": fields}})

            for col in range(header_start, len(HEADERS)):
                write(0, col, HEADERS[col])
            dates = {}
            for index, row in enumerate(cells[1:], 1):
                day = row[0].get("formattedValue", "") if row else ""
                if day:
                    if day in dates:
                        raise SheetError("Duplicate date rows; resolve duplicates before collecting")
                    dates[day] = index
            changed = []
            next_row = max(1, len(cells))
            for day, values in sorted(desired.items()):
                index = dates.get(day)
                if index is None:
                    index = next_row
                    next_row += 1
                    write(index, 0, day)
                old = cells[index] if index < len(cells) else []
                before = len(requests)
                for col, value in values.items():
                    if col >= len(old) or not nonempty(old[col]):
                        write(index, col, value)
                if len(requests) > before:
                    changed.append(day)
            if requests:
                if next_row > grid["rowCount"]:
                    requests.insert(0, {"appendDimension": {"sheetId": sheet_number, "dimension": "ROWS",
                                                            "length": next_row - grid["rowCount"]}})
                api.batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
            return changed
    except SheetError:
        raise
    except Exception:
        raise SheetError(f"Could not open or update spreadsheet {sheet_id}, tab {tab}") from None
