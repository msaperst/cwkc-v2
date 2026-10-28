# Commonwealth Kiddush Cup

A live fundraising competition website built for **two Hillels**. Each organization
collects donations through its own Little Green Light (LGL) forms. This project
combines those gifts with Google Forms participation activities, calculates
competition metrics, and publishes a points scoreboard to GitHub Pages.

**CWKC website:** https://cwkc.org

![Overview of the data flow](highLevelWorkflow.png)

## What it does

1. **Collect:** The Hillels own the payment forms. LGL sends donation
   notifications to a shared processing mailbox; Google Forms record
   non-financial participation in linked Google Sheets.
2. **Calculate:** Python scripts normalize new donation emails, prevent replay
   of already stored emails, read the participation Sheets, and update
   `public/assets/csv/results.csv`.
3. **Display:** A static HTML/JavaScript site compares the two sides across
   scoring categories. The HTML supplies category weights through
   `data-points`; JavaScript updates totals, winners, donor names and the timer.
4. **Publish:** GitHub Actions refreshes results during the configured event
   window. Approved application code lives on `main`; published scores are
   committed separately to `cwkc-results`. A watchdog reports failed or
   stalled updates.

`scraper/pollEmail.py` and Google Apps Script dispatches are optional
ways to request a refresh. **The scheduled GitHub workflow already polls both
sources; neither extra trigger is required for the default setup.**

## Use the application

**As a visitor:** Open the public site, follow your organization's donation
link during the giving period, and return to see categories and totals.
Donations are processed by the Hillels' forms, **not by this website**.
Participation links (when present) lead to separate Google Forms.

**As an organizer:** Set the competition dates, scoring rules, donation
forms and response Sheets before opening; use GitHub Actions to monitor
updates; verify donations against your LGL records. You don't need
a continuously running personal computer. Start with
[Running and deploying](docs/operations.md).

**As a developer:** Run the site without credentials, change the HTML/JS
or Python code, and test with synthetic records. Start with
[Development](docs/development.md).

**As another Hillel:** This is a **working example, not a white-label
one-click service**. You can fork the repository, but names, sources,
scoring rules and branding require code changes. Follow
[Adapting CWKC for another competition](docs/adapting.md).

## Quick start for developers

Requires Git, **Python 3.12**, **Node.js 24** and npm.

~~~bash
git clone https://github.com/msaperst/cwkc-v2.git
cd cwkc-v2
npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
python -m http.server 8000 --directory public
~~~

Open http://localhost:8000. No mailbox, Google Sheet or payment credentials
are needed to preview the website. On Windows activate the environment
from `.venv/Scripts/`. Score display is time-gated; use the offline tests
to exercise competition-time behavior.

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
npx playwright install chromium
npm run test:browser
~~~

See [Development](docs/development.md) for the architecture, test structure,
and how to change scoring categories safely.

## Documentation

| Guide | What you'll find |
| --- | --- |
| [Development](docs/development.md) | Running, testing and changing the frontend, parser and scoring logic |
| [Connecting forms](docs/forms.md) | Setting up LGL donation notifications and Google Form response Sheets |
| [Running and deploying](docs/operations.md) | Credentials, event setup, schedules, deployments, monitoring and recovery |
| [Adapting for another Hillel](docs/adapting.md) | What can be reused, what is hardcoded, and how to create an independent fork |

The [current CWKC event checklist](docs/2026-launch-runbook.md) is separate
from these general guides. It records this year's outstanding organizer
decisions and launch checks; it is **not** part of the reusable app setup.

## Main files

| Path | Role |
| --- | --- |
| `public/index.html` and `public/assets/js/main.js` | Public scoreboard and scoring display |
| `public/assets/config/season.json` | Competition dates and timezone |
| `public/assets/csv/results.csv` | Scoreboard data contract |
| `scraper/getLglFormData.py` and `EmailParser.py` | LGL email parsing and normalization |
| `scraper/donation_ledger.py` and `CalculateValues.py` | Stored submissions and donation metrics |
| `scraper/getGoogleFormData.py` | Google Forms participation totals |
| `.github/workflows/` | Tests, result updates, deployment and monitoring |

**Before running live integrations:** These scripts can write private
Sheets, mark emails read, and publish results. Do not use a production
mailbox, real donations, or current season Sheets as test fixtures.
Use the documented isolated tests and preflight checks first.
