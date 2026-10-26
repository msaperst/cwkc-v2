# Commonwealth Kiddush Cup (CWKC)

The **Commonwealth Kiddush Cup** is an annual UVA (Hoos) vs. Virginia Tech (Hokies) fundraising competition. This repository hosts the public scoreboard and its data ingestion/score-calculation scripts. The Hillels own the fundraising forms and donation processing; CWKC reads approved submission data and publishes the competition totals.

**Public production website:** https://cwkc.org  
**Static hosting:** GitHub Pages at https://msaperst.github.io/cwkc-v2/ (underlying Pages host; `cwkc.org` is the public address).  
**Source:** https://github.com/msaperst/cwkc-v2  
**2026 launch tracker:** [#41](https://github.com/msaperst/cwkc-v2/issues/41)

## 2026 season: implementation versus launch readiness

- Expected competition: **Nov 30 through Dec 7, 2026, ending at 8:00 PM America/New_York**. The frontend currently assumes **midnight Eastern** on Nov 30 as the start, but the exact hour still needs Hillel confirmation ([#32](https://github.com/msaperst/cwkc-v2/issues/32)).
- **Early giving** can happen before Nov 30 through the Hillels' forms, but CWKC is **not to poll/collect/process submissions until kickoff**. Accumulated LGL notification emails should be processed only after activation and reconciliation.
- [PR #42](https://github.com/msaperst/cwkc-v2/pull/42) merged the 2026 frontend dates, year, pre-start scoreboard suppression, start-time countdown transition, and a **zeroed** public `results.csv`.
- **Do not interpret that frontend readiness as launch approval.** `.github/workflows/update.yml` still uses **2025 dates**, and `workflow_dispatch` can bypass its date gate. **Do not manually run production data updates** until [#5](https://github.com/msaperst/cwkc-v2/issues/5) is fixed and tested.
- The existing CSV/HTML/scoring categories still have **2025-era field names** until the approved 2026 rubric and Forms are implemented ([#35](https://github.com/msaperst/cwkc-v2/issues/35), [#36](https://github.com/msaperst/cwkc-v2/issues/36)). Donation and submission URLs and the official 2026 logo also require verification ([#37](https://github.com/msaperst/cwkc-v2/issues/37)).

## Architecture

There are two input paths. Both ultimately update the published `public/assets/csv/results.csv` file.

1. **Little Green Light (LGL) donation forms:** The Hillels configure **every submission** to send a notification email to `servicecwkc@gmail.com`. An IMAP poller (`scraper/pollEmail.py`) checks for unread LGL emails and triggers a GitHub `repository_dispatch` event. The `lgl-form-submission` workflow invokes `scraper.getLglFormData`, which reads/parses mail, writes normalized donations to a Google Sheet, and calculates CSV results.
2. **Google Forms (gatherings and photo entries):** Form responses populate linked Google Sheets. An installable Google Apps Script trigger sends `sheet-change` to GitHub, which runs `scraper/getGoogleFormData.py` to update the applicable CSV columns.

The frontend (`public/index.html` and `public/assets/js/main.js`) reads the CSV to display competition standings. It is a static page; no payment data is captured by the site. The live frontend refreshes its CSV view during the official contest window. GitHub Actions handles static Pages deployments (`.github/workflows/deploy.yml`) and data updates (`.github/workflows/update.yml`).

The 2025 IMAP poller **ran locally on a volunteer's PC**; no always-on production runner is currently configured. A decision about a supervised local poller versus a free scheduled alternative, plus monitoring and a backup operator, is tracked in [#40](https://github.com/msaperst/cwkc-v2/issues/40).

![CWKC data flow diagram](highLevelWorkflow.png)

[Editable source for the diagram](https://www.canva.com/design/DAGgbkbv3WQ/oSKlD4TjEMOe_xGGQLPTSQ/edit)

## Development and testing

Use **feature branches and pull requests**. Do not push directly to `main`. PRs must pass automated checks and be reviewed before merging. Changes to external Forms or scoring must include fixture-based regression tests; don't point PR CI at live donor data.

### JavaScript (Jest)

```bash
npm ci
npm test
```

### Python (pytest)

From the repository root, with Python 3.12 and a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
python -m pytest scraper/tests --maxfail=1 -q
```

CI additionally uploads coverage for SonarCloud. The CI-only file `scraper/requirements-ci.lock` pins **all 42 resolved packages**, including transitive dependencies, to exact versions and SHA-256 hashes. It was verified for **CPython 3.12 on Linux x86_64**. CI enforces hash checking, wheel-only installs and no implicit dependency resolution. **Do not reuse this platform-specific wheel lock for a different Python/OS/CPU without regenerating and validating the hashes via PR.** Local development normally installs the exact-version `requirements-test.txt` graph instead.

[CI/test quality work](https://github.com/msaperst/cwkc-v2/issues/39) is still open for browser-level Playwright/smoke and end-to-end contract tests, even though [PR #42](https://github.com/msaperst/cwkc-v2/pull/42) had green pytest, Jest, and SonarCloud checks.

## Integrations and access

### Account roles

- **`servicecwkc@gmail.com`:** Shared CWKC Gmail mailbox receiving LGL submission notifications. Request Google **Form Editor** and separate linked **Sheet Editor** permissions for this account to manage the Apps Script/Form integrations.
- **Google Cloud service account (`client_email` in the private credentials JSON):** Separate non-Gmail identity used by `gspread` to read the linked Sheets. The exact service-account email should be obtained from private configuration and granted appropriate Sheet access. Never post its private key.
- `cwkcmanager@gmail.com` is a different historical account; do **not** request access for it by default unless a verified integration depends on it.

These identities are not interchangeable. The form owner must check both the Form and its linked Sheet's sharing settings; a public responder link does **not** grant edit or API access.

### Before connecting or replacing any 2026 Form

1. Obtain organizer-approved final **public form URL**, any backend submission form URL, response Sheet link, and full questions/answer-option contract. Establish a **field freeze** with the Hillels before early giving.
2. Grant `servicecwkc@gmail.com` **Editor** access on the Google Form **and** its linked response Google Sheet. Grant the separate GCP service account only the Sheet permissions its API actions require.
3. Obtain the expected school mapping, participant eligibility, thresholds, duplicate handling, and a **sanitized fixture** for each Form. Use authorized test submissions without charging a real donor.
4. For Google Forms, configure the associated Sheet's **installable Apps Script trigger** under the shared CWKC account. It should send the `sheet-change` `repository_dispatch` request to the GitHub repository. Store the GitHub credential in **Apps Script Properties**, never in a public script or repository. Review existing triggers to avoid duplicates, and give the token only the permissions needed for dispatch.
5. For LGL donation forms, verify that **every submission** sends an email notification to `servicecwkc@gmail.com`, and that `scraper/EmailParser.py` can parse every exact label and option. Failed processing must be recoverable without losing/duplicating submissions.
6. Test the **Form → email/Sheet → parser → result CSV → displayed points** chain with sanitized data in a nonproduction rehearsal; clear fixtures before activation. Never enable event ingestion just to test a provisional form.

Detailed 2026 form contracts and changes are tracked in [#32](https://github.com/msaperst/cwkc-v2/issues/32), [#33](https://github.com/msaperst/cwkc-v2/issues/33), and [#36](https://github.com/msaperst/cwkc-v2/issues/36).

### IMAP poller (for the approved event window only)

The poller lives at **`scraper/pollEmail.py`**. Its private environment configuration includes:

```dotenv
EMAIL_ACCOUNT=servicecwkc@gmail.com
EMAIL_APP_PASSWORD=your-private-Gmail-app-password
GITHUB_TOKEN=your-private-GitHub-dispatch-token
```

Once the **official kickoff is confirmed, the backend date gate is fixed, and the launch checklist is approved**, a supervised operator can run the local poller using:

```bash
python scraper/pollEmail.py
```

The poller is **not currently running**; running it continuously or triggering an update early could initiate production data processing. Never commit `.env`, service-account JSON, app passwords, donor emails or secrets. An operator must have a tested restart/stop procedure and check that early-donation emails are ingested without duplication. Refer to [#34](https://github.com/msaperst/cwkc-v2/issues/34) and [#40](https://github.com/msaperst/cwkc-v2/issues/40).

## Annual launch/rollback checklist

Use [#41](https://github.com/msaperst/cwkc-v2/issues/41) as the live go/no-go tracker, not this README alone. At minimum: confirm the Hillels' full scoring rules, signup links, editor/API permissions, logo/contacts, field freeze, exact Eastern start/end times, zero production test data, validated ingestion/retry behavior, `cwkc.org` URLs, green CI/Sonar and production rollback plan. During event week, verify last successful ingestion, reconciliation against submitted gifts, and the final-score stop procedure.

**Never waive a failing quality gate or make a direct `main` change to meet the event deadline.**

## Future reuse

[Documentation issue #6](https://github.com/msaperst/cwkc-v2/issues/6) tracks a configurable, school-independent deployment guide. This repository currently has CWKC-specific sheet IDs, score fields, and event assumptions; changing the school pair is **not** just a logo swap.
