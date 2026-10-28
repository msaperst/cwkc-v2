# Running and deploying a competition

This guide is **how the existing system operates**, independent of any
particular competition year. For LGL/Google Forms setup see
[Connecting forms](forms.md); for a different pair of Hillels see
[Adapting the project](adapting.md).

An organizer should treat the following as three separate concerns:

- **Collecting gifts** — owned by the organizations' external LGL forms.
- **Processing and publishing** — the gated GitHub Actions workflow.
- **Verifying final totals** — reconciliation against the organizations'
  authoritative LGL records, **not** simply a successful workflow run.

## Accounts and deployment prerequisites

You'll need a GitHub repository with Pages enabled, a dedicated
notification mailbox accessible via IMAP, LGL form owners, a Google Cloud
service account, Google Sheets for normalized gifts and participation,
and people responsible for final rules and operations.

Keep secrets in **GitHub Settings → Secrets and variables → Actions →
Secrets**, never in source or public issues.

| Credential / setting | Purpose |
| --- | --- |
| `EMAIL_ACCOUNT`, `EMAIL_APP_PASSWORD` | IMAP notification mailbox |
| `SPREADSHEET_KEY` | Normalized donations workbook ID |
| `TYPE`, `PROJECT_ID`, `PRIVATE_KEY_ID`, `PRIVATE_KEY`, `CLIENT_EMAIL`, `CLIENT_ID`, `AUTH_URI`, `TOKEN_URI`, `AUTH_PROVIDER_X509_CERT_URL`, `CLIENT_X509_CERT_URL` | Service-account JSON components used by `update.yml`; `UNIVERSE_DOMAIN` optional |
| `CWKC_DONATIONS_WORKSHEET` (**Actions variable**) | Selected normalized Sheet tab (e.g. `entries`); passed to donation importer and calculator |
| `CWKC_INGESTION_ENABLED` (**Actions variable**) | Fail-closed live-ingestion switch; only literal `true` enables it inside the approved time window |
| `SONAR_TOKEN` | CI analysis only, not donation processing |

The runtime `GITHUB_TOKEN` for workflows is issued by GitHub; configure
permissions through workflow YAML and your repo's Actions settings, not by
committing a personal token. The optional **local** `pollEmail.py` and
Apps Script dispatch integrations need their own separately authorized
GitHub dispatch token (see [Connecting forms](forms.md)).

**Two distinct Google identities:** the shared human mailbox account
can own/edit Forms; the GCP service-account `client_email` must be
explicitly shared on every Sheets API source/destination. The updater
constructs local, gitignored `spreadsheet_credentials.json` files
from Actions secrets.

## Configure a competition season

1. Approve event start/end, timezone, both schools' official donation
   links, participation eligibility and all scoring categories.
2. Set `year`, `timezone`, `start` and `end` (ISO timestamps with
   matching UTC offsets) in `public/assets/config/season.json`.
3. From the repository root, regenerate and verify generated assets:

   ~~~bash
   python -m scraper.season_config --write
   python -m scraper.season_config --check
   ~~~

4. Review the **fixed UTC cron dates** in
   `.github/workflows/update.yml` and `watchdog.yml`. They are
   deliberately **not generated** from `season.json`. The date gate
   prevents out-of-window updates but cannot cause a missing schedule
   to execute. Check the scheduler before each event and consider the
   watchdog's delayed runs at the end of the window.
5. Update any changed form IDs, LGL field adapters, scoring Python,
   results CSV schema, website categories, links and branding **together**
   with tests. A new year is not just a JSON date edit.
6. Put approved **current-season** donations on a fresh or verified
   normalized worksheet; retain/archive the prior season privately.
   Check the importer's worksheet and calculator use the same tab.
   Do not delete legacy donor records to bypass validation.

The `season_config.py` HTML metadata generator uses CWKC-specific
title patterns. Rebranded forks must adapt it and its tests.

## Protect and publish results

`main` holds reviewed website code and a **safe starter CSV**.
Live results are committed to a separate `cwkc-results` branch;
normal Pages deployments overlay its latest snapshot so a code merge
doesn't reset the scoreboard.

- Use a **PR-only protected main** with required test/analysis checks.
- The results branch must be writable by the update workflow token
  but not bypass the main code-review rules.
