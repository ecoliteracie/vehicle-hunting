# Deployment Plan — Amazon Linux 2023

This is a plan only. No server package, virtual environment, application file,
or scheduled job has been created.

## Current capacity evidence

The shared Lightsail instance previously reported 559 MiB available RAM, 511
MiB swap, and 35 GB free disk. A local idle headless Playwright/Chromium
process tree was measured at **254.6 MiB working set** and **198.4 MiB private
memory**. This is not a server benchmark, so use **300 MiB temporary headroom**
as the deployment planning budget until measured on Lightsail.

The instance runs the RSI bot and English-test service. Do not schedule this
collector unless a manual server run completes without memory pressure and
leaves adequate capacity for those services.

## Approval-gated steps

1. Create `/opt/App/car-inventory-monitor` with an owner-approved service
   account or directory ownership model that does not affect the other apps.
2. Create a dedicated virtual environment; do not use the RSI bot venv:
   `python3 -m venv /opt/App/car-inventory-monitor/.venv`.
3. Install the pinned Python requirements and the Playwright Chromium runtime
   in that environment. Before completing this step, check disk use and system
   libraries; browser binaries can require several hundred MB.
4. Upload only the source files, excluding local SQLite data, logs,
   diagnostics, and browser caches.
5. Run `main.py --probe` once as the deployment user. Confirm Enterprise and
   Avis output, with Hertz remaining disabled.
6. Measure the process tree during that server run (`ps`, `free -m`, and
   service status before/during/after). Stop if available memory falls below a
   safe operating margin or either hosted service degrades.
7. Review missing Avis fields and resolve them before treating its snapshot as
   complete. Only then consider a manual full run; scheduling remains a
   separate approval.

## Resource recommendation

Do not install or schedule on the current host yet. The measured local idle
browser footprint is material relative to a sub-1-GB shared server. If the
server preflight cannot demonstrate roughly 300 MiB of free headroom during a
manual collection, use a larger instance or a separate small worker instead.
