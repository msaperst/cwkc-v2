# Commonwealth Kiddush Cup (CWKC)

The Commonwealth Kiddush Cup is an annual fundraising competition between UVA and Virginia Tech. This repository contains the public scoreboard and the scripts that turn donation and participation submissions into scores. Donations are collected by the Hillels' forms, not by this website.

**Website:** https://cwkc.org · **Hosting:** GitHub Pages · **Repository:** https://github.com/msaperst/cwkc-v2

## How it works

![CWKC data flow](highLevelWorkflow.png)

[Edit the architecture diagram in Canva](https://www.canva.com/design/DAGgbkbv3WQ/oSKlD4TjEMOe_xGGQLPTSQ/edit)

There are two data sources:

- **LGL donations:** Little Green Light (LGL) form submissions send notification emails to `servicecwkc@gmail.com`. `scraper/pollEmail.py` looks for unread messages and sends a GitHub `lgl-form-submission` dispatch. `scraper/getLglFormData.py` parses the emails, writes normalized donations to Google Sheets, and calculates scoreboard metrics.
- **Participation forms:** Google Forms store gathering/photo responses in linked Google Sheets. An Apps Script trigger sends a GitHub `sheet-change` dispatch. `scraper/getGoogleFormData.py` reads the sheets and updates the participation metrics.

The resulting scoreboard is stored in `public/assets/csv/results.csv`. The static site (`public/index.html` plus `public/assets/js/main.js`) reads that CSV and awards points according to the HTML `data-points` attributes. GitHub Actions handles data updates and deployment.

## Project layout

| Path | Purpose |
| --- | --- |
| `public/index.html` | Website content, links, scoring categories and layout |
| `public/assets/js/main.js` | CSV rendering, points, countdown and results refresh |
| `public/assets/csv/results.csv` | Generated scoreboard data consumed by the browser |
| `scraper/EmailParser.py` | Normalize LGL email fields |
| `scraper/CalculateValues.py` | Calculate donation metrics |
| `scraper/getLglFormData.py` | Process unread LGL emails and update donation results |
| `scraper/getGoogleFormData.py` | Read gathering/photo response sheets |
| `scraper/pollEmail.py` | Poll mailbox and trigger GitHub data updates |
| `scraper/tests/` and `public/assets/js/*.test.js` | Python and JavaScript tests |
| `.github/workflows/test.yml` | PR test/coverage/SonarCloud checks |
| `.github/workflows/update.yml` | Google Sheet/LGL ingestion and results publishing |
| `.github/workflows/deploy.yml` | Static website deployment to GitHub Pages |

## Local development

**Requirements:** Git, Node.js 24 with npm, and Python 3.12.

~~~bash
git clone https://github.com/msaperst/cwkc-v2.git
cd cwkc-v2

npm ci

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
~~~

On Windows, activate the virtual environment using the appropriate `.venv/Scripts/activate` script instead.

### Run the website

No donation mailbox or Google credentials are needed to work on the **frontend**.

~~~bash
python -m http.server 8000 --directory public
~~~

Open http://localhost:8000. The site uses CDN-delivered frontend libraries; there is no frontend build step. Edits to files in `public/` are reflected after refreshing the browser.

The real countdown uses fixed competition dates. Outside the active period, the live scoreboard may not load its CSV; test score rendering and timer boundaries with Jest rather than changing production dates just for a local preview. For manual layout work, use local, non-sensitive sample data.

### Run tests

Run both suites from the **repository root**:

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
~~~

For Python coverage locally:

~~~bash
python -m pytest scraper/tests --cov=scraper --cov-report=term-missing --cov-report=html
~~~

The GitHub Actions test workflow also collects JavaScript coverage and runs SonarCloud. CI installs from `scraper/requirements-ci.lock` using exact versions and SHA-256 wheel hashes for **Python 3.12 on Linux x86_64**. This lock is platform-specific: regenerate and verify wheel hashes when changing dependencies, Python, or the CI platform. For ordinary development use `scraper/requirements-test.txt`.

Work on a feature branch, add or update tests with behavior changes, and open a pull request against `main`. Do not push directly to `main`.

## Credentials and configuration

Live integration scripts access Gmail and Google Sheets. **Do not use production accounts or real donor data for automated tests or local experiments.**

### Mailbox settings

Create `scraper/.env` (ignored by Git) when configuring the email poller or LGL ingestion:

~~~dotenv
EMAIL_ACCOUNT=servicecwkc@gmail.com
EMAIL_APP_PASSWORD=replace-with-Gmail-app-password
SPREADSHEET_KEY=replace-with-normalized-donations-spreadsheet-id
GITHUB_TOKEN=replace-with-GitHub-dispatch-token
~~~

Other supported options include `IMAP_SERVER` (default `imap.gmail.com`), `MAILBOX` (default `INBOX`), `FROM_FILTER`, `SPREADSHEET_SHEET` (default `entries`), `GITHUB_REPO`, and `IDLE_TIMEOUT_SECONDS`. Check the corresponding Python script for the variables it actually uses; the poller needs `GITHUB_TOKEN`, while the LGL processor needs `SPREADSHEET_KEY`.

Use `servicecwkc@gmail.com` for LGL submission notifications. The **Google Cloud service account** used by `gspread` is a separate identity: its `client_email` must have access to the Google Sheets being read or written.

### Google Sheets credentials

Follow the [gspread service-account setup guide](https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account/) to create a credentials JSON file. Keep its private key outside Git.

The current scripts use **working-directory-relative paths**:

- For `getGoogleFormData.py`, run from `scraper/` and place the private credentials file at `scraper/spreadsheet_credentials.json`.
- For `python -m scraper.getLglFormData`, run from the repository root and provide `spreadsheet_credentials.json` in the repository root. This root-level credentials file is also gitignored.

Share the response Sheets with the service account's `client_email`. For editing a Google Form, its associated Sheet and Apps Script, grant the CWKC Google user (`servicecwkc@gmail.com`) **Editor** access to the Form **and** its linked response Sheet. Form-editor access alone is not the same as API access for the service account.

The `update.yml` workflow reconstructs the credentials JSON from GitHub Actions secrets and reads the mailbox and destination-sheet secrets. Refer to that workflow for the expected secret names (including `EMAIL_ACCOUNT`, `EMAIL_APP_PASSWORD` and `SPREADSHEET_KEY`); the test workflow separately uses `SONAR_TOKEN`. Set secrets in the repository's GitHub Actions settings, never in source files.

## Connecting a new or replacement form

### LGL donation forms

1. Configure each Hillel's public and backend LGL form to email **every submission** to `servicecwkc@gmail.com`.
2. Compare the exact notification field labels and form titles against `scraper/EmailParser.py` and its tests. The parser depends on those fields to identify the school, donation type and values.
3. Confirm the destination normalized-donations spreadsheet, its ID (`SPREADSHEET_KEY`), and the service account's Sheet access.
4. Validate with authorized, non-financial test messages and sanitized test fixtures before accepting real donations. Freeze field names/options once verified.

### Google Forms and linked response Sheets

1. Have the owner share both the Form and its linked response Sheet with `servicecwkc@gmail.com` as **Editor**. Share the Sheet with the GCP service account for API access too.
2. Update the spreadsheet IDs and expected response columns in `scraper/getGoogleFormData.py`, with tests for the actual response schema. A new Form or reordered questions can change column positions.
3. In the **linked response Sheet**, open **Extensions → Apps Script**. Create a script like this:

~~~javascript
function triggerGithubAction() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN script property is missing');

  const response = UrlFetchApp.fetch(
    'https://api.github.com/repos/msaperst/cwkc-v2/dispatches',
    {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json'
      },
      payload: JSON.stringify({
        event_type: 'sheet-change',
        client_payload: { message: 'Participation response sheet updated' }
      }),
      muteHttpExceptions: true
    }
  );

  if (response.getResponseCode() !== 204) {
    throw new Error('GitHub dispatch failed: HTTP ' + response.getResponseCode());
  }
}
~~~

