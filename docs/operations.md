# Running and deploying CWKC

This is the **reusable operating procedure**, not the current season's status. For the 2026 blockers and approvals, see the [launch checklist](2026-launch-runbook.md). Donation forms and participation Sheets are covered in [Forms](forms.md).

**Three separate responsibilities:** Hillels own payment/financial records; the gated Actions workflow processes and publishes scores; operators reconcile results against **authoritative LGL records**, not just green CI.

## Accounts and settings

Use GitHub **Settings → Secrets and variables → Actions**; never check credentials into Git or issue comments.

| Item | Purpose |
| --- | --- |
| `EMAIL_ACCOUNT`, `EMAIL_APP_PASSWORD` (secrets) | Dedicated LGL notification IMAP mailbox |
| `SPREADSHEET_KEY` (secret) | Donations workbook ID |
| GCP service account JSON fields (secrets) | Private Google Sheets access; Actions reconstructs `spreadsheet_credentials.json` |
| `CWKC_DONATIONS_WORKSHEET` (variable) | **Current-season tab**, used by both importer and calculator |
| `CWKC_INGESTION_ENABLED` (variable) | Only literal `true` enables live Actions ingestion **inside** the season window |
| `SONAR_TOKEN` (secret) | CI scanning, unrelated to donor processing |
| Workflow `GITHUB_TOKEN` | GitHub-issued token; set minimal workflow permissions, no committed PAT |

The **human Google account** can edit Forms, but the distinct GCP **service-account `client_email`** must explicitly have access to each source/destination Sheet. Optional local pollers/Apps Script dispatches require separately approved tokens.

## Prepare a season

1. Get organizer agreement on dates, rules, form schema, public links, participation eligibility and financial accounting.
2. Update `public/assets/config/season.json` (`year`, timezone, offset-aware start/end), then from repo root:

   ~~~bash
   python -m scraper.season_config --write
   python -m scraper.season_config --check
   ~~~

3. **Separately inspect the fixed UTC schedules** in `.github/workflows/update.yml` and `watchdog.yml`. The runtime season gate cannot make a missing scheduled run appear.
4. Update HTML scoring `data-points`, Python calculations, CSV column schema, form mappings and tests **as one contract**. Review on a PR; code changes belong on protected `main`.
5. Retain a private prior-season backup. Prepare a clean new current-season donations tab with `NORMALIZED_FIELDS` plus `submission id`; verify the source Sheet and that the importer and calculator use the **same** tab. Never delete historical donations to bypass a ledger failure.
6. Confirm both public forms and staff/backend forms deliver to the correct mailbox, and the participation Sheets are readable using the actual service-account identity.

## Publishing architecture

- `main`: reviewed website code and a **safe starter results CSV**.
- `cwkc-results`: only approved generated score snapshots; Pages deploy overlays this branch's CSV so application deploys don't reset live scores.
- `update.yml`: scheduled, gated ingestion of both sources and serialized data publication.
- `deploy.yml`: publishes approved app code with latest valid results overlay.
- `watchdog.yml`: alerts on missed/failed ingestion work; an **unchanged CSV alone is not a failure**.

Bootstrap `cwkc-results` only after the final CSV schema is approved, starting from an audited safe `main` snapshot:

~~~bash
git fetch origin
git switch -c cwkc-results origin/main
git push -u origin cwkc-results
git switch main
~~~

Verify workflow token permission to update that branch and complete a **separately authorized synthetic real Pages deployment**. An offline test cannot establish Pages permissions. Never bootstrap from old donor-filled scores; schema drift should fail closed.

## Preflight and opening go/no-go

With `CWKC_INGESTION_ENABLED=false`:

- Verify production form ownership/access, correct 2026 donor fields, exact LGL email notifications, isolated tests, and both Hillels' approval.
- Run the **authorized read-only** mailbox/ledger check:

  ~~~bash
  python -m scraper.getLglFormData --reconcile-only
  ~~~

  Check `legacy=0`, `id_tracking=enabled` and pending-message totals; compare privately with LGL. This reads but **does not parse or financially reconcile** pending messages.
- From `scraper/`, run the participation `python getGoogleFormData.py --dry-run` with authorized credentials. Confirm test Form responses are removed.
- Confirm a clean score CSV, `cwkc-results`, successful synthetic Pages rehearsal and primary/backup operators receiving alerts.
- At the authorized opening instant, and **only** after sign-off, set `CWKC_INGESTION_ENABLED=true`.

**Caution:** The workflow switch does **not** gate manually invoked Python scripts with live credentials. Such scripts can write Sheets and mark IMAP messages Seen. Do not smoke-test against the production mailbox.

## Manual read-only score preview (before launch)

After merging the preview workflow, use **Actions → Preview CWKC results (read-only) → Run workflow** on `main`. It parses **currently unread** LGL emails without changing Seen flags, computes the donation CSV numbers, and optionally reads the current Google Forms response Sheets (`include_forms=true`) in dry-run mode. It does **not** write a Sheet, update `cwkc-results`, or publish Pages. Exclude only verified non-payment test records using their comma-separated LGL *Submission IDs*; otherwise they will appear in provisional totals. Donor-name columns are redacted.

