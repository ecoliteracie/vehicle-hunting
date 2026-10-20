# Phase 1 and Phase 2 Findings

Checked on 2026-10-12, without modifying Lightsail.

## Environment

| Check | Finding |
|---|---|
| Operating system | Amazon Linux 2023 |
| Capacity | 2 vCPU, 916 MiB RAM (559 MiB available at check), 511 MiB swap, 35 GB free disk |
| Python | Python 3.11.15 in `/home/kiwasaki/venv/bin/python` for the existing application user |
| Existing jobs | `kiwasaki` crontab contains weekday RSI-bot collection/processing tasks; no changes made |
| Chromium | Not installed or on `PATH` |
| Playwright | Not installed in the existing venv |

The Lightsail instance is shared with the RSI bot and an English-test site. The
new monitor must use its own virtual environment and be measured after a manual
run before any daily cron is enabled.

## Website proof of concept

No browser installation was made on Lightsail because this is a shared
production server and installing browser binaries is an infrastructure change.
The local browser probe ran on 2026-10-12. Hertz was blocked; Enterprise's
page rendered inventory but required a site-specific selector update; Avis
returned visible cards. The collector was updated to recognize Enterprise's
cards and compact mileage values such as `49k mi`.

| Website | Accessible | Vehicles Detected | Price Extracted | Mileage Extracted | Status |
|---|---:|---:|---:|---:|---|
| Hertz Rent2Buy | No | 0 | No | No | Imperva/Incapsula request-block page |
| Hertz Bedford | No | 0 | No | No | Imperva/Incapsula request-block page |
| Enterprise | Yes | 42 | Yes | Yes | Two browser pages (21 + 21), collected successfully |
| Avis | Yes | 7 vehicle cards | Yes | Yes | Placeholder/promotional cards excluded; all 7 dealer cards complete after lazy-load hydration |

The implementation is prepared for this proof: `python main.py --probe` uses
the original URLs, does not follow a CAPTCHA/access-control bypass path, and
writes diagnostics when a source cannot be read. Validate selector accuracy
and pagination behavior from this first probe before trusting or scheduling
the daily collector.
