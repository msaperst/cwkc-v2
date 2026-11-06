# Developing CWKC

See [README](../README.md) for the overview. This guide covers **the current code**, not annual organizer decisions. Use a feature branch and PR; `main` is protected.

## Local setup and tests

Requires Git, **Python 3.12**, Node.js **24** and npm. From the repository root:

~~~bash
npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
python -m http.server 8000 --directory public
~~~

Open http://localhost:8000. The site is static—**no build step or private credentials** are needed for a frontend preview. Outside the event window scores may be hidden; test the timer with synthetic clock fixtures, **not by changing production dates**.

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
python -m pytest scraper/tests --cov=scraper --cov-report=term-missing
npx playwright install chromium     # once
npm run test:browser
~~~

Jest covers site calculations/timer; pytest covers normalization, ledger, score calculations, season gates and recovery; Playwright uses intercepted synthetic CSV responses on desktop/mobile. CI also runs SonarCloud and GitGuardian. Python CI installs exact-version/hashed wheels from `scraper/requirements-ci.lock` targeting Python 3.12 / Linux x86_64.

## Component map

| Path | Responsibility |
| --- | --- |
| `public/index.html`, `public/assets/js/main.js` | Static site, labels, score comparisons and timer |
| `public/assets/css/main.css`, `tailwind.js` | Styles and colors |
| `public/assets/config/season.json` | Canonical season dates/timezone |
| `scraper/getLglFormData.py`, `EmailParser.py` | LGL MIME parsing, validation, normalization and IMAP acknowledgment |
| `scraper/donation_ledger.py` | Durable, replay-aware private Google Sheet writes |
| `scraper/CalculateValues.py` | Donation metrics, affiliation and Class of 2026 eligibility |
| `scraper/getGoogleFormData.py` | Current participation response Sheets and scores |
| `public/assets/csv/results.csv` | Derived public scoreboard contract, not the donor source of truth |
| `.github/workflows/` | CI, gated updates, Pages deployment and watchdog |

The reference implementation is designed for exactly **two schools** (`uva`, `vt`). For reusing it with other participants, see [Adapting](adapting.md).

## Changing a season or rule

**Dates:** Edit `public/assets/config/season.json` with offset-aware timestamps, then run:

~~~bash
python -m scraper.season_config --write
python -m scraper.season_config --check
~~~

This also regenerates browser metadata. The GitHub Actions **fixed UTC cron schedules** in `update.yml` and `watchdog.yml` must be checked separately.

**Scoring:** Treat the form label/answer contract → `donation_ledger.NORMALIZED_FIELDS` → `CalculateValues` metric keys → CSV headers → HTML scoring selectors and `data-points` → JS/Playwright fixtures as **one change**. Cover one-status, multi-status and invalid/ambiguous-year cases. Never attribute a related student's graduation year to a donor's alumni class.

**UI:** Preserve the existing HTML IDs, `.score-area`, `.winner`, `.points`, `data-points`, `.days`, `.hours`, `.minutes`, `.seconds` and `.enable-during-contest` unless updating their consumers/tests together. Logo and social preview metadata both need checking. Verify responsive layout and accessible controls.

**Integrations:** [Forms](forms.md) documents LGL/Google schemas and authorized read-only checks. [Operations](operations.md) covers live access, controlled publishing and failure recovery.

Never commit real notifications, backend form links, service-account credentials or identifying donor data. A manual importer run may mutate **live** Sheets and IMAP Seen flags even with GitHub Actions ingestion switched off. Use fabricated fixtures or separately approved isolated resources.
