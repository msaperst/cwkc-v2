# Adapting CWKC for another Hillel competition

CWKC is an **Apache-2.0-licensed working example**, not a hosted service, generic form importer or no-code template. Fork it only if your team can maintain Python, HTML/JavaScript, GitHub Actions and private donor data.

## What can be reused

- Responsive two-team scoreboard, timer and weighted category scoring.
- LGL email-to-private-Sheet ingestion with same-MIME replay protection, failure handling and retry.
- Participation scoring from linked Google Forms response Sheets.
- Scheduled, gated Actions updates; a distinct `cwkc-results` branch to protect published scores; a monitoring watchdog.
- Offline pytest/Jest/Playwright coverage and a synthetic Git publication/recovery rehearsal.

**Not provided:** a payment processor, auto-discovery of arbitrary forms, support for any number of schools, general-purpose deduplication of separate notifications from one gift, a no-code scoring editor or turnkey public-photo permissions/hosting.

## Adoption checklist

1. **Own infrastructure and permissions.** Fork into an organizer-controlled repo, replace branding and domain, and arrange the Hillels' LGL accounts, a dedicated notification mailbox, private Google Sheets/Forms, a GCP service account and GitHub Pages. Do not copy CWKC's donor data, production results, credentials or staff/backend form URLs. Code licensing does **not** grant permission to reuse schools' trademarks, photos or other third-party assets.
2. **Define the scoring contract first.** Write down competing organizations, categories, weights, eligible statuses, year semantics, donor identity/dedup rules, recurring-gift treatment and tie policy. Include overlapping-affiliation examples and expected totals.
3. **Change all coupled code.** Update `EmailParser.determine_source`, field/status mappings, `CalculateValues`, participation Sheet IDs/columns, CSV schema, `public/index.html` hooks, images, date and metadata, plus tests. The reference code hardcodes `uva`/`vt`, its form schemas and several site assumptions.
4. **Connect and test forms safely.** Follow [Forms](forms.md). Require distinct donor versus related-student graduation-year labels; keep backend URLs private and staff access controlled in LGL. Test all email variants and participation files with synthetic or authorized **non-payment** submissions. Never put donors' raw data in the fork.
5. **Configure and rehearse deployment.** Follow [Operations](operations.md): season settings **and** UTC cron patterns, secrets, separate current-season normalized worksheet, `cwkc-results` bootstrap, approved synthetic Pages deployment, operator/backup alerts and reconciliation.
6. **Operate and close deliberately.** Begin with ingestion disabled. Enable only after organizer approval and only during the approved date window. Reconcile final amounts with the financial source of truth; a green CI run is not a financial audit.

See [Development](development.md) for the component map and local tests. Configurable competitors, forms, branding and scoring could simplify future forks, but **those features do not exist today**.
