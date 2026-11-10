# Connecting donation and participation forms

Two sources feed the public scoreboard; **neither payment nor restricted photo files are handled by the public website**.

| Source | Data path |
| --- | --- |
| Donations | Little Green Light (LGL) forms → notification email → `getLglFormData.py` → private normalized Sheet → results CSV |
| Participation | Google Forms → linked response Sheets → `getGoogleFormData.py` → results CSV |

The scheduled workflow reads both sources during the authorized event window. An always-on local IMAP poller or Apps Script dispatch is **optional**, not needed for the default deployment. See [Operations](operations.md) for credentials, publishing and failure recovery.

## LGL: notification contract

There are four separate variants: **UVA public, UVA backend, VT public, VT backend**. Verify each one by receiving an actual, **sanitized** notification after any form change.

1. **Routing:** the expected mailbox is `servicecwkc@gmail.com`, with unread mail sent by `lglforms-submissions@littlegreenlight.com`. The `From` display name must identify `Brody Jewish Center` (UVA) or `Hillel at VT` (VT); `Form title` must distinguish front versus back end. See `EmailParser.determine_source`.
2. **Encoding and fields:** notifications use a two-column HTML table, usually single-part quoted-printable. Parse the MIME content, not raw quoted-printable text. Labels and option values are the contract—not the question's visual help text. Check amount (`Total Amount`/`Gift Amount`), name and donor phone, affiliations, recurring flag, anonymity, first-time gift and workplace referral.
3. **Graduation years (final Nov 10 contract):** VT emits `Alumni Graduation Year`, `Intended Graduation Year` and `Related Student Graduation Year`. UVA uses the shorter `Alumni Grad Year`, `Intended Grad Year`, `Related Grad Year`. **Only an explicitly identified donor alumni year counts for Class of 2026.** UVA may leave that field blank for an Alum + Current Parent donor; score other eligible categories without class credit. Never use a related student's 2026 year as the donor's year. One verified legacy VT public form sent two ambiguous `Graduation Year` labels: discard those *years only*, retain its legitimate donation and flag for private reconciliation; other unexpected duplicate fields still fail closed.
4. **Multi-affiliation:** retain every applicable affiliation but count actual gift dollars once and unique donors once. VT undergraduate and graduate statuses both normalize to `Current Student`; the separate undergraduate *point category* no longer exists.
5. **Other distinctions:** a workplace-match request is not proof that matching funds were received. VT's separate challenge-grant opt-in is not a workplace-match gift. Recurring monthly commitments currently annualize ×12; organizer accounting rules must be confirmed. A staff-entered/backend gift is not inherently evidence that money was received—reconcile it with LGL.
6. **Staff forms:** **do not publish backend form URLs or LGL editor URLs in this repo or on the public site**. Restrict staff access at the LGL/organizational level; obscurity of an URL is not access control.

The importer stores `donation_ledger.NORMALIZED_FIELDS` and a `submission id` on a private, season-specific worksheet. The ID guards replay of the **identical MIME message**, not separate notifications of the same transaction. Conflicting amounts/statuses and malformed messages still fail closed and stay unread. **Missing alumni class-year information alone does not invalidate a legitimate gift**; non-class categories score, and the alumnus's year can be verified against LGL privately later. Because successful donations are marked Seen after durable storage, record year-unknown entries for follow-up using private Sheet IDs, not public issue comments.

For the finalized November 10 form sample contracts and pre-ingestion reconciliation, see the [launch checklist](2026-launch-runbook.md) and [#33](https://github.com/msaperst/cwkc-v2/issues/33). No real donor identities, staff form URLs, credentials or full raw notifications should appear in source fixtures or public issues.

### Read-only preflight

After an authorized operator configures the private mailbox and GCP service account:

~~~bash
python -m scraper.getLglFormData --reconcile-only
~~~

It reports unread/stored counts and legacy-row/ID readiness **without marking mail read, writing Sheets or publishing CSV**. It does **not** validate the pending emails' fields or reconcile amounts with LGL's financial records. A normal importer run with live credentials **can mutate** IMAP Seen flags and Google Sheets even while the GitHub workflow's ingestion switch is off.

## Google Forms: participation

1. Create each Form and its linked response Sheet. Share the Form/Sheet with the authorized human editor **and separately** share the response Sheet with the GCP service account's `client_email`. A human's Editor share does not grant the API bot access.
2. Verify the exact Sheet/tab and header columns before mapping them in `getGoogleFormData.py`; the implementation currently uses fixed IDs/columns, not auto-discovery. Retain a current-season boundary so historical responses cannot count.
3. **Hanukkah:** one qualifying participant per normalized email per school. The eligible respondent's Yes answer determines eligibility; photo public-display permission is **independent** of scoring. A photo is not publishable without explicit consent and organizer moderation, including permissions for any minors.
4. **Alumni gatherings:** in-person gathering of four or more attendees including the host, with a required photo. Validate and deduplicate source responses under the agreed rules.
5. Test with fabricated/authorized non-financial responses, then remove test rows from **both** the linked Sheet and Forms response store and verify a clean read-only baseline.

From `scraper/` with an authorized, local, gitignored `spreadsheet_credentials.json`:

~~~bash
python getGoogleFormData.py --dry-run
~~~

This reads participation sources and reports aggregate results without writing the CSV or publishing. A public slideshow is optional and separate from scorekeeping; see [#50](https://github.com/msaperst/cwkc-v2/issues/50).

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Missing email | Sender/To address, mailbox `UNSEEN` filter, LGL notification settings |
| Wrong school/source | `From` display name and `Form title` |
| Bad status, year or match | Actual HTML table labels and option text; synthetic regression fixture |
| Missing/ambiguous donor alumni year | Withhold Class of 2026 credit only; reconcile private Sheet record against LGL. Unexpected duplicate labels still fail closed |
| Sheets 403 | Access for the **GCP service account** to the exact workbook/tab |
| Sheets 429 or failed append | The replay ledger's read-after-write and retry path; never blindly append |
| Incorrect scores | Source tabs, normalized fields, CSV schema, scorer and public HTML hooks together |

See [Operations: Pause, recover or close](operations.md#pause-recover-or-close) before repairing any live import.
