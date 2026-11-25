# Deploy your own Hillel fundraising competition

This guide walks an organizing team through **forking CWKC, adapting it for two Hillels, connecting donation and participation sources, and publishing its own scoreboard**.

CWKC is source code, not a hosted fundraising service. It **does not handle payments**: the Hillels own their Little Green Light (LGL) forms, donor financial records, consent and reconciliation. The website is a static GitHub Pages project; Python runs in GitHub Actions to score donations and Google Form responses. The default update mechanism is a **GitHub scheduled workflow**, not a continuously running server or an email-received webhook.

> **Important limitation:** This is a reproducible *reference implementation*, **not a one-click white-label app**. It currently assumes **exactly two schools**, uses internal `uva` / `vt` codes, and includes CWKC-specific 2026 form fields, categories, year, sheet IDs, names and styles. A new pair of schools must make and test those changes. Start with an organizer-approved scoring and data contract.

## 1. Decide what your competition will count

Before creating accounts, have both Hillels agree on:

- The two teams' public names, colors, logos, domains and approved branding rights.
- Contest start/end **with an IANA timezone**, score categories/point weights, tie rules, and which donations count.
- Donor identity/deduplication policy, first-time giving, recurring commitments, family affiliations, graduation-year eligibility, and handling processing fees and employer matching.
- Whether you will count alumni gatherings and seasonal photo participation, and the exact consent/eligibility rules.
- Owners for LGL configuration, Google Forms/Sheets, the repository, incident monitoring, donor reconciliation and final financial sign-off.

The sample competition annualizes eligible monthly donations ×12, counts several independently applicable affiliations, and excludes anonymous donors from the public name scroller. **These are CWKC rules, not universal defaults.** Do not use a payment-notification email as proof that money was received.

## 2. Fork, review and run locally

