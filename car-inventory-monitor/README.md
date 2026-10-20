# Daily Used Car Inventory Monitor

An isolated Python/Playwright service that collects the four exact dealer
searches supplied for the Dallas area, writes a daily CSV, and preserves
inventory history in SQLite. It is intentionally separate from the static
vehicle-shopping site at this repository's root.

## Current status

The initial fetcher is implemented. It is designed to be run manually first,
then from a once-daily Lightsail cron job supplied by the operator.
No server changes, browser installs, cron changes, or deployments are made by
this project.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the phased approach,
operational constraints, and the validation criteria before enabling a daily
job. The current environment review and blocked browser proof are recorded in
[PHASE_1_AND_2_FINDINGS.md](PHASE_1_AND_2_FINDINGS.md).

## Planned local usage

```powershell
cd car-inventory-monitor
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
python main.py
```

The command will create `output/`, `logs/`, and `data/` if necessary. These
runtime files are excluded from Git.

## Safety and collection policy

- The original filtered URLs are stored verbatim; their criteria are never
  broadened or reconstructed.
- One source is processed at a time with a pause between sources. Retries are
  limited and no CAPTCHA or access-control bypass is attempted.
- A blocked or failed source is recorded as an error, never interpreted as an
  empty inventory snapshot.
- Screenshots and sanitized diagnostic HTML are retained only on failures.
- SSH keys, credentials, and server configuration are not copied here.
