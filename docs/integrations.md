# Development and integration reference

For the quick start, see [README](../README.md). For the Nov 30 launch
decision, production configuration and incidents, use the
[2026 launch runbook](2026-launch-runbook.md).

**Do not use live forms, the real mailbox, or real donor records as test fixtures.**
Form labels and scoring rules for 2026 still require organizer sign-off:
[#32](https://github.com/msaperst/cwkc-v2/issues/32),
[#33](https://github.com/msaperst/cwkc-v2/issues/33),
[#35](https://github.com/msaperst/cwkc-v2/issues/35) and
[#36](https://github.com/msaperst/cwkc-v2/issues/36).

## Data flow and access

The **primary event-week automation is GitHub Actions**, not a permanently
running PC or Apps Script dispatch.

1. UVA and VT public/backend Little Green Light (LGL) donation forms send
   notifications to the dedicated **`servicecwkc@gmail.com`** mailbox.
   `scraper/getLglFormData.py` parses unread messages, persists normalized
   donations in the private Google Sheet, and calculates donation metrics.
2. Alumni gathering and Hanukkah photo Google Forms write responses to their
   respective linked Sheets. `scraper/getGoogleFormData.py` reads the approved
   response schemas and calculates participation metrics.
3. During the **authorized window only**, `.github/workflows/update.yml`
   polls **both** sources, reconciles a shared CSV, commits a changed CSV to
   `cwkc-results`, and deploys the site. Unchanged scores do not require a
   results commit. The website itself is served from GitHub Pages.
4. The independent `watchdog.yml` monitors successful processing runs
   (including a successful `recompute` job). It does not read donor data.

Legacy `scraper/pollEmail.py` can send an LGL-triggered repository dispatch
from a local computer; an authorized Apps Script can send a
`sheet-change` dispatch. **Neither is required for the current
scheduled-run primary operating mode**, and redundant dispatches complicate
debugging. Keep them off unless specifically coordinating a fallback.

**Identities are distinct:** the shared Google user
`servicecwkc@gmail.com` is used for mailbox and Form ownership/sharing;
the separate GCP **service-account `client_email`** is the principal that
`gspread` uses to read/write the linked Sheets. Grant Sheet access to both
as appropriate; Form-editor permission does not establish service-account
API access.

## Local setup

Requires Git, **Python 3.12** and **Node.js 24/npm**. From repository root:

~~~bash
npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt

npm test
python -m pytest scraper/tests --maxfail=1 -q
npx playwright install chromium
npm run test:browser
~~~

On Windows activate the environment under `.venv/Scripts/`.
Playwright starts its own **localhost** static server and uses synthetic
scoreboard fixtures; it does not call LGL, Gmail or Sheets. For Python
coverage:

~~~bash
python -m pytest scraper/tests --cov=scraper --cov-report=term-missing --cov-report=html
~~~

The CI workflow uses SHA-pinned GitHub Actions, the fixed, SHA-256 wheel-hashed
`scraper/requirements-ci.lock` on **Python 3.12/Linux x86_64**, Jest,
Playwright, SonarCloud and GitGuardian. Regenerate and reverify wheel hashes
when changing the CI Python version, architecture, or dependencies.
Do development on a branch, require green CI, and merge via PR—never
push application changes directly to protected `main`.

To preview the website locally (no credentials needed):

~~~bash
python -m http.server 8000 --directory public
~~~

Open http://localhost:8000. The browser is intentionally time-gated.
Use Jest/Playwright for active-score and kickoff/close scenarios rather
than modifying the production season to test a layout.

## Credentials (only for explicitly authorized integrations)

Keep Gmail app passwords, GCP JSON keys and GitHub tokens **out of the
repository and all test artifacts**. Unit/browser tests require none.
For local integration configuration, `scraper/.env` is ignored by Git:

~~~dotenv
EMAIL_ACCOUNT=servicecwkc@gmail.com
EMAIL_APP_PASSWORD=replace-with-authorized-app-password
SPREADSHEET_KEY=replace-with-private-donations-workbook-id
GITHUB_TOKEN=replace-with-authorized-dispatch-token
~~~

Optional per-script settings include `IMAP_SERVER` (default
`imap.gmail.com`), `MAILBOX` (default `INBOX`), `FROM_FILTER`,
`SPREADSHEET_SHEET` (default `entries`), `GITHUB_REPO` and
`IDLE_TIMEOUT_SECONDS`. The GitHub Actions variable
`CWKC_DONATIONS_WORKSHEET` is passed to the importer as
`SPREADSHEET_SHEET`; **configure it to `entries_2026` only after the
approved new-season worksheet exists**, following the runbook. Do not
change the workbook secret merely to select a tab.

The scripts currently resolve the **private GCP credentials file
relative to their working directories**:

| Script | Working directory | Private JSON path |
| --- | --- | --- |
| `python -m scraper.getLglFormData` | repository root | `./spreadsheet_credentials.json` |
| `python getGoogleFormData.py` | `scraper/` | `scraper/spreadsheet_credentials.json` |

The production `update.yml` creates both files from GitHub Actions
Secrets (never from committed credentials). Refer to the workflow for
its complete current secret contract. The test workflow additionally
uses `SONAR_TOKEN`.

## Verifying a replacement form

### LGL donation notifications

For **each** of UVA/VT public and backend forms:

1. Have the Hillel owner freeze the final form and configure a submission
   email to `servicecwkc@gmail.com`. Verify the notification's actual
   sender/display name, two-column HTML structure, form title, and exact
   question labels and options.
2. Obtain an **approved, sanitized** notification fixture. Check the
   parser/normalizer contract in `scraper/getLglFormData.py`,
   `scraper/EmailParser.py` and `scraper/tests/`. Duplicate
   `Graduation Year` labels (including equal answers) intentionally
   fail closed until questions are distinguished and verified.
3. Rehearse in an **isolated mailbox/folder and disposable Sheet**,
   never the current production donation workbook. Validate the
   missing/ambiguous-value, retries and unread-on-failure cases.
4. Verify identity, matching, recurring and multi-affiliation decisions
   **only after the signed-off 2026 rubric**. Avoid real payments or
   changing a live submission merely to manufacture test data.

The read-only preflight is:

~~~bash
python -m scraper.getLglFormData --reconcile-only
~~~

It inspects the unread notifications and **the configured normalized
Sheet even when the inbox is empty**, without marking mail Seen, writing
rows or changing the CSV. It returns aggregate
`pending`/`already_stored`/`failed`, identified/legacy row counts,
and ID-tracking status. This is **not** full reconciliation against
authoritative LGL financial totals. The legacy `entries` worksheet
contains historical donations; do not delete, migrate or relabel them
just to make the preflight pass.

### Google Forms and response Sheets

1. Have the owner grant `servicecwkc@gmail.com` **Editor** permission
   to the Form **and separately** to its linked response Sheet; share
   the response Sheet with the independent GCP service account.
2. Freeze the response header/column schema and verify which form maps
   to which Sheet. A reordered question can change the columns used
   by `getGoogleFormData.py`. Do not claim the service-account access
   has been proved merely because a human can open the Sheet.
3. Add mocked schema/malformed/duplicate tests before changing the
   importer. Verify the actual form and Sheet behavior only with an
   authorized non-sensitive sample, then reconcile/remove test rows.
4. The scheduled update workflow already reads **both** sources.
   A Google Apps Script dispatch trigger is **optional**; only install
   one when operators have explicitly chosen near-real-time update
   dispatch, confirmed ownership, and checked for duplicate triggers.

#### Optional Apps Script form-submission dispatch

If authorized, use the **linked response Sheet** →
**Extensions → Apps Script** and store a GitHub repository-dispatch token
in **Project Settings → Script properties** as `GITHUB_TOKEN`.
An example script (not installed by this repository):

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

Create an installable **On form submit** trigger with the shared CWKC
account, only after authorization. Installable triggers run as their
creator. Use **On change** additionally only if manual Sheet edits
must trigger jobs. Keep the webhook private, monitor non-204 errors
and avoid duplicate dispatch triggers. No such trigger is required for
the scheduled polling mode.

## Live commands are not smoke tests

The following **can change private data and email flags**, or send
production dispatches:

~~~bash
# Only when expressly authorized and the separate production gate is open:
python -m scraper.getLglFormData
(cd scraper && python getGoogleFormData.py)
# Optional legacy dispatch poller; do not run beside scheduled automation:
python scraper/pollEmail.py
~~~

None of these bypass the need for Hillel form/rule sign-off. Local
invocations can be state-changing even if the GitHub Actions season
switch is disabled; only use them with approved production access
or fully isolated test resources. For safe stop/resume, backup,
`entries_2026`, `cwkc-results`, real Pages rehearsal, and end-of-event
reconciliation use the [launch runbook](2026-launch-runbook.md).
