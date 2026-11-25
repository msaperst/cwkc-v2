# Development

Use a feature branch and pull request; `main` is the reviewed production source. The frontend is **static** (HTML, CSS/Tailwind CDN and JavaScript), so there is no website build step.

## Run and test locally

From the repository root, with Python 3.12 and Node.js 24:

~~~bash
npm ci
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scraper/requirements-test.txt
python -m http.server 8000 --directory public
~~~

Open http://localhost:8000. Test without production credentials:

~~~bash
npm test
python -m pytest scraper/tests --maxfail=1 -q
python -m pytest scraper/tests --cov=scraper --cov-report=term-missing
npx playwright install chromium
npm run test:browser
~~~

Jest covers the UI, timer and score rendering; pytest covers parsing, durable ledger writes, scoring and date gates; Playwright tests desktop/mobile rendering using synthetic data. CI runs these tests and security/static analysis. Python CI installs hash-pinned dependencies from `scraper/requirements-ci.lock`.

## Code map

| Files | Responsibility |
| --- | --- |
| `public/index.html`, `public/assets/js/main.js` | Static site, countdown, score display |
| `public/assets/css/main.css`, `public/assets/js/tailwind.js` | Styles and theme |
| `public/assets/config/season.json`, `scraper/season_config.py` | Single source of truth for event dates and generated JS config |
| `scraper/getLglFormData.py`, `EmailParser.py`, `lgl_forwarding.py` | Validate and normalize direct/forwarded LGL emails |
| `scraper/affiliations.py`, `CalculateValues.py` | Canonical categories and donation scoring |
| `scraper/donation_ledger.py` | Verified, deduplicated private Sheets persistence |
| `scraper/getGoogleFormData.py` | Hanukkah and gathering scoring |
| `scraper/scoreboard_snapshot.py`, `public/assets/csv/results.csv` | Published CSV contract |
| `.github/workflows/{update,deploy,watchdog,test}.yml` | Scheduled updates, Pages, monitoring and CI |

## Change safely

**Season:** edit `public/assets/config/season.json` (offset-aware local Eastern timestamps), then run:

~~~bash
python -m scraper.season_config --write
python -m scraper.season_config --check
~~~

Update the **UTC cron windows** in `.github/workflows/update.yml` and `watchdog.yml` separately. Avoid testing by modifying real event dates.

**Forms/scoring:** update aliases and fields, normalized column schema, calculator metrics, CSV headers, HTML IDs/`data-points` selectors, and synthetic fixtures together. Multi-affiliation donors may qualify in several scoring categories but must not be double-counted in total dollars or donor counts. Keep alumni donor years distinct from related students' years.

**UI:** preserve `.score-area`, `.winner`, `.points`, timers (`.days`/`.hours`/`.minutes`/`.seconds`), `.enable-during-contest` and JS-targeted IDs unless all consumers/tests are updated. Check responsive behavior and keyboard accessibility.

**Live operations:** read [Operations](operations.md) before touching real mailbox or Sheets. Never put private donor data, LGL staff links or Google credentials in repository files, fixtures, Actions logs or issues. Track feature requests and future work in [GitHub issues](https://github.com/msaperst/cwkc-v2/issues).