1. Open [the CWKC source repository](https://github.com/msaperst/cwkc-v2) and **Fork** it into an account or organization controlled by the event organizers.
2. Clone your fork (substitute your GitHub owner), then install prerequisites: **Python 3.12**, **Node.js 24**, Git and npm.

   ~~~bash
   git clone https://github.com/YOUR-ORG/cwkc-v2.git
   cd cwkc-v2
   npm ci
   python3.12 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r scraper/requirements-test.txt
   python -m http.server 8000 --directory public
   ~~~

3. Open http://localhost:8000 to view the static page. Outside the configured competition dates, the scoreboard is intentionally hidden.
4. Work on a **feature branch → pull request → reviewed merge to `main`**. Check your fork's **Settings → Actions** to enable workflows if GitHub has disabled them for the fork. Keep the production switch `CWKC_INGESTION_ENABLED=false` until the approved opening.
5. Do not import CWKC donor sheets, saved emails, production secrets, staff/backend donation links or private photo files into your fork. Its Apache-2.0 code license **does not grant permission** to reuse university/Hillel trademarks, artwork, photography or third-party content.

Reference: [GitHub Actions repository settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository).

## 3. Customize the two schools, branding and scoring

For a **two-team** fork, the least disruptive approach is to retain internal `uva` and `vt` prefixes as *team A* and *team B* while changing what they represent on the website and in the data sources. Renaming those internal keys or adding more teams requires a coordinated code/schema migration.

| Edit | What must change |
| --- | --- |
| `public/index.html` | School names, donation/form links, intro, footnotes, external Hillel URLs, image alt text, title and Open Graph URL/image; keep score element IDs and `data-points` synchronized with JS |
| `public/assets/img/` | Replace CWKC/UVA/VT logos, cup artwork and favicon with assets you have permission to publish |
| `public/assets/js/tailwind.js` and `public/assets/css/main.css` | Team palette, gradients and styles; inspect any `hoo`/`hokie` classes |
| `scraper/EmailParser.py` | Two source identities, accepted answer labels, affiliation and fee/year normalization |
| `scraper/lgl_forwarding.py` | The **four** exact LGL form titles, direct sender expectations and approved forwarding domains |
| `scraper/affiliations.py` | Allowed donor-affiliation text and canonical scoring groups |
| `scraper/CalculateValues.py` | Per-school metrics, Class-of-2026 year, monetary and donor-count rules |
| `scraper/getGoogleFormData.py` | Participation Sheet IDs, response tab, exact column headers, team-name parsing and eligibility |
| `public/assets/csv/results.csv` + `public/index.html` + JS/tests | The single-row public CSV schema must agree with every rendered score selector |
| `public/assets/config/season.json` and two workflow cron schedules | Competition dates/timezone and actual UTC scheduled ticks |
| `sonar-project.properties` / `package.json` | Your repository's analysis project, metadata, links and branding |

Search for all inherited details before publishing. For example:

~~~bash
git grep -n -E 'cwkc\.org|msaperst|brody|hillelvt|UVA|Virginia Tech|2026|cwkcservice|secure\.lglforms' -- \
  ':!package-lock.json'
~~~

Review matches instead of blindly replacing every `uva` / `vt` identifier. Replacing a public name is easy; replacing a metric prefix affects the importer, score calculator, CSV headers, HTML IDs and automated tests.

**Payments links:** Put only the two schools' approved **public** LGL donation links in `public/index.html`. Never expose staff/backend form entry or administration URLs.

## 4. Configure event dates correctly

Edit `public/assets/config/season.json` with your own year, timezone and start/end **offset-aware ISO 8601** timestamps:

~~~json
{
  "year": 2027,
  "timezone": "America/New_York",
  "start": "2027-11-29T00:00:00-05:00",
  "end": "2027-12-06T20:00:00-05:00"
}
~~~

*This is an illustrative example, not an approved future CWKC schedule.*

Then regenerate the website's matching JavaScript and metadata:

~~~bash
python -m scraper.season_config --write
python -m scraper.season_config --check
~~~

**Separately edit the UTC cron lines** in `.github/workflows/update.yml` and `.github/workflows/watchdog.yml`. The existing crons were written for the **2026 November 30–December 7** window. GitHub's scheduler understands UTC; the Python `contest_window.py` checks the true configured start/end and the independent kill switch. Cron may be delayed or occasionally skipped. Never change dates to bypass the gate during testing.

## 5. Create the LGL donation forms and notification emails

Both participating schools must have access to their own LGL form configuration and payment records. The current importer recognizes **four variants**: each school's **public donor form** and **staff/backend form**. The source contract is in `scraper/lgl_forwarding.py`:

| Internal source | Original CWKC title — replace with your own |
| --- | --- |
| `uva-front` | `14th Annual Commonwealth Kiddush Cup Front End Form` |
| `uva-back` | `14th Annual Commonwealth Kiddush Cup Back-end Form` |
| `vt-front` | `CWKC 2026 Donation Form` |
| `vt-back` | `CWKC 2026 Back End Form (Virginia Tech)` |

For each form:

1. Configure payments and ownership **inside the Hillel's LGL account**. Set notifications to deliver to your dedicated collection mailbox (step 6). Decide whether to notify directly or through an authorized staff forward.
2. Ensure the notification includes a stable **`Submission ID`**, a clear `Form title`, donor first/last name and phone (or your reviewed identifier policy), the full donated amount, relevant affiliations, recurring-gift flag and any first-time/anonymous/workplace-match answers you score.
3. Preserve the distinction between **donor alumni graduation year** and any related student/family member year. Existing parser labels include `Alumni Grad Year` / `Alumni Graduation Year`, `Related Grad Year` / `Related Student Graduation Year` and `Intended Grad Year` / `Intended Graduation Year`.
4. Existing amount fields are `Total Amount` for public forms and `Gift amount` for staff forms. The CWKC rules count the full reported amount including donor-covered processing fees. If your LGL form labels, status options, currency semantics or accounting policy differ, change `EmailParser.py`, `affiliations.py` and the tests **before accepting live emails**.
5. Make one **authorized, nonpaying test submission** of each form type, inspect the actual delivered MIME/HTML table and verify the expected school/title/fields. Payment forms and staff test submissions may generate financial records: coordinate testing with LGL administrators and remove/exclude only confirmed tests. Never publish those notifications or real identities as code fixtures.

**Critical:** `EmailParser.determine_source` expects specific sender display names (`Brody Jewish Center` or `Hillel at VT` today), and `validate_submission` checks `FORM_TITLES` exactly. Changing only the website or LGL form title will **not** make the parser work. Unexpected affiliations or malformed/mismatched notifications fail closed rather than silently inventing donor categories.

## 6. Create an organizer-controlled email inbox

Create a dedicated Gmail/Google Workspace inbox controlled by your organizing team, separate from anyone's personal Gmail. The address is your choice; nothing requires the original CWKC address.

1. Set up a backup owner, account recovery and 2-Step Verification. For the **current IMAP password-based importer**, create a Google **App Password** if available for your account. Some Google Workspace or security policies may disallow app passwords; **OAuth-based IMAP authentication is not implemented here**.
2. Confirm IMAP access to `imap.gmail.com`, mailbox `INBOX`, using the **actual Google account login** (`EMAIL_ACCOUNT`) and the app password (`EMAIL_APP_PASSWORD`), not the GCP service-account credentials.
3. In LGL, direct both schools' notifications to that inbox. If staff forward instead, update `FORWARDER_DOMAINS` and sender/subject checks in `scraper/lgl_forwarding.py`. Forwarding must preserve the original Gmail-style `---------- Forwarded message ---------` header, LGL sender and `New Submission:` subject, form HTML table and source Submission ID. Simple inline summaries or differently formatted forwards may be rejected.
4. Keep eligible donation notifications **unread until processed**. The scheduled importer searches unread direct LGL mail and unread messages with subject `Fwd: New Submission:`; it marks successfully **verified-and-persisted** messages Seen. Malformed or unconfirmed messages remain for investigation. Do not create a mailbox rule that marks them read before ingestion.

The current importer supports `IMAP_SERVER`, `MAILBOX` and `FROM_FILTER` overrides for local use, but `update.yml` only passes the email account/app-password secrets and relies on default Gmail/sender settings. If you change provider or direct sender, update the workflow environment or the implementation in your fork.

Official guidance: [Google app passwords](https://support.google.com/mail/answer/185833) and [Gmail IMAP access](https://support.google.com/mail/answer/7126229).

## 7. Set up Google Cloud and private spreadsheets

**Two distinct identities are required:** (a) the *human owner/editor* who manages Forms and Sheets, and (b) a **Google Cloud service account** that the GitHub workflow authenticates as. Giving the human access does not grant the service account access.

1. Create an organizer-owned [Google Cloud project](https://console.cloud.google.com/) and enable the [Google Sheets API](https://developers.google.com/workspace/sheets/api/quickstart/python). Create a service account in that project. For the current code, generate a **JSON key** only if your organization permits it; store it privately, restrict access and plan rotation. This repository currently reconstructs a JSON key from GitHub Actions secrets rather than using keyless workload identity.
2. Create a **new private donation Google spreadsheet**, share it with the service account's `client_email` as **Editor**, and note its spreadsheet ID (the part after `/d/` in its URL). Do not reuse CWKC's spreadsheet or import CWKC's donor records.
3. Create a current-season worksheet, e.g. `entries_2027`, with **exactly these 12 header cells in row 1, in this order**:

   ~~~text
   phone number | total amount | first name | last name | anonymous donation | first time giver | graduation year | status | work referral | recurring payment | source | submission id
   ~~~

   There should be **no non-header rows** before your first approved ingestion. The verified-batch ledger writes contiguous rows and re-reads them before acknowledging email. The public CSV must never contain private phone/email/contact data.
4. Note both the private spreadsheet ID and current worksheet name for GitHub Actions secrets/variables in step 9. The importer and scorer must use the **same** worksheet.

The service-account credentials are **not** a replacement for a working Gmail mailbox. File-upload folders also have distinct permissions; access to a Forms response Sheet does not automatically grant access to uploaded photos.

Official guidance: [create a service account](https://cloud.google.com/iam/docs/service-accounts-create) and [manage keys](https://cloud.google.com/iam/docs/keys-create-delete).

## 8. Create the participation Google Forms and linked response Sheets

CWKC's current calculator expects **both** Forms/response Sheets, even if no participant has submitted yet. If you do not want a category, remove/modify that category and the corresponding parser/CSV/HTML/tests together rather than leaving a missing spreadsheet ID.

1. Create two organizer-owned Google Forms (or your own equivalents), with each Form linked to a **Google Sheets response spreadsheet**. Share each response Sheet with the *same GCP service account* as **Viewer** (or minimum read access permitted). Keep the human organizers as owners/editors.
2. In `scraper/getGoogleFormData.py`, replace `GATHERING_SHEET_ID`, `HANUKKAH_SHEET_ID` and `CURRENT_TAB` with **your** response spreadsheet IDs and actual response tab name (currently `Form Responses 1`). Both forms must use the expected tab name, or adapt the code to support distinct tab names.
3. Match the parser's normalized question/header contract, or update `GATHERING_FIELDS` / `HANUKKAH_FIELDS` and their tests. Current expected headings are:

   | Gathering response | Hanukkah/participation response |
   | --- | --- |
   | `Timestamp` (automatic) | `Timestamp` (automatic) |
   | `Name` (host) | `Name` |
   | `Which school are you supporting?` | `Non-school affiliated email` |
   | `Affiliation` | `Which school are you supporting?` |
   | `Who was in attendance at your event?` | `Are you an alumni that graduated in the past 15 years, or a parent of one?` |
   | `Where was your event?` | `Graduation year (if applicable)` |
   | `Please submit photos of your event!` | `Submit your photo here!` |
   | — | `Photo release:` |

   Header comparison is case/whitespace-normalized and sometimes permits an additional suffix, but missing/duplicated required questions **fail** the update. Verify the **actual response Sheet headers**, not just visible Form prompts.
4. Adapt `_school` to recognize your two team names. Gathering eligibility currently requires an alumni/current-parent host, an in-person venue, a photo and **at least four distinct attendees including the host**. Hanukkah participation requires eligibility `Yes`, a photo and a unique normalized email per school. Adjust scoring rules and regression tests if your competition differs.
5. **Photo visibility is a separate system:** a Form upload is not automatically public. Obtain explicit release permission, guardian consent where relevant, organizer approval, and a safe hosting/takedown process before displaying images. The current repository **scores participation but does not ship a public photo viewer**.
6. Put the two new **public** Form URLs in the matching sections of `public/index.html`. Never use CWKC's existing response workbooks or Forms in a new fork.

For a read-only test after access is configured, place the **private** service account JSON at `scraper/spreadsheet_credentials.json` (gitignored) and run from `scraper/`:

~~~bash
python getGoogleFormData.py --dry-run
~~~

Do not commit credentials. After test submissions, clear synthetic responses from **both** Google Forms and their linked response Sheets.

## 9. Configure GitHub Actions secrets and variables

In **your fork**, go to **Settings → Secrets and variables → Actions**. Use repository/organization secrets and variables accessible to the workflows. The names below are exactly what the current `update.yml` reads.

| Type | Exact name(s) | Value |
| --- | --- | --- |
| Secret | `EMAIL_ACCOUNT` | Login of your dedicated Gmail/Google Workspace mailbox |
| Secret | `EMAIL_APP_PASSWORD` | Mailbox app password; **not** regular login password or GCP JSON key |
| Secret | `SPREADSHEET_KEY` | ID of your private donations spreadsheet |
| Secrets | `TYPE`, `PROJECT_ID`, `PRIVATE_KEY_ID`, `PRIVATE_KEY`, `CLIENT_EMAIL`, `CLIENT_ID` | Values from matching lowercase properties in your service-account JSON |
| Secrets | `AUTH_URI`, `TOKEN_URI`, `AUTH_PROVIDER_X509_CERT_URL`, `CLIENT_X509_CERT_URL` | Remaining matching properties from the same JSON |
| Secret (optional) | `UNIVERSE_DOMAIN` | Matching JSON property if present; defaults to Google's standard domain |
| Variable | `CWKC_DONATIONS_WORKSHEET` | Name of the current private worksheet, e.g. `entries_2027` |
| Variable | `CWKC_INGESTION_ENABLED` | Set literal **`false`** until the approved launch; switch to **`true`** at the authorized instant |

The workflow reconstructs two private credential files from these secrets at runtime. Paste the full `private_key` into the `PRIVATE_KEY` secret; the workflow supports actual line breaks or escaped `\n` sequences. It does **not** accept the entire JSON document as one secret. Do not paste this key into a PR, issue, public screenshot or repository file.

**GitHub permissions:** Enable Actions for the fork. The update workflow needs the job-scoped `contents: write` permission to push the **data-only** `cwkc-results` branch; the deployment needs `pages: write` and `id-token: write`. Protect `main` with reviews/tests and configure your branch rules so the Actions bot can publish the separate data branch. Do not grant arbitrary third parties access to secrets, and never run live-secret workflows from unreviewed pull requests.

**Optional CI scanning:** `test.yml` includes SonarCloud and reads `SONAR_TOKEN`; `sonar-project.properties` currently points to the original CWKC Sonar project. Register your own project and secret, or deliberately remove/disable that optional scan in a reviewed fork PR and adjust any required checks. Do not assume the original project's token or quality gate is available to forks.

## 10. Optional: trigger updates immediately on a Form submission

**You do not need any push integration to run CWKC.** `update.yml` already schedules a complete refresh about every five minutes within its UTC calendar. Both donation inbox and participation response Sheets are polled/read **by the same workflow**. The old local email poller was removed.

For quicker updates when **Google Form responses** arrive, the workflow accepts GitHub `repository_dispatch` with event type `sheet-change`. **The repository does not currently contain the Google Apps Script that sends this event.** If you want it, create a script bound to **each** linked Form response spreadsheet:

1. Create a **fine-grained GitHub token** limited to your fork, with **Contents: read/write** (the dispatch endpoint requires Contents write), an expiration date and the smallest practical access. Prefer an organizer-owned automation identity, not a personal long-lived token.
2. In each response spreadsheet, open **Extensions → Apps Script**, then add these **Script properties** under Project Settings: `GITHUB_REPO` = `YOUR-ORG/YOUR-REPO` and `GITHUB_DISPATCH_TOKEN` = your token. Do not put the token in source code or a spreadsheet cell.
3. Paste this script. It only signals that source data changed; it does not transmit names, emails or photo URLs.

   ~~~javascript
   function notifyGitHubOfParticipation(e) {
     if (!e || !e.range) throw new Error('Requires a spreadsheet form-submit trigger');

     const properties = PropertiesService.getScriptProperties();
     const repo = properties.getProperty('GITHUB_REPO');
     const token = properties.getProperty('GITHUB_DISPATCH_TOKEN');
     if (!repo || !token) throw new Error('Missing script properties');

     const response = UrlFetchApp.fetch(
       'https://api.github.com/repos/' + repo + '/dispatches',
       {
         method: 'post',
         contentType: 'application/json',
         headers: {
           Authorization: 'Bearer ' + token,
           Accept: 'application/vnd.github+json'
         },
         payload: JSON.stringify({event_type: 'sheet-change'}),
         muteHttpExceptions: true
       }
     );
     if (response.getResponseCode() !== 204) {
       throw new Error('GitHub dispatch HTTP ' + response.getResponseCode());
     }
   }
   ~~~

4. In Apps Script's **Triggers** panel, add an **installable** trigger for `notifyGitHubOfParticipation`: **From spreadsheet → On form submit**. Authorize it using the designated owner account. Do this on each relevant response spreadsheet. A **simple** trigger is not sufficient for authenticated outgoing API calls.
5. Submit a **synthetic** response. Look for a GitHub Actions run titled `sheet-change`. Before the authorized event window or while ingestion is disabled, `check-window` should pass but `recompute` must be **skipped**. That proves dispatch and the safety gate, **not** end-to-end ingestion. Do not enable production just to test a webhook.

Use a token stored only in restricted Script Properties; people with edit rights to the Apps Script project may be able to access or exfiltrate it, so strictly control script editors and rotate the token if access changes. A dispatch arriving before the response sheet is fully updated may see stale data; **the periodic schedule is the correctness fallback**.

References: [Google installable form-submit triggers](https://developers.google.com/apps-script/guides/triggers/installable), [GitHub repository dispatch API](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event).

**Email is not pushed directly to GitHub:** Gmail's official push API needs additional Pub/Sub and hosting components not shipped by this project. No Gmail→GitHub push integration is required or configured by these instructions.

## 11. Initialize the public results branch and GitHub Pages

The site **must** separate reviewed code from automatically written scoreboard data:

- `main`: static site source, workflows, tests, and a **safe starter CSV** at `public/assets/csv/results.csv`.
- `cwkc-results`: last published snapshot of the **same CSV schema**. The updater commits only the CSV here; a code deployment overlays it so a merge never resets active scores.

1. Make sure your **fork's** `public/assets/csv/results.csv` has the schema expected by *your* adapted site and is **zeroed**—no private names, numbers or live gift totals. The original format is one header + one result row with `uva_*` / `vt_*` fields, ending in two donor-name columns.
2. Create the data branch **in your fork**, starting from your already-reviewed, sanitized `main`:

   ~~~bash
   git fetch origin
   git switch main
   git pull --ff-only origin main
   git switch -c cwkc-results
   git push -u origin cwkc-results
   git switch main
   ~~~

   The workflow checks the CSV **schema** before restoring or committing changes. Do not bootstrap from a branch containing private donor data, and do not give the updater permission to bypass `main` code reviews.
3. In your fork's **Settings → Pages**, select **GitHub Actions** as the publishing source. The existing `deploy.yml` uploads `public/` on each `main` push; `update.yml` deploys a new snapshot after a successful changed-score run. There is **no separate frontend build**.
4. Confirm `https://YOUR-ORG.github.io/YOUR-REPO/` works (the site uses relative asset paths). To use a custom domain, first configure/verify it under GitHub Pages and update your DNS per GitHub's current instructions. Replace CWKC's absolute `og:url` / `og:image` and other inherited site links in `public/index.html`; do not point your fork at `cwkc.org`.
5. Check your Pages URL or custom domain after a **normal code deployment** with the zeroed scores. The initial public website should show the upcoming countdown and no donors. Don't mistake an Actions test run or a data-branch commit for proof that the public deployment succeeded.

Reference: [GitHub Pages with Actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [custom domains](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site).

## 12. Verify everything safely, then launch

Keep `CWKC_INGESTION_ENABLED=false` throughout setup. Use **fictional code fixtures** and organizer-authorized nonpayment submissions; isolate real integrations from any paid donor data.

| Verify | What success looks like |
| --- | --- |
| Tests | `npm test`, `python -m pytest scraper/tests -q` and `npm run test:browser` pass after every custom form/schema/score change |
| Static site | Your logos, names, public form links, countdown, browser layout and HTTPS work; no CWKC production links remain |
| Mailbox | Each of the four accepted LGL formats reaches your inbox with the expected form title, source, amount and Submission ID; approved forwards preserve required headers |
| Private Sheets | The service account opens the donations Sheet and both 2026-equivalent response Sheets; worksheet/headers are exact |
| Read-only LGL preflight | With temporary local `EMAIL_ACCOUNT`, `EMAIL_APP_PASSWORD` and `SPREADSHEET_KEY` environment variables, service-account JSON at `spreadsheet_credentials.json`, run `python -m scraper.getLglFormData --reconcile-only` from the repo root; no email flags or rows change |
| Read-only participation | From `scraper/`, run `python getGoogleFormData.py --dry-run` with `scraper/spreadsheet_credentials.json`; current response headers and school values parse correctly |
| Safe Pages | `cwkc-results` has zeroed results; `deploy.yml` succeeds and displays the correct prelaunch state |
| Optional form dispatch | A synthetic response causes `repository_dispatch: sheet-change`, but cannot bypass the season/kill-switch gate |
| Operators | At least one primary/backup can view Actions failures and watchdog issues; review the stop/recovery playbook |

If a custom scenario needs a **real write** test, use a separate test mailbox, separate test spreadsheet and test fork/environment with invented data. Do not change production event dates or reset genuine payment rows to run a rehearsal.

**At the approved start instant**, after each Hillel's source-of-truth financial review, change `CWKC_INGESTION_ENABLED` to literal `true`. Verify the first actual **`schedule` run** executes `recompute`, persists every accepted LGL Submission ID, updates participation counts, commits any changed CSV to `cwkc-results`, and deploys the corresponding site. A green `check-window` alone does not prove ingestion; GitHub schedule ticks are best effort.

During the event, the scheduled watchdog checks ingestion heartbeat and can open a GitHub issue on failure. Use [Operations](operations.md#pause-recover-close) to stop new processing, reconcile ambiguous messages and retry safely. At the official end instant, the time gate blocks new ingestion and publication; obtain final LGL financial sign-off before declaring results final.

## What this fork does and doesn't give you

**Included today:** two-team static responsive scoreboard, LGL MIME parsing and durable private Sheets ingestion, current-year participation scoring, Eastern/other offset-aware season gates, a protected data branch, scheduled GitHub Actions, Pages publishing, watchdog and synthetic tests.

**You supply and maintain:** LGL payment/form accounts and field mappings, organizational mailbox and IMAP credentials, Google project/service account/Sheets/Forms, optional Apps Script dispatch tokens, domain, authorized branding, source-of-truth financial reconciliation, donor/privacy consent and event operators.

**Not included as turnkey features:** arbitrary team counts, drag-and-drop scoring or form mapping, automatic migration to other schools, a live photo gallery, Gmail push notifications, keyless Google auth or guaranteed GitHub cron precision. If you implement changes to generalize these features, track them in your fork's GitHub issues and submit reviewed PRs.

For the current code structure see [Development](development.md); for the established parser/scoring contract see [Forms](forms.md); for live operations see [Operations](operations.md).
