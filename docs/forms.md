# Forms, normalization and scoring

CWKC uses **four LGL donation forms** (UVA/VT × public/staff) and **two Google Forms** (Hanukkah photos, alumni gatherings). Forms, private file uploads and payment processing are owned by the Hillels/Google, **not** the public website.

## LGL donations

**Pipeline:** LGL email → `scraper/getLglFormData.py` / `EmailParser.py` → `scraper/donation_ledger.py` → private `entries_2026` Google worksheet → `CalculateValues.py` → public CSV.

- **Mailbox:** `cwkcservice@brodyjewishcenter.org`; direct notifications from `lglforms-submissions@littlegreenlight.com`. Forwarded notifications must come from the approved `brodyjewishcenter.org` or `hillelvt.org` domains and preserve Gmail forwarding headers, original LGL sender, subject, table and source Submission ID. Suspicious forwards fail closed.
- **School/form:** verified `From` display name and exact form title identify UVA/VT and front/back. Real notifications have a two-column HTML table; use MIME-aware parsing.
- **Amount:** use public `Total Amount` or staff `Gift amount`, including any donor-covered processing fee; do not substitute lower `Amount - Details`. Recurring monthly gifts are annualized ×12 for total/qualifying dollar categories. Workplace-match requests and VT challenge-grant opt-ins do not themselves add money.
- **Identity/privacy:** private rows contain donor name/phone and flags for anonymity, first-time giving, recurring gifts and matching requests. Anonymous donors contribute to applicable scores but **not** the public name scroller. Distinct LGL Submission IDs are unique source events; the importer deduplicates direct/forwarded copies. Two different IDs for one payment still require private LGL financial reconciliation.
- **Affiliations:** `scraper/affiliations.py` owns aliases and eligible status groups. A gift can qualify for multiple distinct scoring categories, but total dollars and unique people count only once. VT undergraduate/graduate normalize to `Current Student`. Unknown affiliation labels fail closed.
- **Alumni year:** UVA uses `Alumni Grad Year` / `Intended Grad Year` / `Related Grad Year`; VT uses `Alumni Graduation Year` / `Intended Graduation Year` / `Related Student Graduation Year`. Only the **donor's own verified alumni year** can score Class of 2026. Blank or ambiguous years withhold *class credit*, not otherwise valid gifts; conflicting repeated fields fail closed.
- **Durability:** batch writes use explicit cell ranges and readback verification **before** marking notification emails Seen. Import failures block publication. The private worksheet has the 11 normalized columns plus `submission id` (12th), and is not the published results CSV.

**Never publish staff/backend form or editor URLs.** LGL remains the authority for money received; legitimate early gifts and nonpaid test records must be privately reconciled.

### Safe LGL readiness check

With operator-managed private credentials, from the repository root:

~~~bash
python -m scraper.getLglFormData --reconcile-only
~~~

This inspects mailbox/ledger readiness **without** changing IMAP flags, rows or public CSV. It is not a payment audit and does not parse every pending message. A normal live importer *does* mutate the inbox/Sheet, independent of the GitHub workflow's kill switch.

## Google Forms participation

The workflow runs `scraper/getGoogleFormData.py` against **current 2026** linked response Sheets. Grant the actual GCP service-account `client_email` read access to both response workbooks (a human editor's permission is not enough).

- **Hanukkah:** distinct eligible respondents per normalized email and school; explicit eligibility answer controls scoring. Public display consent is **separate** from scoring or upload permission.
- **Alumni gatherings:** [2026 gathering form](https://forms.gle/mPGcizkmiCZZRV9d6), response workbook `1CygL3GcCUlX1hKqQi8j7eFy_K73_RKYPWycWs8uJlW4`, tab `Form Responses 1`. The source is **not** the archived 2022 workbook. Require in-person gathering, at least **four attendees including the host**, an eligible organizer affiliation and a photo. Only qualifying gatherings score.
- **Photos:** source uploads are not necessarily publicly readable. See [photo moderation](photos.md) for approval, consent (including any minors), Drive access, publication and takedown. Do not expose restricted Drive URLs merely because a Sheet row is accessible.

For an authorized read-only participation check, from `scraper/`:

~~~bash
python getGoogleFormData.py --dry-run
~~~

After testing, remove fake responses from the Google Forms *and* linked response Sheets.

## Common failures

| Symptom | Inspect |
| --- | --- |
| Donation missing | Unread Gmail, sender/forward validation, LGL form title |
| Unexpected donor status or year | Exact submitted field labels, aliases and private LGL record |
| Sheets 403 / missing photos | GCP service account and upload-folder permissions (separately) |
| Lost/duplicated rows | Ledger IDs, batch readback, unread status; do not blindly append/replay |
| Score mismatch | Private source rows, scorer, published CSV and HTML selectors |

For recovery use [Operations](operations.md); put unresolved work in [issues](https://github.com/msaperst/cwkc-v2/issues).
