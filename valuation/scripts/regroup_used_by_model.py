"""
One-time migration: regroup data/used/*.csv from "one file per retailer"
into "one file per model" (matching the data/new/ convention).

Adds a `retail` column (Enterprise / Avis / Hertz) so which retailer sold
the vehicle is still recorded on each row after the regroup.

Reads:
  data/used/enterprise_car_sales.csv
  data/used/avis_car_sales.csv
  data/used/hertz_rent2buy.csv

Writes one CSV per make+model into data/used/, e.g. toyota_corolla.csv,
toyota_camry.csv, honda_cr-v.csv, etc. Does not delete the source files.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
USED_DIR = ROOT / "data" / "used"

SOURCE_FILES = {
    "enterprise_car_sales.csv": "Enterprise",
    "avis_car_sales.csv": "Avis",
    "hertz_rent2buy.csv": "Hertz",
}

COLUMN_ORDER = [
    "vehicle_id", "make", "model", "trim", "drivetrain", "powertrain",
    "year", "condition", "status", "mileage", "price",
    "doc_fee_included", "dealer_adjustment_included", "comparable_key",
    "source", "date_collected", "retail", "notes",
]


def sanitize(name: str) -> str:
    return name.lower().replace(" ", "_")


def main():
    frames = []
    for filename, retail in SOURCE_FILES.items():
        path = USED_DIR / filename
        df = pd.read_csv(path)
        df["retail"] = retail
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[COLUMN_ORDER]

    for (make, model), group in combined.groupby(["make", "model"], sort=True):
        filename = f"{sanitize(make)}_{sanitize(model)}.csv"
        group.to_csv(USED_DIR / filename, index=False)
        print(f"Wrote {len(group)} rows to data/used/{filename}")


if __name__ == "__main__":
    main()
