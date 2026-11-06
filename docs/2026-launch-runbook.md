# CWKC 2026 — launch status and checklist

**Status (November 6, 2026): HOLD early-giving link distribution.**
All four LGL notification variants have been received and tested, but graduation-year fields cannot reliably distinguish the **donor** from a related **student** across UVA and VT. Both Hillels have been asked to resolve this before links go out. The November 5 "forms frozen" message is **superseded for these specific corrections**.

For repeatable operational instructions, see [Operations](operations.md); for form mappings, see [Forms](forms.md). [Issue #41](https://github.com/msaperst/cwkc-v2/issues/41) is the concise launch tracker.

## Event settings and decisions

| Item | Current state |
| --- | --- |
| Contest | UVA vs VT, November 30–December 7, 2026 |
| Configured window | Nov 30 **00:00 America/New_York** to Dec 7 **20:00 Eastern** (exclusive end); confirm opening hour with organizers |
| Early gifts | Count at kickoff, not upon receipt. Direct school LGL links are the prelaunch channel **only after form clearance**; `cwkc.org` donation buttons stay disabled until kickoff |
| Scoring | **15 points** implemented in [PR #58](https://github.com/msaperst/cwkc-v2/pull/58); no separate undergraduate-giving category |
| Multiple affiliations | **Agreed:** credit every independently eligible scoring category, but count gift dollars and unique donors only once |
| Class of 2026 | May 2026 **donor alumni** class; the child's or grandchild's year must not count |
| Hanukkah photos | Eligible submissions score regardless of public-photo consent; displaying an image requires explicit opt-in **plus review** |
| Alumni gatherings | In person, at least four attendees including the host |
| Processing | Scheduled GitHub Actions, `cwkc-results` publication branch; `CWKC_INGESTION_ENABLED` remains **off** until go/no-go |

**Accounting decisions still to confirm:** monthly recurring gifts are presently annualized ×12; VT's optional $75,000 challenge grant is **not** automatically added or treated as workplace matching. See [#35](https://github.com/msaperst/cwkc-v2/issues/35).

## Before anyone distributes donation links

- [ ] **Both schools agree on the same data contract**: separate `Alumni Graduation Year` (donor), `Intended Graduation Year` (donor currently studying), and `Related Student Graduation Year` (child/grandchild). Show each applicable question when multiple affiliations are chosen. See [#32](https://github.com/msaperst/cwkc-v2/issues/32).
- [ ] **Both schools correct public and staff/backend forms.** UVA currently uses one ambiguous `Grad Year` for different people. VT public repeats two `Graduation Year` labels; VT backend supplies a student's `Grad Year` without the donor's own year when Alum + Current Parent are selected.
- [ ] **Retest the actual emitted LGL email from each of the four forms**, with alumni+parent and single-affiliation cases; verify safe normalization, Class of 2026 eligibility, and delivery to `servicecwkc@gmail.com`. The existing parsers intentionally block unsafe variants. See [#33](https://github.com/msaperst/cwkc-v2/issues/33).
- [ ] **Reserve time for fixes and repeat verification before outreach.** Any donations already received require source-level reconciliation; new field labels do not repair old notifications.
- [ ] Get explicit organizer go-ahead to circulate the links **only after** these checks.

## Before Nov 30 production ingestion

- [ ] Confirm recurring ×12 and VT grant accounting with both Hillels; verify website/rules-page parity and the precise kickoff hour ([#32](https://github.com/msaperst/cwkc-v2/issues/32), [#35](https://github.com/msaperst/cwkc-v2/issues/35)).
- [ ] **Reconcile the test submissions** with authorized Hillel staff. Preserve the genuine $5 public gifts; exclude any non-paid backend test entries (including the UVA $0.01 and VT $20 examples) from **both** LGL accounting and the eligible email backlog, with an audit trail. Do not silently delete real financial data.
- [ ] Privately retain/back up historical `entries` data; prepare clean `entries_2026` with `NORMALIZED_FIELDS` plus `submission id`. Confirm the **GCP service account**, not just the human account, can read/write the intended sources. Set `CWKC_DONATIONS_WORKSHEET=entries_2026` ([#34](https://github.com/msaperst/cwkc-v2/issues/34)).
- [ ] Perform the **authorized read-only** `python -m scraper.getLglFormData --reconcile-only` preflight with ingestion off; verify `legacy=0`, `id_tracking=enabled`, pending-email inventory, and compare privately against authoritative LGL records. This command **does not parse** pending messages or verify received dollars.
- [ ] Verify participation Sheet access and read-only `python getGoogleFormData.py --dry-run` from `scraper/`; remove all temporary Form test responses ([#41](https://github.com/msaperst/cwkc-v2/issues/41)).
- [ ] Bootstrap `cwkc-results` from approved empty/safe `main` CSV; separately authorize and verify a **real synthetic GitHub Pages deployment**. Offline [PR #56](https://github.com/msaperst/cwkc-v2/pull/56) does not verify live permissions ([#38](https://github.com/msaperst/cwkc-v2/issues/38)).
- [ ] Assign primary and backup operators; verify receipt of watchdog/Actions alerts, recovery procedure, and final cutoff/reconciliation responsibility ([#40](https://github.com/msaperst/cwkc-v2/issues/40)).
- [ ] Receive both Hillels' final sign-off, then enable `CWKC_INGESTION_ENABLED=true` **at** the approved opening instant—not earlier.

## Implementation status

The 2026 site, scoring, four-email parser regression tests, participation forms, replay-safe ledger, separate results branch, watchdog and offline recovery tests are **merged**. See the [launch tracker #41](https://github.com/msaperst/cwkc-v2/issues/41) for the concise PR map; this checklist tracks only remaining approvals and live verification.

**Never** use real donor records as fixtures, make unapproved chargeable donations, mark failed messages as read, or move the competition window to bypass a failure. See [Pause, recover or close](operations.md#pause-recover-or-close).
