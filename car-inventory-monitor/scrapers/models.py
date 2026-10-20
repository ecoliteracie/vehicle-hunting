from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Listing:
    site: str
    vehicle: str | None
    listed_price: int | None
    mileage: int | None
    vin: str | None = None
    detail_url: str | None = None
    dealership_location: str | None = None
    availability_status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceResult:
    source_key: str
    site: str
    collected_at: str
    status: str
    listings: list[Listing]
    error: str | None = None
    diagnostics_path: str | None = None
