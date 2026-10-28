# CWKC 2026 launch and recovery runbook

**This is an operator checklist, not approval to enable donation ingestion.**
See [launch tracker #41](https://github.com/msaperst/cwkc-v2/issues/41)
and [rules #32](https://github.com/msaperst/cwkc-v2/issues/32).

**Approved window:** Nov 30, 2026 00:00 ET through Dec 7 20:00 ET,
exclusive of the exact end. Hillels distribute their own LGL early-giving
links; those emails are collected only after authorized kickoff.

## Assign ownership first

Record a primary operator, a backup with GitHub Actions access, and
authorized UVA/VT score and cutoff approvers **privately**. Both operators
must subscribe to repository Issues/Actions notifications and verify they
actually receive an alert. Public GitHub issues must never contain donor
names, payment details, credentials or private test-data links.

## Safe rehearsal before rules are finalized

From the repository root using Python 3.12 and test dependencies:

```bash
python -m pytest scraper/tests/test_release_rehearsal.py -v
```

This exercise creates **temporary local Git repositories** only. It never
uses GitHub credentials, Gmail, Google Sheets, LGL or GitHub Pages.
It proves that (1) unchanged CSVs do not commit again; (2) changed results
are committed solely to `cwkc-results`; (3) fresh Pages-source checkouts
restore the last published CSV; (4) an interrupted update preserves the
last good snapshot for later recovery; (5) code merges cannot overwrite
scores with `main`'s zero placeholder; (6) schema drift blocks publication.

**Limit:** this tests Git mechanics, not actual GitHub Pages permissions,
service account access, live email delivery, or finalized 2026 score fields.
A separate, authorized synthetic deployment drill is still required.

## Go/no-go before Nov 30

- [ ] **Rules:** Both schools explicitly agree on multi-affiliation
  treatment, recurring monthly annualization, May 2026 class eligibility,
  the 15-point rubric and VT challenge-grant handling (#32, #35).
- [ ] **Forms:** Four frozen LGL variants (UVA/VT public and backend) have
  sanitized notification fixtures; expected sender, labels and routing to
  `servicecwkc@gmail.com` are verified, including conditional VT
  graduation years (#33).
- [ ] **Participation:** Final gathering/Hanukkah form schemas, eligibility,
  response Sheets, GCP service-account reads and Apps Script dispatches
  are verified (#36). Photo slideshow publication remains separately
  consent-gated (#50).
- [ ] **Content:** Public pages and homepage links reflect the approved
  rules, current forms, contacts and logo (#37).
- [ ] **Historical data:** Privately back up and retain the historical
  `entries` worksheet. Do not delete historical donations to unblock
  production (#34, #38).
- [ ] **2026 data:** With approval, prepare an *empty* `entries_2026`
  worksheet containing the 11 `NORMALIZED_FIELDS` followed by
  `submission id`. Confirm production `SPREADSHEET_KEY` refers to
  the intended workbook and its **separate GCP service account** has
  access. Set `CWKC_DONATIONS_WORKSHEET=entries_2026`.
- [ ] **Read-only preflight:** An authorized operator runs
  `python -m scraper.getLglFormData --reconcile-only` and confirms
  `legacy=0`, `id_tracking=enabled` and aggregate pending counts,
  without changing Seen flags or Sheet rows.
- [ ] **Publishing:** After the 2026 score schema is final, bootstrap
  `cwkc-results` from the approved *empty* `main` snapshot (not
  historic donor data). Verify a **separately approved synthetic**
  branch-only push and real Pages deployment; confirm branch protection
  applies to `main` but not the data branch.
- [ ] **Operations:** Primary and backup can see update, deploy and
  watchdog jobs; monitor permissions, schedules and alert subscriptions.
  No premature collection; `CWKC_INGESTION_ENABLED` stays `false`
  until authorized kickoff.

## Kickoff and normal monitoring

At approved kickoff, enable `CWKC_INGESTION_ENABLED=true` only after
all go/no-go gates pass. Check the first actual `recompute` job, its
aggregate LGL message counts, data-branch commit and published website.
Reconcile LGL source totals with the normalized 2026 ledger, including
early November gifts. **A green Actions run is not a complete donation
reconciliation.**

The watchdog runs approximately twice an hour and may be delayed by
GitHub scheduling. It requires an actually successful `recompute` job;
a green workflow with skipped ingestion does not count. A failure opens
one deduplicated GitHub alert issue. A stale results-branch commit alone
does not imply failure if totals did not change.

## Failure or disaster restart

1. Record the failed update/watchdog run, last *known-good* results
   commit, and aggregate backlog. Do not disclose donor details.
2. Set `CWKC_INGESTION_ENABLED=false` to prevent **new** jobs. It
   does **not** stop one already processing. Keep local poller off unless
   explicitly coordinating a fallback.
3. Run a read-only reconciliation and inspect errors (Sheets 429/403,
   ambiguous LGL fields, schema mismatch, missing branch or IMAP flag
   failure). Never mark failed messages Seen or erase test/real donations
   merely to clear an alert.
4. Repair with a reviewed PR or authorized credential correction.
   Stored MIME SHA-256 IDs protect replay of the **same notification**,
   but do not prove separate emails represent distinct gifts.
5. If still inside the authorized window, resume only after verifying
   the fix; compare source totals, new data commit and Pages snapshot.
   Close the alert only after confirmed recovery.
6. At/after Dec 7 **20:00 ET**, never quietly extend the season gate.
   Escalate late/failed collections to both Hillels for a documented
   final reconciliation and publication decision.

Website-code rollback does **not** undo Google Sheet writes or email
acknowledgments. Keep #41 open until final sign-off and actual
production cutover verification.
