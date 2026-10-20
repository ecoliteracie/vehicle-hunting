import csv
from pathlib import Path

from scrapers.models import SourceResult


def write_csv(results: list[SourceResult], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["collection_timestamp", "site", "vehicle", "listed_price", "mileage", "vin", "detail_url", "dealership_location", "availability_status"])
        writer.writeheader()
        for result in results:
            if result.status != "success":
                continue
            for item in sorted(result.listings, key=lambda x: (x.listed_price is None, x.listed_price or 0)):
                writer.writerow({"collection_timestamp": result.collected_at, **item.as_dict()})
