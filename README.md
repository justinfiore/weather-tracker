# weather-tracker

Collect Pittsburgh, PA forecasts from weather.com, AccuWeather, and WTAE, and
previous-day actuals from the NWS Pittsburgh daily climate summary, into Google
Sheets. Weather sources are read from rendered browser pages, not weather APIs.

## Requirements

- Python 3.13
- [Poetry](https://python-poetry.org/) 2.x
- Google Chrome/Chromium, or Playwright's Chromium

## Setup

```bash
poetry sync
poetry run playwright install chromium
poetry run weather-tracker --help
```

Poetry creates `.venv` in this directory and uses Python 3.13. The collector
prefers an installed `google-chrome` or `chromium` (already available in Amp orbs);
the Playwright install command is needed only when neither is available. Linux
machines missing browser libraries can use `playwright install --with-deps chromium`.

## Sheets setup

Use an existing spreadsheet and an existing, empty tab named `Daily`, or configure
another tab. The collector initializes the empty tab's 36 headers, but does not
create spreadsheets or tabs. Existing 32-column headers are extended with four
timestamp headers without moving existing columns or changing data. It refuses
an incompatible header instead of overwriting unrelated data. Enable the Google Sheets API in the OAuth app's Cloud
project, and include the sheet owner as a test user if the app is in testing mode.

Configuration comes from environment variables (Amp project configuration for a
scheduled orb):

| Variable | Purpose |
| --- | --- |
| `GWS_AUTH` | **Project secret** already containing the shared OAuth app: base64 JSON mapping filenames to contents, including `client_secret.json`. |
| `SHEETS_REFRESH_TOKEN` | **Separate project secret** obtained by authorizing this project's sheet owner. Never reuse cubscouts' token. |
| `GOOGLE_SHEET_ID` | Spreadsheet ID from its URL, between `/d/` and `/edit`. |
| `GOOGLE_SHEET_TAB` | Existing tab name; defaults to `Daily`. |

Do not put secrets in tracked files, shell command arguments, chat, or logs.
`GWS_AUTH` is consumed from the collector process environment; only its client
file is unpacked into a temporary mode-0600 file outside the repo and removed
after use. Encryption keys and other projects' credential blobs are ignored.

### One-time authorization

```bash
poetry run weather-tracker auth
```

Run this in an interactive browser environment and consent as the Google user
who owns the science-project sheet, **not** the cubscouts user. Only the Sheets
scope (`https://www.googleapis.com/auth/spreadsheets`) is requested. The callback
is `http://localhost:8080/`; an installed-app client may register portless
`http://localhost`. A web client must register the exact callback URI. If it is
missing, the command stops and tells you which URI to add in Google Cloud.

The browser and callback server must run on the same machine. In an orb, use the
orb Desktop browser, not a browser on your laptop: laptop `localhost` does not
reach the orb. The command prints only the path to a mode-0600 file under `/tmp`,
never the refresh token. Securely import that file as the Amp **project secret**
`SHEETS_REFRESH_TOKEN`, then delete the file. Refresh the orb's secret environment
before collecting (`amp orb restart-processes`). Daily collection uses this
token unattended: it opens weather pages, but never a Google consent browser.

## Daily collection

```bash
poetry run weather-tracker collect
```

The default is headless Chrome. AccuWeather returned HTTP 403 with headless
Chrome in this orb, but loaded and parsed correctly with fresh visible Chrome
on the same network. Use `--headed` on a graphical display; it still uses
Playwright with an isolated context, without hiding automation flags or using
your signed-in Chrome profile. In an Amp orb, start the Desktop first with
`amp orb desktop ensure`, then run:

```bash
DISPLAY=:0 poetry run weather-tracker collect --headed
```

This configuration does not guarantee future access or bypass site challenges.

One run computes dates in `America/New_York`, then visits sources sequentially:

- Forecasts for tomorrow and collection date + 5 calendar days, matched to the
  rendered dates rather than a site's day index.
- NWS maximum/minimum for yesterday, accepted only when the summary names that
  date and Pittsburgh, PA. Current observations and older reports are not used.
- Source-native values and locally converted F/C values, preserving published
  decimal places and rounding conversions half away from zero.

The collection-date row holds each site's next-day high/low (F/C), five-day
high/low (F/C), and five-day date, in weather.com, AccuWeather, WTAE order. The
four NWS actual columns are filled on **yesterday's row**; today's actuals remain
blank. A missing yesterday row is created with actuals only. Temperature cells
are numeric with explicit decimal formatting, so they can be charted directly.

Four columns appended at AG–AJ record `Collected At (Eastern)` for weather.com,
AccuWeather, WTAE, and NWS. Each is the first successful page read for that source
in the run, recorded as an ISO date/time with seconds and UTC offset, such as
`2026-10-25T06:00:08-04:00`, not the common run start time. NWS's timestamp goes
on yesterday's row alongside its actuals. Failed sources have no timestamp.
Like other values, a timestamp is written only when blank and preserved on reruns;
on a legacy row it records the first successful read since timestamp tracking began.

### Screenshot evidence

Every `collect` run saves 2× screenshots under
`.amp/in/artifacts/collections/<Eastern collection date>/<run start time>-<unique ID>/`:

```text
2026-10-26/060000.123456-0400-abcd1234/
  README.md                         # Human-readable lookup index
  manifest.json                     # Exact values, times, URLs, and selected attempts
  weather.com/attempt-1/
    page.png                        # Browser viewport for context
    2026-10-27.png                   # Tomorrow's dated forecast card
    2026-10-31.png                   # Five-day dated forecast card
  AccuWeather/attempt-1/...
  WTAE/attempt-1/...
  NWS/attempt-1/
    page.png
    climate-report.png
```

The command prints the index path. To check a sheet data point, use its source,
row date, and **Collected At (Eastern)** timestamp to find the matching run index,
then open the image named for the forecast's target date. For NWS, use the index's
previous-date sheet row and the climate-report image. The index lists the high
and low in both units and the actual requested/resolved URLs. Retry attempts
remain separate; the index identifies which attempt supplied each date's values.
Failed sources also get page captures when possible, including stale NWS reports.
Page captures are bounded to the viewport; dated cards and the climate report
are captured separately so unrelated advertising cannot make an enormous image.
A screenshot failure is explicitly recorded and warned about, not silently
treated as successful evidence or substituted for a missing weather value.

Reruns never overwrite earlier capture folders or filled sheet timestamps.
The index describes what that run observed, not a claim that existing sheet
values were replaced. Old readings from before screenshot capture was enabled
cannot be reconstructed. Images and indexes are local orb artifacts, excluded
from Git; they are retained without automatic deletion, not uploaded to Drive
or backed up outside this orb. Keep or download evidence you need before
discarding the orb.

### Blank-only updates and retries

Only blank cells are filled. Existing numbers (including zero), dates, and
formulas are preserved on reruns. A failed source leaves its cells blank and
does not cancel the others. Timeouts/rendering failures receive up to three
attempts, waiting 2 seconds then 8 seconds plus 0–1 second jitter; parse failures
are retried once. Each source prints `ok`, `partial`, or `failed`, followed by
the date rows created/updated. Exit status is 0 after a successful write or when
collected values are already present, and 1 when every source fails or the sheet
cannot be opened/updated. An all-failed run writes nothing.

Run scheduled and manual collection in the **same orb**. A per-destination lock
serializes their sheet reads/writes. Do not run multiple independent orbs or edit
the tab concurrently during collection: Sheets has no compare-and-swap primitive
for the read-before-write sequence.

## Amp schedule

After one consented live collection and verification of both date rows, create
an Amp **thread schedule** for **6:00 a.m. America/New_York daily**. Its saved
prompt should say:

```text
In justinfiore/weather-tracker, run `amp orb desktop ensure`, then
`DISPLAY=:0 poetry run weather-tracker collect --headed` and report the command
output and exit status. Do not archive this thread.
```

Keep the thread unarchived and configure its project secrets and sheet ID above.
Use the timezone, not a fixed UTC hour: 6 a.m. is 10 UTC in EDT and 11 UTC in EST.
There is no repository cron or GitHub Actions schedule. The three-week project
window is not a code-enforced stop; disable the Amp schedule when the study ends.
Deleting `SHEETS_REFRESH_TOKEN` disconnects only this project's sheet account.

## Verification

```bash
poetry run pytest -q
poetry run weather-tracker auth --help
poetry run weather-tracker collect --help
```

Tests render saved page excerpts with external requests blocked, and exercise
Eastern midnight/DST, precision, missing dates, retries, blank-only Sheets writes,
partial failures, and CLI exit status. The optional live smoke test visits all
four public pages, requires no OAuth secrets, and **does not write Sheets**:

```bash
amp orb desktop ensure
DISPLAY=:0 WEATHER_TRACKER_LIVE=1 poetry run pytest -m live --headed -s
```

Sites may delay rendering, change markup, or block automated browsers. Live
failures are reported rather than replaced with another site's values or APIs.

## OpenSpec

Planning workflows live in `.agents/skills/`. Ask Amp to propose, apply, or archive a change, or invoke a skill directly (`/openspec-propose`).
