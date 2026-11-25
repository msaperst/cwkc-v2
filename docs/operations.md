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

  Check `legacy=0`, `id_tracking=enabled` and pending-message totals; compare privately with LGL. This reads only enough to identify pending direct/forwarded submissions; it does **not financially reconcile** pending messages.
- From `scraper/`, run the participation `python getGoogleFormData.py --dry-run` with authorized credentials. Confirm test Form responses are removed.
- Confirm a clean score CSV, `cwkc-results`, successful synthetic Pages rehearsal and primary/backup operators receiving alerts.
- At the authorized opening instant, and **only** after sign-off, set `CWKC_INGESTION_ENABLED=true`.

**Caution:** The workflow switch does **not** gate manually invoked Python scripts with live credentials. Such scripts can write Sheets and mark IMAP messages Seen. Do not smoke-test against the production mailbox.

## Controlled November 2026 end-to-end rehearsal

The normal scheduled/repository-dispatched workflow still runs **only inside**
the configured competition window with `CWKC_INGESTION_ENABLED=true`.

To verify the real ingestion, Sheet append, CSV publication and Pages deploy
**before kickoff**, operators may run **Actions → Update results from multiple
locations → Run workflow** on `main` with `rehearsal=true` and confirmation
`REHEARSE`. This override only works before the November 30 opening, only for
`workflow_dispatch`, and only while `CWKC_INGESTION_ENABLED` is *not*
`true`. Both pre- and post-ingestion date guards enforce that rule. Do not
change `season.json` or enable the production switch to test early.

**This is not a read-only run.** It writes 2026 donation rows to the private
ledger, marks successfully processed direct/forwarded LGL notifications
**Seen**, commits the resulting CSV to `cwkc-results`, and deploys the public
site if the score changes. Rehearsal publishes **the full production CSV,
including donor names that the normal scoring logic considers public**.
The Pages deployment also temporarily enables the real live scoreboard and
donor scroller, using an inline expiration marker valid for up to 10 minutes
before kickoff. After that time, open browser tabs reload into the ordinary
prelaunch countdown. The source season dates remain unchanged.

**Public data is not automatically deleted when the preview expires.**
The CSV remains accessible by direct URL until the score branch is reset and
a clean Pages deployment completes. The prior public Git commit can remain
accessible via Git history, caches, or copies even after resetting; a
10-minute browser view does not guarantee a 10-minute exposure.

Preflight: ensure the current Donations tab is `entries_2026` with 12
columns ending in `submission id` (with a space), `SPREADSHEET_KEY` is
configured, the GCP service account has Editor access to the Donations
workbook and read access to **both** current 2026 response workbooks, and
`cwkc-results` exists with a clean zeroed CSV. The new gathering source is
`CWKC Alum Gathering Photos Form 2026 (Responses)`, **not** the 2022 archive.
Run the read-only preview first to test the new source permissions.

After the E2E test: compare the normalized ledger and published CSV with the
read-only reference audit, then restore `cwkc-results` to the zero-score
snapshot and run a clean Pages deploy. This restores the normal prelaunch
display but does not reliably erase donor information from public Git history.
The 10-minute display marker expires by itself; resetting the data branch
and redeploying remain manual steps. Remove test Google Form responses from
both the Forms and their response Sheets. Restoring the CSV does **not** undo
Google Sheet writes or IMAP Seen flags; if required for a later inbox audit,
re-mark the relevant notifications unread manually. **Keep legitimate early
donations in the 2026 ledger**; do not delete/replay them just to reset the
public scoreboard. No permanent date override is left on: a later manual
rehearsal still requires the explicit inputs and the prelaunch boundary.

## Manual read-only score preview (before launch)

After merging the preview workflow, use **Actions → Preview CWKC results (read-only) → Run workflow** on `main`. It parses **currently unread** LGL emails without changing Seen flags, computes the donation CSV numbers, and optionally reads the current Google Forms response Sheets (`include_forms=true`) in dry-run mode. It does **not** write a Sheet, update `cwkc-results`, or publish Pages. Exclude only verified non-payment test records using their comma-separated LGL *Submission IDs*; otherwise they will appear in provisional totals. Donor-name columns are redacted.

