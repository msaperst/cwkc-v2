# CWKC 2026: event-specific launch checklist

This page tracks **this year's** decisions and verification. It is not
documentation of how the tool works in general.

- [README](../README.md): what the system does
- [Development](development.md): code and local testing
- [Connecting forms](forms.md): LGL / Google Forms setup
- [Running and deploying](operations.md): repeatable season setup,
  Pages deployment, monitoring, incident recovery and cutoff procedures
- [GitHub launch tracker #41](https://github.com/msaperst/cwkc-v2/issues/41):
  the current status and workstream owners

## Confirmed event settings

| Item | Current agreement |
| --- | --- |
| Competitors | UVA / Virginia Tech Hillels |
| Contest opens | Nov 30, 2026, **00:00 America/New_York** |
| Contest closes | Dec 7, 2026, **20:00 America/New_York** (exclusive) |
| Early giving | The schools share their own direct LGL form URLs/QR codes. Gifts are counted starting at kickoff; `cwkc.org` donation buttons stay disabled before opening. |
| Data publication | Scheduled GitHub Actions with gated `cwkc-results` publishing, not a local computer left running |
| Production switch | Keep `CWKC_INGESTION_ENABLED` **off** until the approved kickoff/go-no-go |

## Still awaiting organizer agreement

- [ ] **Affiliation scoring:** One scoring affiliation per donor, or all
  applicable donation categories? Amanda's and Jana/Truman's answers differ
  (#32, #35). Confirm equivalent UVA/VT form options.
- [ ] **Recurring and grant accounting:** Confirm monthly commitment
  annualization and whether/how the VT $75,000 challenge grant affects
  total dollars and other categories (#32, #35).
- [ ] **Donation form freeze:** Verify final UVA/VT public and backend
  notifications, including distinct graduation-year labels and the
  expected recipient mailbox (#33).
- [ ] **Non-donation forms:** Confirm participation eligibility, Google
  response columns, service-account access and photo-consent language
  where relevant (#36, #50).
- [ ] **Public content:** Both schools' final rules and links match the
  agreed category definitions (#37).

## 2026 data cutover (requires operator approval)

- [ ] Retain and privately back up the historical `entries` tab
  (previous audit counted 748 historic entries); reconcile against the
  authorized LGL financial records without deleting historical data.
- [ ] Prepare the empty **`entries_2026`** normalized Sheet with
  `NORMALIZED_FIELDS` and `submission id`; verify the GCP service
  account has access. Set the Actions variable
  `CWKC_DONATIONS_WORKSHEET=entries_2026` (#34, #38).
- [ ] Run an **authorized read-only** `--reconcile-only` preflight;
  confirm `legacy=0` and `id_tracking=enabled`, and privately check
  the early-giving backlog before any live processing.
- [ ] After the approved 2026 score schema is merged, initialize the
  `cwkc-results` branch from a clean approved `main` CSV. Perform a
  separately authorized synthetic **actual GitHub Pages** rehearsal.
  Offline Git tests in #56 do **not** prove production permission (#38).
- [ ] Assign primary/backup operators; verify receipt of Actions
  failure and watchdog GitHub-issue notifications (#40).
- [ ] Confirm final reconciliation/cutoff ownership and both Hillels'
  sign-off; only then enable ingestion at the opening instant (#41).

**Do not** send paid test donations, use live donor records as
fixtures, erase email Seen flags, or extend the contest window to
bypass an ingestion failure. Follow the generic
[Operations recovery procedure](operations.md#pause-recover-or-close)
when a run fails. Closing reconciliation requires an explicit joint
organizer decision, not merely a green GitHub Actions status.