This repository is **public**. The manual workflow uploads an **unencrypted, redacted aggregate score CSV** as a short-lived GitHub Actions artifact. No names, phone numbers, addresses, email addresses, raw notifications, or LGL submission IDs appear in the uploaded CSV or logs. No encryption keys or repository variables are required.

After the run succeeds, open its **Artifacts** section, download `cwkc-preview-results-<run number>`, and extract `proposed-results.csv`. The artifact expires after **1 day**; you can also delete it after reviewing. Anyone who can access the public workflow artifact may copy its aggregate totals before deletion, so deletion is not a confidentiality guarantee. The numeric CSV totals are intentionally kept **out of the permanent workflow logs**.

The proposed CSV has the exact public results schema but **excludes donor names** for privacy; compare the numeric fields with LGL payments. Without `include_forms`, participation/football columns remain at their starter values. This is a **current unread inbox projection**, not a merged view of any already-persisted Sheet rows, not evidence of payment receipt, and **not** a full email→Sheet→Pages integration test. A separate controlled rehearsal is required before opening.

## End-to-end rehearsal: email → Sheet → CSV → HTML

After merging the isolated integration workflow, open **Actions → Rehearse CWKC email to website (sandbox) → Run workflow** on `main`. Start with **mode: offline**; it uses ten **synthetic** quoted-printable LGL notifications covering both schools' front/back forms, the old VT repeated graduation-year labels, missing donor alumni years, monthly ×12, family giving, and fee-inclusive gifts. This exercises the actual `process_messages`, `SubmissionLedger`, `CalculateValues`, `update_local_csv`, Google Forms response reader, and final CSV writer against an in-memory spreadsheet. Playwright then serves the real site locally and feeds the **same generated CSV** into its actual AJAX/PapaParse/scoreboard code on desktop and mobile.

The workflow checks that ten rows are inserted once, the same ten messages replay without extra rows, every persisted column matches the 2026 worksheet contract, and the resulting 26-column CSV matches the verified totals ($269.68 UVA, $373 VT; $264.68 UVA family, $373 VT family) plus synthetic participation counts. It creates a downloadable **one-day synthetic fixture artifact** and never reads the real IMAP mailbox, changes its Seen flags, writes real donor rows, commits the results branch or deploys Pages. Local shortcut: `python -m scraper.tests.e2e_rehearsal --mode offline`, then `npx playwright test e2e/full-pipeline.spec.cjs`.

### Optional real Google Sheets sandbox write verification

To test Google Sheets API row insertion and subsequent reading **without touching production**:

1. Create a new, otherwise empty Google spreadsheet, name it **exactly** `CWKC-E2E-SANDBOX`, and share it with the existing CWKC Google service-account email as **Editor**. Do not use an existing donation or form-responses spreadsheet.
2. Store its spreadsheet **ID** in the GitHub Actions **secret** `CWKC_E2E_SPREADSHEET_KEY` (not the production `SPREADSHEET_KEY`). Keep the existing service-account secrets unchanged.
3. Run the same workflow on `main` with **mode: sandbox**. It refuses an unset/matching production ID or incorrect spreadsheet title, creates a **new** `E2E_<run>_<attempt>` worksheet with only invented donors, writes and rereads ten rows through the real Sheets API, verifies duplicate replay, computes the real CSV, then checks local HTML with Playwright.
4. Privately inspect that new test worksheet and the synthetic CSV artifact. Delete the test worksheet or sandbox spreadsheet when satisfied.

Real participation Forms sheets are **not** touched: both modes feed synthetic responses through the existing form-response parser, verifying that those aggregate counts update the CSV. This isolates the integration from donor payments, actual forms, mail, and publication. A final operator-approved launch reconciliation against LGL and the real `entries_2026` worksheet remains a separate gate. Running this rehearsal **never** enables production ingestion.

## During the event

Scheduled Actions refresh roughly every five minutes; GitHub cron can be delayed or occasionally skipped. Check actual workflow executions and watchdog alerts. Use aggregate non-PII counters from Actions, but reconcile donations and totals with LGL privately. Avoid running a local poller and scheduled ingester independently without a coordinated fallback plan.

## Pause, recover or close

1. Record the failed run, latest valid `cwkc-results` commit and aggregate unread backlog. **Never log donor names, raw messages or credentials.**
2. Set `CWKC_INGESTION_ENABLED=false` to block **new** ingestions; this does not cancel a running job. Stop any local poller if in use.
3. Run authorized read-only checks. Investigate label ambiguity, service-account access, Sheet quota/headers, source-transaction duplication and Pages permissions. Failed emails must stay unread.
4. Fix via reviewed PR or authorized credential change. A stored MIME fingerprint stops replay of the *same email* but **not two distinct notifications of one payment**. Reconcile with LGL.
5. Resume only within the agreed window after verification. Compare the published snapshot and source totals, and resolve the watchdog issue only after recovery.
6. At cutoff, stop normal imports/publication. **Do not extend the season window** to force missing gifts through. Organizers must explicitly approve final reconciliation and sign-off.

A code rollback does not undo Google Sheet writes or IMAP Seen flags.

### Offline recovery rehearsal

~~~bash
python -m pytest scraper/tests/test_release_rehearsal.py -v
~~~

This uses synthetic CSVs and disposable local Git repos; it does **not** test production Pages, IMAP or donor records. For per-season owners and outstanding approvals, return to the [2026 launch checklist](2026-launch-runbook.md).