- After the **final CSV schema** is approved, and only with an
  authorized empty/synthetic starter snapshot, initialize a results
  branch from that approved main revision:

  ~~~bash
  git fetch origin
  git switch -c cwkc-results origin/main
  git push -u origin cwkc-results
  git switch main
  ~~~

- Verify an authorized **synthetic** data-only push and a real Pages
  deployment separately before live collection. The automated
  temporary-repo test is not proof of GitHub Pages permissions.
- Do not bootstrap from an older donor-filled CSV. A schema mismatch
  between main and the published branch intentionally blocks restore.

`.github/workflows/deploy.yml` runs on approved `main` pushes and
overlays the published CSV. `.github/workflows/update.yml` checks
both sources, publishes only when the CSV changes, and explicitly
deploys Pages. GitHub Pages domain, ownership, certificate, logo and
public assets are repository-specific settings, not portable defaults.

## Before opening collection

- Confirm **all** forms and scoring rules are final; the four current
  LGL notification types and participation Sheet schemas have
  sanitized fixtures and isolated tests.
- Confirm the correct Sheets are accessible to the service account
  and the source LGL notifications go to the right mailbox.
- With ingestion still **off**, use an **authorized** read-only
  reconciliation:

  ~~~bash
  python -m scraper.getLglFormData --reconcile-only
  ~~~

  Inspect pending/known email counts, old rows without IDs and
  `submission id` column readiness. This does **not** reconcile
  actual monetary totals against LGL.
- Confirm the `cwkc-results` bootstrap, Pages deployment and
  GitHub branch protections were tested.
- Assign a primary and backup operator and ensure they actually
  receive GitHub issue and failed-Actions notifications.
- Only at the authorized opening instant, set
  `CWKC_INGESTION_ENABLED=true` in Actions Variables.

**Important:** Running a Python importer manually with live credentials
is **not gated by the workflow's switch**. Do not use those commands
to smoke-test the real mailbox or Sheet. Simulate with fixtures or
explicitly approved isolated resources.

## While the event is live

The update workflow is scheduled roughly every five minutes during
its configured UTC dates, and both imports run serially. No local PC
needs to stay online. GitHub cron execution is best-effort, can be
delayed or dropped, and on public repositories may be deactivated
after prolonged inactivity. Check scheduled runs before the event.

The watchdog checks at scheduled intervals and alerts on stale or
failed real `recompute` jobs. An unchanged CSV may be legitimate;
check processing runs rather than only the last CSV commit. Track the
aggregate message counts and privately reconcile donations against
source LGL totals.

The optional local IMAP poller / Google Apps Script dispatches can
cause redundant refreshes if enabled alongside scheduling; coordinate
any fallback rather than running competing processors.

## Pause, recover or close

1. Record failing Actions runs, last known-good published CSV commit
   and the unread backlog; do not put donor details in public logs.
2. To prevent **new** ingestion runs, set
   `CWKC_INGESTION_ENABLED=false`; that does **not** cancel a
   running update. Stop any locally operating poller.
3. Check the mailbox and Sheet using read-only reconciliation;
   investigate Sheets permission/quota errors, duplicate LGL labels,
   missing headers, schema drift or Pages permissions. Failed emails
   must stay unread.
4. Repair via a reviewed PR or authorized credential change. Ledger
   submission IDs prevent replay of the **identical email**, not
   all separately generated notifications of the same real gift.
5. Resume **only within** the approved window after verification;
   compare the newest results branch and published site with private
   authoritative source totals. Close any alert only after recovery.
6. At the exact configured cutoff, the update gate stops new imports
   and publications. Never quietly extend it to force a late replay.
   Escalate missing eligible gifts to the authorized organizers for
   an explicit final reconciliation decision.

Code rollback does not reverse Google Sheet writes or IMAP Seen flags.
The private normalized ledger and authoritative LGL records must be
reconciled separately.

### Repeat an offline publishing/recovery test

~~~bash
python -m pytest scraper/tests/test_release_rehearsal.py -v
~~~

This creates disposable **local** Git repositories and synthetic score
CSVs to exercise changed/unchanged publication, code deploy overlay,
failure/replay and schema mismatch; it never reaches live GitHub Pages
or donor systems.

For the actual CWKC season's approvals and date-specific handoff,
see the [current CWKC event checklist](2026-launch-runbook.md).
