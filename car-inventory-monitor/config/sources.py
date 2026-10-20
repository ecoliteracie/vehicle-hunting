"""Exact dealer search URLs and non-invasive extraction hints."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str
    card_selectors: tuple[str, ...]
    load_more_selectors: tuple[str, ...] = ()
    pagination_next_selectors: tuple[str, ...] = ()
    enabled: bool = True


SOURCES = (
    Source(
        "hertz_rent2buy", "Hertz Rent2Buy",
        "https://www.hertzcarsales.com/rent2buy-inventory/index.htm?geoRadius=250&year=2024-2026&geoZip=75019&make=Toyota&make=Honda&accountCity=Dallas",
        (".vehicle-card", ".inventory-card", "article.vehicle"),
        ("button:has-text('Load More')", "a:has-text('Load More')"),
        enabled=False,
    ),
    Source(
        "hertz_bedford", "Hertz Bedford",
        "https://www.hertzcarsales.com/bedford/used-cars.htm?compositeType=certified%2C%20Rent2Buy&geoRadius=0&geoZip=75019&make=Honda&make=Toyota&accountState=TX&accountCity=Bedford&accountCity=Dallas&sortBy=internetPrice%20asc",
        (".vehicle-card", ".inventory-card", "article.vehicle"),
        ("button:has-text('Load More')", "a:has-text('Load More')"),
        enabled=False,
    ),
    Source(
        "enterprise", "Enterprise",
        "https://www.enterprisecarsales.com/search?token=N4IgZglgNgLgpgJwM4gFyjAg9gWzQBgBoQoBDGCGAVwBM40BmBgOnwEYA2NgDm+KiwA7AOaVa9VAFoAnB2YB2edzb4ArMSpJEALQgAHAMZY6aEPNX5pDEMQSkaETWgvEcpANZwAInCQGE+hRCaADaISAAKlgAnlgwpCAAuomuxnBQPn4BekGCoeEAwljYUGQ2IAWkOAjR5QAKAU7JxEgQAF4SAExsLcUwAELRAHJwpAi+MGgwCFRwAL4towgGABYRiHioICBzQA",
        ("a:has(.vehicleCardHeaderTitle)", "[data-testid*='vehicle']", ".vehicle-card", "article"),
        ("button:has-text('Load More')",),
        ("button[aria-label='Next page']",),
    ),
    Source(
        "avis", "Avis",
        "https://www.aviscarsales.com/all-inventory/index.htm?defaultRange=100&geoRadius=50&geoZip=75014&make=Toyota&sortBy=internetPrice%20asc",
        ("li.vehicle-card-detailed[data-uuid]",),
        ("button:has-text('Load More')", "a:has-text('Load More')"),
        ("button[aria-label='Next page']",),
    ),
)
