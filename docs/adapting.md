# Adapt this project for another Hillel competition

CWKC is an **Apache-2.0-licensed codebase** demonstrating a two-organization
fundraising scoreboard. You may fork and adapt the code under that license,
but the reference implementation is **not a hosted service, configuration
wizard, or turnkey generic fundraising platform**.

It assumes a particular pair of schools, their branding, LGL field labels,
Google response Sheets, a particular metric list and an annual event.
You need someone who can modify Python and HTML/JavaScript, manage
GitHub Actions, and handle private donation records responsibly.

For the source architecture see [Development](development.md);
for connecting external data see [Connecting forms](forms.md);
for running the resulting site see [Operations](operations.md).

## What you can reuse

- A static GitHub Pages scoreboard with a live timer, paired metrics,
  weighted category points and desktop/mobile layout.
- Python ingestion of HTML LGL notification emails into a normalized
  Google Sheet, with unread-on-failure and identical-email replay safety.
- Importing additional participation totals from Google response Sheets.
- A guarded, scheduled GitHub Actions pipeline that separates reviewed
  website code from generated results.
- Pytest, Jest, Playwright, security/quality checks and an offline
  publication/restart drill.
- A GitHub watchdog that notices failed or stalled ingestion runs.

**Not included:** payment processing, arbitrary custom form discovery,
multi-school bracket scoring, a no-code rules editor, public media hosting,
turnkey deduplication of distinct emails for one transaction, or a
production-ready generic consent/gallery system.

## A practical adoption sequence

### 1. Own the accounts and copy the code

Fork this repository into a GitHub organization **controlled by your
Hillel/organizers**, not a volunteer's personal account.
Keep it private while verifying credentials and test data. Decide
whether GitHub Pages (with your own domain) and Google Sheets are
acceptable for your organization's retention, privacy and
access requirements.

Create a dedicated LGL submission mailbox, Google Forms/Sheets owner
and GCP service account. Do not copy CWKC donor data, form responses,
GitHub secrets or a production results branch into the fork.

The repository is under Apache 2.0, but permission to use its source
does **not** automatically grant permission to use the participating
schools' names, logos, photographs or other third-party content.
Replace that branding with approved assets and retain applicable
license/notice files.

### 2. Replace the branding and public site

Change the organizations' names, websites, official donation URLs,
logos and social-card metadata in `public/index.html` and the
images/styles under `public/assets/`. Update scoreboard labels,
color classes, donor-name areas, mobile presentation and any text
that refers to UVA, VT, Hoos or Hokies.

There is no general `schools.json` configuration in the current
code. The frontend JavaScript and HTML assume two specific sides;
`scraper/season_config.py` also validates/updates particular CWKC
title and metadata patterns. Update these references **and their
tests** in the fork.

Choose whether donor names will be shown publicly, and ensure that
the consent and privacy treatment match your organization policy.
The default project has donor-name output; don't reuse it blindly.

### 3. Define your own scoring contract

Decide which categories award points, how ties work, what constitutes
a unique person, how recurring gifts are counted, and which
participation activities are eligible. Get written approval from
both participating organizations.

Then change **all four linked layers**:

| Layer | What to change |
| --- | --- |
| `scraper/EmailParser.py` | LGL sender/title to school/source mapping, exact field labels, status choices, gift flags |
| `scraper/CalculateValues.py` | School codes, eligibility conditions, category calculations and returned metric names |
| `scraper/getGoogleFormData.py` | Participation Sheet IDs, response columns, activities and school matching |
| `public/assets/csv/results.csv`, `public/index.html`, `main.js` | New metric columns, category IDs/labels, paired values, weights, team display and winner text |

At present those scripts use the literal `uva` and `vt` prefixes
in multiple places. A replacement name must be propagated consistently.
The current category code includes **year-specific legacy metrics**;
review every category, not just the displayed date.

A two-competitor format is the smallest supported adaptation.
More than two competitors requires **new scoring/rendering logic**,
not another row in a configuration file.

### 4. Connect your forms (without processing real gifts yet)

Follow [Connecting forms](forms.md):

1. Identify each LGL public/back-end form and configure its exact
   submission-notification email.
2. Verify sender/header/form-title and every conditional question
   with *sanitized* examples; adapt the source classifier and
   normalizer. The existing UVA/VT mapping won't recognize a new Hillel.
3. Create a separate, empty normalized donations Sheet for the event;
   share it with your GCP service account and preserve the `submission id`
   field. No historical data is required for a new fork.
4. Create participation Google Forms and linked response Sheets;
   adapt `getGoogleFormData.py` to the new IDs/columns and rules.
   The updater polls them on its schedule; Apps Script dispatches
   are **optional**, and the included example must use *your* repo.
5. Test all variants offline with synthetic fixtures and, if explicitly
   authorized, a **separate disposable inbox and Sheet**. Never make
   real donations just to exercise the integration.

### 5. Configure time, GitHub and production

Edit `public/assets/config/season.json` with the real event year,
IANA timezone and timestamps with matching offsets, then run:

~~~bash
python -m scraper.season_config --write
python -m scraper.season_config --check
~~~

**Important:** the season validator accepts configurable timezones,
but the browser display, metadata tests and older comments may still
assume CWKC/Eastern-time labels. Inspect and update them.

Edit the **UTC cron expressions** in `.github/workflows/update.yml`
and `watchdog.yml` for your event dates; the current schedule is
not derived from the JSON. Update repo-specific URLs in
`scraper/pollEmail.py` and any optional Apps Script dispatch code.
Set up GitHub Pages/domain and the approved main-branch ruleset.

Use [Operations](operations.md) to configure GitHub Secrets, the
normalized worksheet variable, an **empty** `cwkc-results` branch,
CI requirements, watchdog notifications and an authorized synthetic
Pages rehearsal. Only enable `CWKC_INGESTION_ENABLED` after
the forms, scoring, source accounts and publication all pass a
documented go/no-go check.

### 6. Maintain it safely

At the start of each event, review rules, dates, forms, Sheets,
public branding, synthetic regression fixtures, source totals
and operator ownership. Do not assume last year's response columns,
participant categories or labels still match the new forms.

Run `npm test`, `python -m pytest scraper/tests` and
`npm run test:browser` before merging changes. If CSV headers change,
plan and test **data-branch migration** so a code deploy cannot reset
or reinterpret published data.

At closing, compare normalized and published totals with the
participating organizations' authoritative donation records.
This site is a **scoreboard**, not a financial accounting ledger.

## What would make future forks easier?

A genuinely no-code Hillel template would first need configurable
organization IDs and branding, declarative form mappings, an
editable scoring model, and configurable participation sources.
Those features **do not exist today**. The steps above document
how to adapt the working code without promising capabilities
it hasn't implemented.
