# Connecting donation and participation forms

This guide explains how to connect or replace the external forms without
changing the live scoreboard prematurely. For application code, see
[Development](development.md); for credentials, workflows and cutover, see
[Running and deploying](operations.md).

Two input types are supported:

| Input | Where answers arrive | Importer |
| --- | --- | --- |
| LGL donation forms | HTML notification emails to the processing mailbox | `scraper/getLglFormData.py` |
| Google Forms participation activities | Google Forms linked response Sheets | `scraper/getGoogleFormData.py` |

Both importers update **different columns in the same results CSV**.
The scheduled update workflow runs both together during the authorized event
window. Google Forms email notices and Apps Script dispatches are **not
required** for this polling-based mode.

## LGL: add or replace a donation form

The reference competition uses a public and a staff/backend LGL form for
each organization. Those are **four distinct notification variants** that
must be verified separately.

1. **Decide which organization and flow the form represents.** Record the
   official public donation URL, backend form name, and the correct
   source/school. The Python parser currently infers UVA or VT from the
   **displayed From header**, and front/back from the `Form title` value
   (look at `EmailParser.determine_source`). A fork **must change this
   mapping** for its Hillels; updating URLs alone will not suffice.
2. **Have the form owner enable submission notifications** to the dedicated
   processing mailbox. The current default is `servicecwkc@gmail.com`;
   the importer searches the configured IMAP folder for **unread** mail
   from the default `lglforms-submissions@littlegreenlight.com` sender.
   `FROM_FILTER` and `MAILBOX` can override those settings.
3. **Capture the actual notification layout** with the form owner. The
   parser expects an HTML message with a first table of field/value rows.
   Check exact labels, case, option values, conditional questions,
   `Form title`, and sender branding for each flow. Examples include
   `Total Amount` / `Gift amount`, `Name - First Name`,
   `I am a/an`, `Is Recurring` and `Check all that apply`.
   This is a **code contract**, not a generic LGL data API.
4. **Resolve ambiguous fields at the source.** Repeated
   `Graduation Year`, `Grad Year` or `Intended Graduation Year`
   fields fail closed even if their values match; other conflicting
   repeated labels also fail. Use **distinct question names** for
   alumni and relatives, then verify which one should count under
   the approved scoring rule.
5. **Update the adapter and tests** (`EmailParser.py`,
   `getLglFormData.py`, and `scraper/tests/`) when the final
   labels, statuses, recurring options or school identifiers differ.
   `NORMALIZED_FIELDS` in `donation_ledger.py` defines the
   destination row contract. Preserve the submission-ID column so a
   previously imported **same MIME notification** can be recognized.
6. **Test safely before enabling production ingestion.** Use fabricated
   or organizer-approved redacted email fixtures and a fully isolated
   test inbox and Sheet. Verify all four variants, malformed amounts,
   missing fields, repeated labels, duplicate replay, acknowledgement
   failure and no partial CSV publication. Do **not** make real,
   chargeable payments merely to produce test emails.

### Normalized donation worksheet

A destination Sheet needs the fields defined by
`donation_ledger.NORMALIZED_FIELDS` plus `submission id`. The
importer will validate the header and can initialize an empty worksheet,
but it **refuses to write over old rows without IDs**. Preserve
historical seasons on separate tabs, and prepare a clean current-event
tab after approval.

Set `SPREADSHEET_KEY` to the workbook ID and
`SPREADSHEET_SHEET` to the selected tab for local runs. In GitHub Actions
the corresponding repository variable is
`CWKC_DONATIONS_WORKSHEET`; **both the importer and calculator read that
same tab**.

The read-only preflight is:

~~~bash
python -m scraper.getLglFormData --reconcile-only
~~~

Run only with authorized credentials. It reads **unread** notifications
and the normalized Sheet without acknowledging emails, modifying rows or
writing the CSV. It reports aggregate pending/previously stored counts,
legacy rows and ID tracking. It cannot establish that all real LGL
financial transactions have arrived or that two distinct emails aren't
the same donation.

## Google Forms: add or replace a participation activity

The reference app counts participation from linked response Sheets
rather than parsing Google Forms notification emails. Current examples
include alumni gatherings and memory/photo submissions.

1. **Create or identify the Google Form** and link it to a response
   spreadsheet under the intended organization account.
2. **Define eligibility and data needed** (school selection, submitter,
   attendee count or names, graduation/affiliation answers and any
   photo-consent questions). Require consent before any public image
   display; scoring and publication permissions are **separate**.
3. **Share appropriately:** give the shared Hillel Google user
   **Editor** access to the Form and, separately, the linked Sheet.
   The independent Google Cloud **service-account email** used by
   `gspread` must also be granted access to the response Sheet.
   Human Editor access alone is not API access for that bot.
4. **Inspect the actual response headers and columns.** The current
   `getGoogleFormData.py` contains **hardcoded spreadsheet IDs,
   positional column references and eligibility checks**; it cannot
   discover arbitrary Forms automatically. Change its sheet IDs,
   column mapping and scoring functions in a reviewed code PR.
5. **Add synthetic response fixtures** for qualifying/nonqualifying
   entries, blanks, renamed/reordered columns and duplicate participants.
   Verify the importer updates the intended CSV columns. Use a
   disposable Sheet for any authorized real Google API test.
6. **Check a scheduled update** after the entire workflow has been
   approved. A Google Form submission does not have to dispatch
   immediately: the normal updater periodically reads both sources.

### Optional near-real-time notification via Apps Script

Only add this if waiting for the next scheduled run is unacceptable.
It is **not a prerequisite** for normal operation.

In the **linked response Sheet**, open **Extensions → Apps Script**.
Save a repository-dispatch-capable GitHub token as a **Script property**
named `GITHUB_TOKEN` (never in script source). A sample:

~~~javascript
function triggerGithubAction() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Missing GITHUB_TOKEN script property');

  const response = UrlFetchApp.fetch(
    'https://api.github.com/repos/msaperst/cwkc-v2/dispatches',
    {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json'
      },
      payload: JSON.stringify({event_type: 'sheet-change'}),
      muteHttpExceptions: true
    }
  );
  if (response.getResponseCode() !== 204) {
    throw new Error('Dispatch failed: HTTP ' + response.getResponseCode());
  }
}
~~~

**Forks must replace the repo path.** Authorize an installable **On
form submit** trigger under the dedicated organization account. It runs
as its creator, so avoid a volunteer's personal account. Add a second
On change trigger **only** if manual row edits must cause updates; duplicate
triggers generate redundant runs. Test dispatches only in an approved
isolation environment; GitHub's main-branch/season switch still guards
the receiving updater.

## When something breaks

- **Wrong school or donation type:** inspect the actual From header,
  `Form title`, `determine_source`, and the fixture used to approve it.
- **Missing or wrong metric:** check the normalized columns, exact
  answer values, Sheet ID, column indexes and CSV header together.
- **Permission error (403):** confirm the **GCP service account**
  was shared on the correct Sheet, not just the human CWKC account.
- **Sheets API 429:** the ledger retries transient failures and verifies
  a possibly completed append before retrying; do not replay blindly.
- **Ambiguous LGL email:** it remains unread on failure. Fix the
  field/adapter contract and reprocess, rather than marking it read.
- **Old donations in the new scoreboard:** verify both importer and
  calculator use the same season-specific `SPREADSHEET_SHEET`.

See [Running and deploying](operations.md) for safe pause/restart and
cutoff reconciliation. These procedures affect private records and must
be performed by an authorized operator.
