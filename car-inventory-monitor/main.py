import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

from config.sources import SOURCES
from reports import write_csv
from scrapers import InventoryScraper
from storage import InventoryDatabase

ROOT = Path(__file__).parent
CHICAGO = ZoneInfo("America/Chicago")


async def run(probe_only: bool) -> int:
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT / "logs" / "collector.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        scraper = InventoryScraper(browser, ROOT / "diagnostics")
        results = []
        for source in (item for item in SOURCES if item.enabled):  # Serial by design: do not overload dealer sites.
            result = await scraper.collect(source, probe_only)
            results.append(result)
            logging.info("%s: %s (%s listings) %s", source.key, result.status, len(result.listings), result.error or "")
            await asyncio.sleep(4)
        await browser.close()
    db = InventoryDatabase(ROOT / "data" / "inventory.sqlite3")
    changes_by_source = {}
    for result in results:
        changes_by_source[result.source_key] = db.save(result)
    db.close()
    if not probe_only:
        filename = f"car_inventory_{datetime.now(CHICAGO):%Y-%m-%d}.csv"
        write_csv(results, ROOT / "output" / filename)
    for result in results:
        suffix = f"; changes={changes_by_source[result.source_key]}" if result.status == "success" else f"; {result.error}"
        print(f"{result.site}: {result.status}; {len(result.listings)} listings{suffix}")
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Inspect only the first visible page; do not write a CSV.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.probe)))
