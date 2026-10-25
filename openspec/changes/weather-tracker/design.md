# Design

## Context

The package is a Poetry project on Python 3.13 with no application code yet. See proposal.md for why the collector exists. Behavior is in the four delta specs.

The control actuals are the Pittsburgh daily climate report shown on weather.gov/wrh/Climate?wfo=pbz for Pittsburgh, Pennsylvania. A live station observation is not the same number.

weather.com and AccuWeather publish paid forecast APIs. Those APIs are not used. All four weather sources are read from the pages a person would open. Google Sheets is the only API.

The sheet write uses the same Google Cloud OAuth app as cubscouts. That app's client file is already stored as the weather-tracker Amp project secret `GWS_AUTH`, copied from cubscouts without printing the value. Amp's own Google Sheets connection is not available in this account. The sheet user is a different Google account from the cubscouts user, so this project gets its own consent and refresh token.

## Goals / Non-Goals

**Goals:**

- One CLI run collects all sources, retries failures, and updates the date rows.
- Each source is a browser adapter behind the same reading type, so a page change does not change the sheet.
- A scheduled orb can run the CLI at 6:00 a.m. America/New_York without a person at the keyboard.

**Non-Goals:**

- Drawing the charts. The sheet stores one number per cell so charting is possible later.
- A GitHub Actions cron.
- Weather data APIs, including api.weather.gov, api.weather.com, and the AccuWeather API.

## Decisions

### Browser adapters

Each source implements one function: given an observation time, open its page in Playwright and return the high and low for the target dates, or a typed failure. One browser run visits the four pages in sequence. It does not call a weather data API, including a JSON endpoint discovered behind the page.

- weather.com: open the Pittsburgh, PA forecast page and read the rendered high and low for the next local date and the local date plus five.
- AccuWeather: open the Pittsburgh, PA daily forecast page and read those same rendered dates.
- WTAE: open `https://www.wtae.com/weather`, set the location to Pittsburgh, PA if the page does not already show it, and read those same rendered dates.
- NWS: open `https://www.weather.gov/wrh/Climate?wfo=pbz`, select the Daily Climate Report for Pittsburgh, Pennsylvania, and read the previous local date's maximum and minimum. Ignore a summary for any other date.

The unit printed on the page is native. The other unit is converted locally. A page that shows both units still has one native unit: the unit shown first.

Alternative considered: official forecast and climate APIs. Rejected because the weather.com and AccuWeather APIs can cost money, and the procedure names the pages a person would visit. Browser runs are slower and can break when markup changes. That is accepted for a once-daily, three-week collection.

### Calendar dates, not forecast indexes

Target dates are computed in America/New_York before any request: observation date, next date, observation date plus five, previous date. Adapters match forecast periods by calendar date. A period named "day 5" is used only when its date equals the five-day target. A page that labels its fifth forecast day as a different calendar date is not used for that cell. The adapter reads the dated day that matches the target.

### Units

Native means the unit the chosen response published. Conversion is (F − 32) × 5/9 or C × 9/5 + 32. The stored value keeps the source's published precision: 69 stays 69, and 69.4 stays 69.4. The converted unit is rounded half away from zero to that same number of decimal places. Python's `round` half-to-even is not used. Missing values stay missing; they are not converted to zero.

### Google Sheets OAuth

The sheet client uses the OAuth app already stored for cubscouts. Scope for this project is `https://www.googleapis.com/auth/spreadsheets` only. Do not request the broader Google Workspace scopes cubscouts uses, and do not reuse cubscouts' refresh token or encrypted credential blob.

Storage follows cubscouts, with one difference: cubscouts commits encrypted credential blobs because `gws` owns that format. This collector does not use `gws`. It keeps the client in the Amp project secret and keeps this project's refresh token in a separate Amp project secret.

- `GWS_AUTH` is already set on `justinfiore/weather-tracker`. It is the cubscouts secret: one base64 line of JSON whose keys are filenames. The collector reads the `client_secret.json` entry and ignores `.encryption_key`. That key decrypts cubscouts' credential blob and is not used here.
- Setup unpacks `GWS_AUTH` the way cubscouts does: base64-decode, require a JSON object, write `client_secret.json` to a mode-0600 file outside the repo, then unset `GWS_AUTH`. Do not print the payload.
- Consent is a separate command, `weather-tracker auth`. It runs the installed-app flow with the unpacked client, loopback redirect, and the Sheets scope. The Google account that consents is the weather-tracker sheet owner, not the cubscouts account.
- The refresh token from that consent is stored as a new Amp project secret, `SHEETS_REFRESH_TOKEN`. It is not committed and not written into `GWS_AUTH`. Daily runs read that secret from the environment. They do not open a browser.
- If the existing OAuth client has no loopback redirect URI, auth stops and prints only the URI to add in Google Cloud. It does not print the client secret.
- Spreadsheet ID and tab name come from `GOOGLE_SHEET_ID` and `GOOGLE_SHEET_TAB`.

Alternative considered: separate `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` env vars. Rejected so this project stores the client the same way cubscouts does. Alternative considered: reuse cubscouts' encrypted refresh token. Rejected because the sheet must be authorized as a different Google user. Alternative considered: Amp's Google Sheets tools. Rejected because this account has no Google connection.

The sheet tab is created with a header row if the tab exists but is empty. Each data row is one America/New_York collection date. The row holds the forecasts collected that morning. The next morning writes yesterday's NWS actuals onto yesterday's row. Actuals never share a row with the forecasts collected on the actuals' own morning.

Header columns, in order:

