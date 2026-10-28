# Commonwealth Kiddush Cup (CWKC)

An annual fundraising competition between the University of Virginia and
Virginia Tech. This repository hosts the **public scoreboard**, the
donation/participation importers and their GitHub Actions automation.
Donations are **collected through the Hillels' LGL forms**, not directly
on this website.

**Website:** [cwkc.org](https://cwkc.org) ·
**Launch status:** [2026 readiness tracker](https://github.com/msaperst/cwkc-v2/issues/41)

![CWKC data flow](highLevelWorkflow.png)

## Start here

| What you want to do | Where to look |
| --- | --- |
| Run or develop the website | [Quick start](#local-quick-start) below |
| Understand scripts, credentials, Google Forms and LGL notifications | [Integration and developer reference](docs/integrations.md) |
| Prepare kickoff, 2026 worksheet, `cwkc-results`, alerts or rollback | [2026 launch / recovery runbook](docs/2026-launch-runbook.md) |
| See what's done and what's still blocked | [Launch tracker #41](https://github.com/msaperst/cwkc-v2/issues/41) |
| Review unapproved scoring or form contracts | [Rules #32](https://github.com/msaperst/cwkc-v2/issues/32), [LGL #33](https://github.com/msaperst/cwkc-v2/issues/33), [scoring #35](https://github.com/msaperst/cwkc-v2/issues/35), [participation #36](https://github.com/msaperst/cwkc-v2/issues/36) |

## How it works

- **Donation data:** UVA/VT LGL forms notify the CWKC mailbox.
  `scraper/getLglFormData.py` normalizes unread messages, uses private
  submission IDs to avoid replaying the **same email**, stores donations
  in a private Google Sheet, and calculates donation metrics.
- **Participation data:** Alumni-gathering and Hanukkah-photo Google Forms
  save to linked response Sheets. `scraper/getGoogleFormData.py` reads
  these records for the participation metrics.
- **Updates and publishing:** `.github/workflows/update.yml` checks both
  sources on a schedule, **only while the approved season window and
  `CWKC_INGESTION_ENABLED=true` allow it**. A changed score CSV is
  committed to the separate `cwkc-results` branch, then GitHub Pages
  publishes it. The protected `main` branch contains application code,
  not live results commits.
- **Monitoring:** `.github/workflows/watchdog.yml` checks successful
  ingestion runs and opens an alert issue on failures or a stalled
  heartbeat. An unchanged scoreboard is not itself an outage.

The legacy local IMAP poller and optional Apps Script dispatches are
**not needed for the normal scheduled-update mode**. Setup instructions
for either fallback are in the [integration guide](docs/integrations.md).

**2026 safety:** Early donations are collected through the schools' own
LGL links. CWKC ingestion remains off until **Nov 30, 2026 at
00:00 Eastern**; the configured closing instant is **Dec 7 at
20:00 Eastern**. Final scoring, overlapping-affiliation treatment,
four notification contracts and some participation permissions
still require organizer approval. Passing CI does **not** mean the
system is cleared for live donation processing.

## Local quick start

Requires **Node.js 24**, **Python 3.12** and Git.

~~~bash
git clone https://github.com/msaperst/cwkc-v2.git
cd cwkc-v2

npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
~~~

On Windows activate the environment under `.venv/Scripts/`.

To preview the site without credentials:

~~~bash
python -m http.server 8000 --directory public
~~~

Open [localhost:8000](http://localhost:8000). The browser intentionally
hides scoreboard data before kickoff. For active-event behavior,
use the synthetic Jest/Playwright tests instead of changing production dates.

### Tests

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
npx playwright install chromium   # first browser run
npm run test:browser
~~~

The browser tests use localhost and fabricated CSV values, **not real
donations or submission forms**. CI also runs SonarCloud, GitGuardian
and hash-locked Python dependencies. Every change should be developed
on a feature branch and merged through a passing PR.

## Key files

| Path | Role |
| --- | --- |
| `public/index.html` and `public/assets/js/main.js` | Public website and scoreboard |
| `public/assets/config/season.json` | Authoritative event year and Eastern-time boundaries |
| `scraper/getLglFormData.py`, `EmailParser.py`, `CalculateValues.py` | LGL ingestion and donation scoring |
| `scraper/getGoogleFormData.py` | Participation form Sheet ingestion |
| `scraper/tests/` and browser/Jest specs | Offline regression coverage |
| `.github/workflows/test.yml` | Test, coverage and SonarCloud |
| `.github/workflows/update.yml` | Authorized ingestion and result publication |
| `.github/workflows/deploy.yml` | Code-triggered Pages deployment preserving published scores |
| `.github/workflows/watchdog.yml` | Event-week heartbeat and GitHub issue alerts |

## Production and annual changes

**Do not run live import commands as smoke tests.** They can write to
Google Sheets or mark messages read even if the GitHub Actions ingestion
switch is disabled. See the [integration guide](docs/integrations.md)
for exact credentials, safe read-only preflight and form replacement.

The [launch runbook](docs/2026-launch-runbook.md) is the **single
operator checklist** for opening day, the separate 2026 worksheet,
results-branch bootstrap, fallback, rollback and cutoff. Avoid
copying these procedures into the README or individual issues.

For a new competition year, edit the configuration in
`public/assets/config/season.json`, regenerate derived site metadata
with `python -m scraper.season_config --write`, verify with
`python -m scraper.season_config --check`, and review the **separate**
annual logo, form links, scoring schema, football date and public
Hillel rules pages. A new season is **not** enabled merely by changing
a date.

Keep project and operator history in GitHub PRs/issues; keep this
README short enough that a new maintainer can identify the right guide
without reading the full incident history.