This repository is **public**. The manual workflow uploads an **unencrypted, redacted aggregate score CSV** as a short-lived GitHub Actions artifact. No names, phone numbers, addresses, email addresses, raw notifications, or LGL submission IDs appear in the uploaded CSV or logs. No encryption keys or repository variables are required.

After the run succeeds, open its **Artifacts** section, download `cwkc-preview-results-<run number>`, and extract `proposed-results.csv`. The artifact expires after **1 day**; you can also delete it after reviewing. Anyone who can access the public workflow artifact may copy its aggregate totals before deletion, so deletion is not a confidentiality guarantee. The numeric CSV totals are intentionally kept **out of the permanent workflow logs**.

The proposed CSV has the exact public results schema but **excludes donor names** for privacy; compare the numeric fields with LGL payments. Without `include_forms`, participation/football columns remain at their starter values. This is a **current unread inbox projection**, not a merged view of any already-persisted Sheet rows, not evidence of payment receipt, and **not** a full email→Sheet→Pages integration test. A separate controlled rehearsal is required before opening.

## During the event

Scheduled Actions refresh roughly every five minutes; GitHub cron can be delayed or occasionally skipped. Check actual workflow executions and watchdog alerts. Use aggregate non-PII counters from Actions, but reconcile donations and totals with LGL privately. Avoid running a local poller and scheduled ingester independently without a coordinated fallback plan.

## Pause, recover or close

1. Record the failed run, latest valid `cwkc-results` commit and aggregate unread backlog. **Never log donor names, raw messages or credentials.**
2. Set `CWKC_INGESTION_ENABLED=false` to block **new** ingestions; this does not cancel a running job. Stop any local poller if in use.
3. Run authorized read-only checks. Investigate label ambiguity, service-account access, Sheet quota/headers, source-transaction duplication and Pages permissions. Failed emails must stay unread.
4. Fix via reviewed PR or authorized credential change. A stored LGL Submission ID deduplicates direct/forwarded copies of the *same form submission*, but **not two distinct submissions of one payment**. Reconcile with LGL; investigate old MIME-hash ledger keys before ingestion.
5. Resume only within the agreed window after verification. Compare the published snapshot and source totals, and resolve the watchdog issue only after recovery.
6. At cutoff, stop normal imports/publication. **Do not extend the season window** to force missing gifts through. Organizers must explicitly approve final reconciliation and sign-off.

A code rollback does not undo Google Sheet writes or IMAP Seen flags.

**Silent Sheets overwrite recovery (Nov 25 rehearsal):** A prior 50-email
run reported 49 durable `append_row` responses, but the live 2026 ledger and
published CSV contained only the **last** $18.54 VT gift. The importer now
collects all valid donations, writes missing records to one **explicit,
contiguous cell range** (not implicit per-row table append), and reads the
entire range back before acknowledging any source emails or generating the
public scoreboard. A partial/incorrect readback blocks publication.

If the old importer already marked everything Seen, run the normal
**Update results from multiple locations** manual workflow on `main`
with `rehearsal=true`, `confirmation=REHEARSE`, and
`replay_all=true`. Only before kickoff, only with the production kill
switch off, the real importer searches **all** approved LGL messages,
including Seen ones, deduplicates by LGL Submission ID, writes missing
rows to `entries_2026`, independently verifies the entire batch, and
recalculates/deploys the live site. Replay **does not change email flags**.
Do not delete the single already persisted row, and do not bulk-mark all
emails unread merely to replay. Do not run this outside the manual,
prelaunch recovery workflow.

**IMAP acknowledgement uncertainty:** An IMAP STORE response can fail after the
server has already applied the `\\Seen` flag. The importer now queries the
actual FLAGS before declaring that an already-persisted donation has failed.
If confirmation also fails, it blocks CSV publication. Inspect the live
`entries_2026` submission IDs and Gmail unread status before deciding to
reset any flags or replay mail. A rerun with no unread LGL notifications
still recalculates the CSV from the full durable 2026 ledger, without
duplicating any donations.

### Offline recovery rehearsal

~~~bash
python -m pytest scraper/tests/test_release_rehearsal.py -v
~~~

This uses synthetic CSVs and disposable local Git repos; it does **not** test production Pages, IMAP or donor records. For per-season owners and outstanding approvals, return to the [2026 launch checklist](2026-launch-runbook.md).
