# CWKC 2026 — launch status and checklist

**Status (November 10, 2026): EARLY GIVING HAS STARTED; production ingestion NOT YET CLEARED.**
Both schools have finalized their public and staff form labels. Organizers will not make further UVA graduation-year changes. The four November 10 notification examples are our accepted email contract. A blank UVA alumni year means **no Class of 2026 credit**, not a rejected gift; a related student's year never substitutes for the donor's. Parser coverage is in [PR #69](https://github.com/msaperst/cwkc-v2/pull/69). The remaining release gates concern reconciliation, end-to-end verification and live operations.

For repeatable operational instructions, see [Operations](operations.md); for form mappings, see [Forms](forms.md). [Issue #41](https://github.com/msaperst/cwkc-v2/issues/41) is the concise launch tracker.

## Event settings and decisions

| Item | Current state |
| --- | --- |
| Contest | UVA vs VT, November 30–December 7, 2026 |
| Configured window | Nov 30 **00:00 America/New_York** to Dec 7 **20:00 Eastern** (exclusive end); confirm opening hour with organizers |
| Early gifts | Schools have already distributed donation links and are receiving gifts. Count eligible early gifts **at kickoff**, not upon receipt; `cwkc.org` donation buttons stay disabled until kickoff |
| Scoring | **15 points** implemented in [PR #58](https://github.com/msaperst/cwkc-v2/pull/58); no separate undergraduate-giving category |
| Multiple affiliations | **Agreed:** credit every independently eligible scoring category, but count gift dollars and unique donors only once |
| Class of 2026 | May 2026 **donor alumni** class; the child's or grandchild's year must not count |
| Hanukkah photos | Eligible submissions score regardless of public-photo consent; displaying an image requires explicit opt-in **plus review** |
| Alumni gatherings | In person, at least four attendees including the host |
| Processing | Scheduled GitHub Actions, `cwkc-results` publication branch; `CWKC_INGESTION_ENABLED` remains **off** until go/no-go |

**Accounting decisions still to confirm:** monthly recurring gifts are presently annualized ×12; VT's optional $75,000 challenge grant is **not** automatically added or treated as workplace matching. See [#35](https://github.com/msaperst/cwkc-v2/issues/35).

## Final LGL notification contract (Nov 10)

| Form | Donor alumni field | Intended / related year fields | Missing alumni year |
| --- | --- | --- | --- |
| UVA public / backend | `Alumni Grad Year` | `Intended Grad Year` / `Related Grad Year` | **Accept donation**, no Class-of-2026 credit |
| VT public / backend | `Alumni Graduation Year` | `Intended Graduation Year` / `Related Student Graduation Year` | **Accept donation**, no Class-of-2026 credit |

- [ ] Merge and verify [#69](https://github.com/msaperst/cwkc-v2/pull/69): four synthetic quoted-printable email fixtures, exact status/amount/checkbox recognition and correct alumni-only scoring. VT's known pre-edit, duplicate-year `Current Parent||Alumni` notification must retain valid donor dollars **without guessing year**.
- [ ] Complete final automated golden-path tests from email → normalized Sheet → score CSV → browser, with mixed categories, recurrence and anonymity. No production mailbox writes for testing.
- [ ] Privately review any genuine early submissions with **unknown donor alumni year** that might deserve Class of 2026 credit, using LGL as the authoritative record; do not assume a related student's 2026 year proves alumni eligibility.

## Before Nov 30 production ingestion

- [ ] Confirm recurring ×12 and VT grant accounting with both Hillels; verify website/rules-page parity and the precise kickoff hour ([#32](https://github.com/msaperst/cwkc-v2/issues/32), [#35](https://github.com/msaperst/cwkc-v2/issues/35)).
- [ ] **Reconcile the test submissions** with authorized Hillel staff. Preserve the genuine paid public gifts; exclude **all non-paid backend test entries**, including November 6 and November 10 UVA/VT examples, from **both** LGL accounting and the eligible email backlog, with an audit trail. Do not silently delete real financial data or assume all $5 submissions are duplicates.
- [ ] Privately retain/back up historical `entries` data; prepare clean `entries_2026` with `NORMALIZED_FIELDS` plus `submission id`. Confirm the **GCP service account**, not just the human account, can read/write the intended sources. Set `CWKC_DONATIONS_WORKSHEET=entries_2026` ([#34](https://github.com/msaperst/cwkc-v2/issues/34)).
- [ ] Perform the **authorized read-only** `python -m scraper.getLglFormData --reconcile-only` preflight with ingestion off; verify `legacy=0`, `id_tracking=enabled`, pending-email inventory, and compare privately against authoritative LGL records. This command **does not parse** pending messages or verify received dollars.
- [ ] Verify participation Sheet access and read-only `python getGoogleFormData.py --dry-run` from `scraper/`; remove all temporary Form test responses ([#41](https://github.com/msaperst/cwkc-v2/issues/41)).
- [ ] Bootstrap `cwkc-results` from approved empty/safe `main` CSV; separately authorize and verify a **real synthetic GitHub Pages deployment**. Offline [PR #56](https://github.com/msaperst/cwkc-v2/pull/56) does not verify live permissions ([#38](https://github.com/msaperst/cwkc-v2/issues/38)).
- [ ] Assign primary and backup operators; verify receipt of watchdog/Actions alerts, recovery procedure, and final cutoff/reconciliation responsibility ([#40](https://github.com/msaperst/cwkc-v2/issues/40)).
- [ ] Receive both Hillels' final sign-off, then enable `CWKC_INGESTION_ENABLED=true` **at** the approved opening instant—not earlier.

## Implementation status

The 2026 site, scoring, initial four-email parser tests, participation forms, replay-safe ledger, separate results branch, watchdog and offline recovery tests are **merged**. The November 10 final-form normalization fixes are **proposed in PR #69**, not yet released. See the [launch tracker #41](https://github.com/msaperst/cwkc-v2/issues/41) for release readiness.

**Never** use real donor records as fixtures, make unapproved chargeable donations, mark failed messages as read, or move the competition window to bypass a failure. See [Pause, recover or close](operations.md#pause-recover-or-close).
