# Implementation Plan

## Scope

Collect these four pre-filtered searches once daily: Hertz Rent2Buy, Hertz
Bedford, Enterprise Car Sales, and Avis Car Sales. Produce a Chicago-time CSV
grouped by site, sorted by price, and maintain a SQLite history of observed
inventory.

## Phase 1 — environment review

The known Lightsail host is Amazon Linux 2023 with 2 vCPU, about 916 MiB RAM,
40 GB disk, and no swap. It is shared with the RSI bot and an English-test
application. The application will therefore run one browser session and one
source at a time. Before deployment, a read-only current-state check will
confirm available memory/disk, Python, Chromium/Playwright availability, and
existing scheduled jobs. No infrastructure changes are in scope.

## Phase 2 — accessibility proof

For each exact URL, the probe will launch headless Chromium, wait for listing
content, inspect cards, try to read vehicle/title/price/mileage, and detect
pagination or a Load More control. It saves a screenshot and sanitized HTML
when collection fails. CAPTCHA, denial pages, and other access restrictions
are reported as limitations; the collector will not evade them.

## Phase 3 — collector module

`config/sources.py` holds the exact URLs and source metadata. `scrapers/`
contains a shared respectful Playwright runner and source-specific selectors.
The collector normalizes values, keeps missing values as null, deduplicates by
VIN or URL, and records each source separately. It does not classify a source
failure as zero listings.

`storage/database.py` stores runs, observations, and source errors in SQLite.
`reports/csv_report.py` produces `output/car_inventory_YYYY-MM-DD.csv` with
the collection timestamp in America/Chicago. At least two successful source
snapshots are required before the project can identify additions, removals,
price changes, or mileage changes.

## Phase 4 — operator-owned scheduling

After manual validation, install dependencies in a dedicated virtual
environment outside the other applications. The cron job should use
`flock -n` to prevent overlap, set `TZ=America/Chicago`, run at 07:00, and
write stdout/stderr to this project's log directory. Browser installation and
any operating-system packages must be assessed against the shared server's
remaining RAM and disk first.

Example (adapt paths after deployment):

```cron
TZ=America/Chicago
0 7 * * * flock -n /opt/App/car-inventory-monitor/run.lock /opt/App/car-inventory-monitor/.venv/bin/python /opt/App/car-inventory-monitor/main.py >> /opt/App/car-inventory-monitor/logs/cron.log 2>&1
```

## IP-rate and reliability posture

Daily use is low frequency, but no public site can guarantee it will not rate
limit a cloud IP. The collector minimizes its footprint: one browsing context,
serial sources, no aggressive reloads, small retry limit, and a delay between
sites. If a site blocks access, leave it marked failed and use a dealer-provided
alert, API, feed, or manual review rather than attempting to bypass controls.

## Acceptance checks

1. Run `python main.py --probe` and review each source result.
2. Run `python main.py` manually; confirm a dated CSV, SQLite run records, and
   no source failure is reported as empty inventory.
3. Run it again after a successful snapshot and review detected deltas.
4. Only then add the daily cron entry and inspect its first run.
