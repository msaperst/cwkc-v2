# Operations

CWKC production uses **scheduled GitHub Actions**, no separate VM or continuously running IMAP poller. The Hillels own financial reconciliation; the site only reports computed competition scores. Current launch and future tasks live in [GitHub issues](https://github.com/msaperst/cwkc-v2/issues), especially [#41](https://github.com/msaperst/cwkc-v2/issues/41).

## Access and configuration

Configure **Settings → Secrets and variables → Actions**. Do not store credentials or staff/backend form URLs in code, issues or screenshots.

| Name | Purpose |
| --- | --- |
| `EMAIL_ACCOUNT`, `EMAIL_APP_PASSWORD` (secrets) | Dedicated Gmail inbox for LGL notifications |
| `SPREADSHEET_KEY` (secret) | Private Donations workbook |
| GCP service-account JSON fields (secrets) | Reconstruct private `spreadsheet_credentials.json` for the import jobs |
| `CWKC_DONATIONS_WORKSHEET=entries_2026` (variable) | Exact current-season worksheet, shared by importer/scorer |
| `CWKC_INGESTION_ENABLED` (variable) | Literal `true` allows normal ingestion **only within the configured event window** |

The service account needs **Editor** access to the private Donations worksheet and read access to the 2026 participation response Sheets. Do not assume the connected human Google account's permissions also apply to the service account. The workflow's GitHub token publishes `cwkc-results` and Pages with scoped job permissions.

## Season timing and publishing

Canonical dates/timezone are in `public/assets/config/season.json`. For 2026: **Nov 30 00:00 EST – Dec 7 20:00 EST**. The JavaScript countdown displays Eastern dates/times regardless of the viewer's local timezone; the Python ingester compares offset-aware instants. GitHub cron is **UTC**: review `update.yml`/`watchdog.yml` schedules whenever the season changes.

- `main`: reviewed code and a safe, zeroed starter `public/assets/csv/results.csv`.
- `cwkc-results`: latest published snapshot; website deployments overlay this branch's CSV so code changes cannot reset a live scoreboard.
- `update.yml`: GitHub schedule ~every 5 minutes during event (cron can be delayed); combines unread LGL ingestion and participation; only publishes changes. `sheet-change` repository dispatch may also wake it. **All score updates still pass the same date/kill-switch gate.**
- `update.yml` also synchronizes approved images when `CWKC_PHOTOS_ENABLED=true`, including outside the scoring window. Both snapshots are stored on `cwkc-results`.
- `deploy.yml`: publishes reviewed static site plus current scores and validated photos. See [photo moderation](photos.md).
- `watchdog.yml`: checks ingestion heartbeat twice hourly during event, creates one operator issue for failures/staleness.
- `test.yml`: Python/Jest/Playwright checks on PRs and `main`.

## Before kickoff

1. Reconcile genuine paid early gifts against LGL and exclude/resolve nonpaid staff/backend test submissions **privately**. Do not equate an email with a settled payment.
2. Confirm `entries_2026` has the 12 expected column headers ending in `submission id` and no stray test rows; the current 2026 Google Forms response sheets contain only approved submissions.
3. Ensure every eligible early LGL notification is **unread**; the normal importer searches unread direct and approved forwarded notifications. Do not mark processed mail unread without reconciliation.
4. Run authorized read-only checks: `python -m scraper.getLglFormData --reconcile-only` from root; `python getGoogleFormData.py --dry-run` from `scraper/`. Verify the service account and target worksheet.
5. Confirm `cwkc-results` has the intended prelaunch snapshot, the public site shows **“The Cup Starts In”**, and monitor/backup operators receive alerts.
6. With organizer approval, set `CWKC_INGESTION_ENABLED=true` at the official kickoff **Nov 30 00:00 EST** (Nov 29 22:00 Arizona). The first scheduled tick is approximately **00:02 EST**, not a guaranteed exact execution time.

**Do not change dates or manually run the live importer to force a prelaunch ingestion.** The kill switch gates GitHub Actions; it does **not** prevent a developer with live credentials from running a mutating Python script.

## During the event

- Inspect the **actual `schedule` event** and `recompute`/`deploy-results` jobs, not merely a green `check-window` gate. Confirm private Sheet IDs/counts, published CSV and live page match LGL's authoritative totals.
- A CSV unchanged from the last run can be correct; GitHub cron can be delayed. The watchdog checks a successful ingestion heartbeat, not merely a new data commit.
- Successfully persisted LGL messages are marked Seen. Source IDs dedupe direct/forwarded deliveries; a source-ID collision, malformed form, unreliable Sheets readback, or unconfirmed IMAP acknowledgement blocks incomplete publication.
- Scheduled and `sheet-change` score updates share the same season gate; approved photos have an independent flag. Do not run a separate inbox poller.

## Pause, recover, close

1. Record failing run, latest known-good `cwkc-results` commit, Sheets row count/IDs and unread backlog. Keep donor details out of public logs/issues.
2. Set `CWKC_INGESTION_ENABLED=false` to stop **new** ingest jobs; this does not cancel one already running. Confirm whether the last job wrote Sheets or marked email Seen before any replay.
3. Investigate actual LGL payment/duplicate IDs, malformed source labels, service-account access, quota, batch verification, and Pages artifact/deployment errors. **Never** assume a successful HTTP append means rows persisted—our importer writes a contiguous explicit range and reads it back.
4. Fix with a PR or authorized credential adjustment. Missing or already-Seen messages require a deliberate reconciliation/replay plan; **never** indiscriminately clear a ledger or change flags in production.
5. Resume only within the official collection window after operator sign-off; verify results and close the watchdog incident after recovery.
6. At **Dec 7 20:00 EST**, the backend cutoff prevents new ingestion/publication. Obtain final LGL reconciliation and organizer sign-off; do not extend the window to force a late import.

A code rollback or results-branch reset **does not undo private Sheet writes, email Seen flags, publicly exposed CSV history or cached data**. Never assume a short-lived test display erases published identities. Use [issue #41](https://github.com/msaperst/cwkc-v2/issues/41) for launch decisions and [#40](https://github.com/msaperst/cwkc-v2/issues/40) for monitoring owners; see [photo moderation](photos.md) for gallery recovery.
