# Developing CWKC

See the [README](../README.md) for a short introduction. This guide covers
the actual source and local workflow. It is not tied to one year's event.

## Prerequisites and local preview

Use Python **3.12**, Node.js **24**, npm and Git. From repository root:

~~~bash
npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
python -m http.server 8000 --directory public
~~~

Visit http://localhost:8000. The frontend is static: there is **no build
step** and no Gmail or Google credentials needed to work on layout.
The page reads a CSV and uses CDN-supplied frontend dependencies.
It may hide scores outside the configured event window; don't change
production dates to bypass the timer when testing.

## Components and data flow

| Component | Responsibilities |
| --- | --- |
| `public/index.html` | Page copy, organization links/logos, scoring rows and `data-points` weights |
| `public/assets/js/main.js` | Clock, CSV reading, formatting, category comparisons, winner and name rendering |
| `public/assets/css/main.css` / `tailwind.js` | Presentation and site-specific design tokens |
| `public/assets/config/season.json` | Canonical dates/timezone for frontend and backend |
| `scraper/getLglFormData.py` | Unread IMAP email, field extraction, validation, ledger insert and CSV update |
| `scraper/EmailParser.py` | LGL field labels, source classification and normalized donor fields |
| `scraper/donation_ledger.py` | Exact normalized headers, MIME submission IDs, replay and API retry safety |
| `scraper/CalculateValues.py` | Donation scoring metrics for each side |
| `scraper/getGoogleFormData.py` | Participation Sheet IDs, response columns and participation counts |
| `public/assets/csv/results.csv` | Shared contract between both importers and browser |
| `.github/workflows/` | CI, guarded ingestion, Pages deployment, watchdog |

The **database-like source of truth** for normalized gifts is a private Google
Sheet; `results.csv` is the *derived*, publicly consumed output.
The current code is designed for exactly **two** competitors (`uva` and `vt`).

## Local tests

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
python -m pytest scraper/tests --cov=scraper --cov-report=term-missing
npx playwright install chromium    # one time
npm run test:browser
~~~

Jest tests the JavaScript calculations and clock; Python pytest covers parsers,
ledger, metrics, season boundaries, workflow contracts and temporary-Git
publish/restart behavior. Playwright loads the site locally in desktop/mobile
Chromium with **synthetic, intercepted CSV responses**. No tests require
real donor data or chargeable donations.

CI also runs SonarCloud and GitGuardian, and installs Python dependencies
from `scraper/requirements-ci.lock` with exact versions and SHA-256 wheel
hashes. That lock targets **Python 3.12 / Linux x86_64** and must be
regenerated and reviewed when that environment or dependencies change.
All changes go through feature branches and PR checks; `main` is protected.

## Changing the appearance or site text

Edit `public/index.html` for content, logos, links and scoring rows.
Preserve JavaScript hooks such as element IDs, `.score-area`, `.winner`,
`.points`, `data-points`, `.days`, `.hours`, `.minutes`, `.seconds`
and `.enable-during-contest`, or update the relevant JavaScript and tests
together. Site-specific colors/logos are present in HTML/CSS, not in a
universal theme setting. Verify keyboard/accessible links and mobile layouts.

For a logo or domain change, update the HTML metadata and social-card URLs,
not just the visible image. The season metadata generator currently expects
CWKC-specific HTML patterns (see `scraper/season_config.py`); maintainers
of a fork must update its tests and regexes for a new site title.

## Changing the event dates

Edit `public/assets/config/season.json` and include the correct timezone
and explicit UTC offsets:

~~~bash
python -m scraper.season_config --write
python -m scraper.season_config --check
~~~

This generates `season-config.js` and synchronizes HTML title/social
metadata. The GitHub cron patterns in `.github/workflows/update.yml` and
`watchdog.yml` are **separate fixed UTC schedules**; update them for
different event dates, even though the season gate ultimately determines
which runs may act. Test the exact opening and closing instants.

## Changing scoring rules or competitors

The donation importer writes normalized rows with the fields in
`donation_ledger.NORMALIZED_FIELDS`; `CalculateValues.calculate_all()`
creates per-school metric keys; the CSV columns generally follow
`<school>_<metric>`. Participation totals add more columns.
`main.js` reads these columns and compares paired score-area values;
the points awarded per category come from HTML `data-points` attributes.

Treat this as **one coordinated contract**:

1. Write down expected metrics, eligible individuals and example records.
2. Update parser source identification and allowed field/affiliation mappings.
3. Update calculation functions, participation rules and CSV header/seed row.
4. Update the HTML category hooks, points and any display labels.
5. Add pytest fixtures for individual, overlapping and negative cases;
   update Jest/Playwright fixtures and any snapshot schema assertions.
6. Run all suites and verify a disposable local Git publish/restart test.
   Plan a separate migration for a real published `cwkc-results` branch
   before deploying schema changes during an event.

Do **not** silently carry over another year's categories or interpret an
ambiguous LGL field. The reference repo may intentionally contain older
competition metrics until new rules are signed off.

## Integrations and safe debugging

Use [Connecting forms](forms.md) for LGL/Google Forms details, including
verifying exact notification headers and Sheet columns. Use
[Running and deploying](operations.md) for credentials, read-only mailbox
preflight, gated production updates and failure recovery.

A local call to a live importer can still mutate Sheets or IMAP Seen flags
even if GitHub Actions ingestion is switched off. Mock external sources in
tests or use **explicitly authorized isolated resources**, never a real
donation to manufacture a fixture.