Date, then for weather.com, AccuWeather, and WTAE: Next Day High (F), Next Day High (C), Next Day Low (F), Next Day Low (C), 5-Day High (F), 5-Day High (C), 5-Day Low (F), 5-Day Low (C), 5-Day Date. Then NWS Actual High (F), NWS Actual High (C), NWS Actual Low (F), NWS Actual Low (C).

The repeated "High (C)" after each Low (F) in the requested list is Low (C). Tomorrow's date is the row date plus one, so it has no date column. Each site's 5-Day Date is stored so the three sites can be checked against the same calendar date.

A cell is written only when blank. A later run can fill a missing forecast or a missing actual without replacing a value already recorded. Errors are printed by the command. They are not sheet columns. Blank means missing, not zero.

Example after the 2026-10-26 6:00 a.m. Eastern run. The Oct 25 row was created that previous morning. This run fills its actuals and creates the Oct 26 forecast row. Only weather.com and NWS are shown; AccuWeather and WTAE repeat the weather.com columns.

| Date | weather.com Next Day High (F) | Next Day High (C) | Next Day Low (F) | Next Day Low (C) | 5-Day High (F) | 5-Day High (C) | 5-Day Low (F) | 5-Day Low (C) | 5-Day Date | NWS Actual High (F) | NWS Actual High (C) | NWS Actual Low (F) | NWS Actual Low (C) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-25 | 69 | 21 | 45 | 7 | 72 | 22 | 52 | 11 | 2026-10-30 | 63 | 17 | 39 | 4 |
| 2026-10-26 | 70 | 21 | 48 | 9 | 68 | 20 | 49 | 9 | 2026-10-31 |  |  |  |  |

Each temperature is its own column. A cell never contains two numbers such as `69/21`. AccuWeather and WTAE repeat the nine weather.com columns between weather.com and the NWS columns. The Oct 26 actual cells stay blank until the Oct 27 run. If weather.com had published 69.4 instead of 69, the Next Day High (F) cell would be 69.4 and the Next Day High (C) cell would keep one decimal place.

If every source fails, no new row is created and no filled cell changes. If the sheet cannot be opened, the command exits non-zero and writes nothing.

### Retries

Each page gets three attempts. The wait between attempts is 2 seconds, then 8 seconds, plus a small jitter. Retry on timeout and on a page that has not finished rendering. A parse failure is retried once, then recorded as an error. Pages run one after another. One page's exception does not cancel the others.

### CLI and schedule

The command is `weather-tracker collect`. It prints a one-line result per source and a final line naming the date rows created or updated. Exit 0 when the sheet was updated or when every value for this run was already present. Exit 1 when every source failed or the sheet write failed.

The 6:00 a.m. America/New_York schedule is an Amp thread schedule, not cron in the repo. The saved prompt runs `poetry run weather-tracker collect` in this repo and reports the command output. The thread is not archived. The orb receives project secrets `GWS_AUTH` and `SHEETS_REFRESH_TOKEN`, plus the sheet ID. The schedule is created after one consented run has written a row.

DST is the schedule's timezone, America/New_York, not a fixed UTC hour.

### Configuration

Environment variables, no config file required:

- `GWS_AUTH` (Amp project secret; client file only)
- `SHEETS_REFRESH_TOKEN` (Amp project secret; this project's Google user)
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_TAB` (default `Daily`)
Pittsburgh, PA is the fixed location. It is a constant, not a flag.

### Tests

Unit tests use saved page fixtures. They cover date selection around midnight Eastern, the day-index mismatch, precision-preserving conversion, parsing a saved Pittsburgh climate summary (max 63, min 39 on October 24 2026), a missing summary date, and the sheet updater: create the collection row, fill only blank forecast cells, write actuals onto the previous date, and refuse to replace a filled cell. Live browser runs are not part of unit tests. One optional integration test, marked and skipped in CI, opens the four live pages.

## Risks / Trade-offs

- [A page does not show the five-day calendar date] → Leave that date's cells blank, keep tomorrow, and print the error. Do not use day index 5 when its date differs.
- [Page markup changes] → Each adapter is isolated. A fix changes that adapter only.
- [CLI product is delayed past 6:00 a.m.] → That morning's actual cells stay blank. The next successful run fills them because actuals are written onto the previous date's row and blank cells can still be filled. A manual edit is needed only if the report never arrives.
- [OAuth refresh token expires or is revoked] → The scheduled run fails before writing. `weather-tracker auth` repeats consent as the sheet user and replaces `SHEETS_REFRESH_TOKEN`. The error must not print the token.
- [Existing OAuth client has no loopback redirect] → Auth stops with the exact URI to add in Google Cloud. Adding it does not change the cubscouts client file.
- [Unpacking GWS_AUTH uses the cubscouts encryption key] → The collector never decrypts cubscouts blobs and never writes that key into the sheet token.
- [Site terms restrict automated access] → The browser visit matches the manual procedure: four public pages, once per day, no weather data API.

## Migration Plan

1. `GWS_AUTH` is already on the weather-tracker project. Do not copy it again and do not print it.
2. Enable the Sheets API on that Google Cloud project if it is not already enabled.
3. Confirm the OAuth client has the loopback redirect URI.
4. Run `weather-tracker auth` and consent as the Google user who owns the science-project sheet. Store the refresh token as project secret `SHEETS_REFRESH_TOKEN`.
5. Set `GOOGLE_SHEET_ID` and run `weather-tracker collect` once. Confirm the row.
6. Set the Amp schedule for 6:00 a.m. America/New_York.
7. Rollback is removing the schedule and ignoring new rows. Deleting `SHEETS_REFRESH_TOKEN` disconnects only this project.

## Open Questions

- None that change the specs or the task breakdown. The exact Pittsburgh URL for weather.com and AccuWeather is confirmed during implementation from the page a manual visit opens.
