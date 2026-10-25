# Spec Delta

## Purpose

Run the Pittsburgh forecast and actuals collection once per local day, on demand or at 6:00 a.m. Eastern, and write the result to the sheet.

## ADDED Requirements

### Requirement: One collection command
The project MUST provide one command that collects all forecast sources and the NWS actuals for the current America/New_York date, retries failed sources, and then updates the sheet.

#### Scenario: Manual run
- **WHEN** an operator runs the collection command
- **THEN** it performs one collection for the current Eastern date and attempts the sheet write

#### Scenario: Command reports the outcome
- **WHEN** the command finishes
- **THEN** it reports which sources succeeded, which failed, and which date rows were created or updated

### Requirement: Retry then continue
The run MUST retry a failed source before treating it as failed. A failed source MUST NOT prevent the run from collecting the remaining sources or from writing successes.

#### Scenario: Source fails once and then succeeds
- **WHEN** a source fails its first attempt and succeeds on a later attempt
- **THEN** the sheet uses the successful reading and does not mark that source failed

#### Scenario: Source keeps failing
- **WHEN** a source fails every attempt
- **THEN** the other sources are still collected and the failed source is recorded as an error

### Requirement: Scheduled Eastern morning run
The collection MUST be runnable every day at 6:00 a.m. America/New_York from a scheduled Amp orb thread. The scheduled run MUST use the same command as a manual run.

#### Scenario: Eastern Daylight Time
- **WHEN** the schedule fires for 6:00 a.m. America/New_York on a date observing Eastern Daylight Time
- **THEN** the collection runs at 10:00 UTC

#### Scenario: Eastern Standard Time
- **WHEN** the schedule fires for 6:00 a.m. America/New_York on a date observing Eastern Standard Time
- **THEN** the collection runs at 11:00 UTC

### Requirement: Same local date does not replace written values
A second run on the same America/New_York collection date MUST NOT add another row for that date and MUST NOT replace a forecast or actual cell that already has a value.

#### Scenario: Schedule and manual run overlap
- **WHEN** the command runs twice on the same Eastern date and the first run filled the collection row's forecasts
- **THEN** the second run does not add a row and does not change those forecast cells

### Requirement: Secrets stay outside the repo
The Google OAuth client material MUST be read from the Amp project secret or the environment. The repo MUST NOT contain that value. The Google client MUST be the existing app stored as the project secret `GWS_AUTH`. The sheet refresh token MUST belong to the Google user who consented for this project, not to another project's stored token. No weather data API key is required.

#### Scenario: Missing credential
- **WHEN** the Google client material is absent
- **THEN** the run fails before writing and the error does not include the secret value

#### Scenario: Sheet user is not the other project's user
- **WHEN** the collector writes the sheet
- **THEN** it uses a refresh token obtained by authorizing this project's Google user with the shared OAuth app