4. Under **Apps Script → Project Settings → Script properties**, set `GITHUB_TOKEN` to a GitHub token authorized to create repository dispatches. Create an installable **On form submit** trigger for `triggerGithubAction`, authorizing it with the CWKC account. Add an **On change** trigger only if manual Sheet changes also need to trigger updates; avoid duplicate triggers.
5. Verify the trigger with a safe test response and check the resulting GitHub Actions run, parsed totals and CSV contents. Remove test data before production use.

Installable triggers run as the account that created them; keep their ownership under the shared CWKC account, not a departing volunteer's personal account.

## Running integrations

**These commands can change Google Sheets, mark emails as read, publish results, or trigger production Actions. They are not smoke tests.** Confirm credentials, inputs, the approved event window and backup/recovery procedure before using them.

**LGL poller:** from the repository root (with `scraper/.env` configured):

~~~bash
python scraper/pollEmail.py
~~~

The poller looks for unread LGL messages and sends a `lgl-form-submission` dispatch. It does **not** parse or acknowledge donations itself. Leave it running only while collection is authorized, and monitor its output and the corresponding workflow runs.

**Read participation Sheets and update the local CSV:**

~~~bash
cd scraper
python getGoogleFormData.py
cd ..
~~~

**Process unread donation mail into the normalized Sheet and local CSV:**

~~~bash
python -m scraper.getLglFormData
~~~

That last command processes actual unread messages and marks successfully handled ones as read; use it only when production processing is intended, or with a fully isolated test mailbox and spreadsheet.

## Deployment

The site is a static GitHub Pages deployment with custom domain **cwkc.org**:

1. Make changes on a branch, run both test suites and open a PR.
2. Confirm the PR's **Unit Tests** and **SonarCloud quality gate** pass; review site changes and generated CSV data.
3. Merge the PR into `main`. A push to `main` triggers `.github/workflows/deploy.yml`, which deploys the `public/` directory to GitHub Pages.
4. Check https://cwkc.org after deployment for correct content, links, HTTPS, browser console errors, and the expected countdown/score display.

**Data refresh is a separate workflow.** `.github/workflows/update.yml` handles `sheet-change`, `lgl-form-submission`, and manual `workflow_dispatch` events. It recalculates both sources in a single serialized run and deploys the resulting CSV only when it changes. A bot-generated CSV commit does not trigger another GitHub Actions push workflow, so the update workflow explicitly deploys Pages.

**Enable data collection:** after confirming the event start/end instants and validating the Forms, open the repository's **Settings → Secrets and variables → Actions → Variables** and set `CWKC_INGESTION_ENABLED` to `true`. A missing variable or any value other than exactly `true` blocks all ingestion, including manual runs. The collection window (`scraper/contest_window.py`) also blocks runs outside the configured Eastern-time window and manual runs on branches other than `main`. To pause *future* processing, set the variable to `false` and stop the local poller. Disabling it cannot stop an update already in progress. Never use a manual production dispatch as a test run.

For each new competition season, update and test **both** frontend start/end instants (`public/assets/js/main.js`) and backend collection dates (`.github/workflows/update.yml`), the scoring contract (`CalculateValues.py` / HTML / CSV), form IDs, links and branding. Test the precise timezone boundaries and manual dispatch behavior before enabling ingestion.

If a release must be rolled back, revert the relevant PR on a new branch and merge the corrective PR through the normal checks. A static rollback does not automatically undo emails already processed or data written to Google Sheets; reconcile those separately before republishing scores.
