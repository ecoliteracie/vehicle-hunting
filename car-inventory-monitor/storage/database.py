import sqlite3
from pathlib import Path

from scrapers.models import SourceResult


class InventoryDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, collected_at TEXT NOT NULL, source_key TEXT NOT NULL, status TEXT NOT NULL, error TEXT);
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id), identity TEXT NOT NULL,
                site TEXT NOT NULL, vehicle TEXT, listed_price INTEGER, mileage INTEGER, vin TEXT,
                detail_url TEXT, dealership_location TEXT, availability_status TEXT);
            CREATE INDEX IF NOT EXISTS observations_identity ON observations(identity);
            CREATE TABLE IF NOT EXISTS listing_state (
                source_key TEXT NOT NULL, identity TEXT NOT NULL, first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL, active INTEGER NOT NULL, listed_price INTEGER,
                mileage INTEGER, PRIMARY KEY(source_key, identity));
        """)

    def save(self, result: SourceResult) -> dict[str, int]:
        cur = self.connection.execute(
            "INSERT INTO runs(collected_at, source_key, status, error) VALUES (?, ?, ?, ?)",
            (result.collected_at, result.source_key, result.status, result.error),
        )
        changes = {"new": 0, "removed": 0, "price_reductions": 0, "price_increases": 0, "mileage_changes": 0}
        if result.status == "success":
            previous = {row[0]: row[1:] for row in self.connection.execute(
                "SELECT identity, listed_price, mileage FROM listing_state WHERE source_key = ? AND active = 1", (result.source_key,)
            )}
            current: set[str] = set()
            for item in result.listings:
                identity = item.vin or item.detail_url or f"{item.vehicle}|{item.listed_price}|{item.mileage}"
                current.add(identity)
                self.connection.execute(
                    "INSERT INTO observations(run_id, identity, site, vehicle, listed_price, mileage, vin, detail_url, dealership_location, availability_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cur.lastrowid, identity, item.site, item.vehicle, item.listed_price, item.mileage, item.vin, item.detail_url, item.dealership_location, item.availability_status),
                )
                old = previous.get(identity)
                if old is None:
                    changes["new"] += 1
                    self.connection.execute(
                        "INSERT INTO listing_state(source_key, identity, first_seen, last_seen, active, listed_price, mileage) VALUES (?, ?, ?, ?, 1, ?, ?)",
                        (result.source_key, identity, result.collected_at, result.collected_at, item.listed_price, item.mileage),
                    )
                else:
                    old_price, old_mileage = old
                    if old_price is not None and item.listed_price is not None:
                        if item.listed_price < old_price:
                            changes["price_reductions"] += 1
                        elif item.listed_price > old_price:
                            changes["price_increases"] += 1
                    if old_mileage is not None and item.mileage is not None and item.mileage != old_mileage:
                        changes["mileage_changes"] += 1
                    self.connection.execute(
                        "UPDATE listing_state SET last_seen = ?, active = 1, listed_price = ?, mileage = ? WHERE source_key = ? AND identity = ?",
                        (result.collected_at, item.listed_price, item.mileage, result.source_key, identity),
                    )
            removed = set(previous) - current
            changes["removed"] = len(removed)
            for identity in removed:
                self.connection.execute("UPDATE listing_state SET active = 0 WHERE source_key = ? AND identity = ?", (result.source_key, identity))
        self.connection.commit()
        return changes

    def close(self) -> None:
        self.connection.close()
