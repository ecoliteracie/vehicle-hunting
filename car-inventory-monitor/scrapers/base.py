"""A deliberately conservative, reusable Playwright inventory collector."""
import asyncio
import re
from urllib.parse import urljoin
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError

from config.sources import Source
from .models import Listing, SourceResult

CHICAGO = ZoneInfo("America/Chicago")
PRICE_RE = re.compile(r"\$\s*([\d,]+)")
MILEAGE_RE = re.compile(r"([\d,.]+)\s*(k)?\s*(?:mi\.?|miles)\b", re.I)
VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b", re.I)


class InventoryScraper:
    def __init__(self, browser: Browser, diagnostics_dir: Path, timeout_ms: int = 30_000):
        self.browser = browser
        self.diagnostics_dir = diagnostics_dir
        self.timeout_ms = timeout_ms

    async def collect(self, source: Source, probe_only: bool = False) -> SourceResult:
        timestamp = datetime.now(CHICAGO).isoformat()
        page = await self.browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            response = await page.goto(source.url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            await page.wait_for_timeout(2_500)
            if response and response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            protection = await self._protection_message(page)
            if protection:
                raise RuntimeError(f"access restriction detected: {protection}")
            cards = await self._find_cards(page, source)
            if not cards:
                raise RuntimeError("no recognizable inventory cards; not treated as zero inventory")
            if not probe_only:
                await self._load_more(page, source)
                cards = await self._find_cards(page, source)
            await self._hydrate_cards(cards)
            listings = await self._extract_cards(cards, source, page.url)
            if not listings:
                raise RuntimeError("cards were visible but no listings could be parsed")
            if not probe_only:
                listings.extend(await self._collect_following_pages(page, source))
                listings = self._deduplicate(listings)
            return SourceResult(source.key, source.name, timestamp, "success", listings)
        except (PlaywrightTimeoutError, RuntimeError) as exc:
            diagnostic = await self._save_diagnostics(page, source.key)
            return SourceResult(source.key, source.name, timestamp, "failed", [], str(exc), diagnostic)
        finally:
            await page.close()

    async def _find_cards(self, page: Page, source: Source):
        for selector in source.card_selectors:
            locator = page.locator(selector)
            try:
                if await locator.count():
                    return locator
            except PlaywrightTimeoutError:
                continue
        return None

    async def _load_more(self, page: Page, source: Source) -> None:
        # A hard ceiling prevents accidental repeated requests when a site loops.
        for _ in range(10):
            button = None
            for selector in source.load_more_selectors:
                candidate = page.locator(selector).first
                if await candidate.count() and await candidate.is_visible():
                    button = candidate
                    break
            if not button:
                return
            await button.click()
            await page.wait_for_timeout(1_500)

    async def _hydrate_cards(self, cards) -> None:
        """Trigger the lazy media/detail content used by some dealer result cards."""
        for index in range(await cards.count()):
            await cards.nth(index).scroll_into_view_if_needed()
            await asyncio.sleep(0.35)

    async def _collect_following_pages(self, page: Page, source: Source) -> list[Listing]:
        listings: list[Listing] = []
        for _ in range(20):  # hard ceiling prevents pagination loops
            next_button = None
            for selector in source.pagination_next_selectors:
                candidate = page.locator(selector).first
                if await candidate.count() and await candidate.is_visible() and await candidate.is_enabled():
                    next_button = candidate
                    break
            if not next_button:
                return listings
            previous_url = page.url
            await next_button.click()
            await page.wait_for_timeout(1_500)
            await page.wait_for_load_state("domcontentloaded")
            cards = await self._find_cards(page, source)
            if not cards or page.url == previous_url and not await cards.count():
                return listings
            listings.extend(await self._extract_cards(cards, source, page.url))
        return listings

    @staticmethod
    def _deduplicate(listings: list[Listing]) -> list[Listing]:
        seen: set[str] = set()
        unique: list[Listing] = []
        for item in listings:
            identity = item.vin or item.detail_url or f"{item.vehicle}|{item.listed_price}|{item.mileage}"
            if identity not in seen:
                unique.append(item)
                seen.add(identity)
        return unique

    async def _extract_cards(self, cards, source: Source, page_url: str) -> list[Listing]:
        listings: list[Listing] = []
        seen: set[str] = set()
        for index in range(await cards.count()):
            card = cards.nth(index)
            text = " ".join((await card.inner_text()).split())
            if source.key == "avis":
                listing = await self._parse_avis_card(card, text, page_url)
                identity = listing.detail_url or f"{listing.vehicle}|{listing.listed_price}|{listing.mileage}"
                if identity not in seen:
                    listings.append(listing)
                    seen.add(identity)
                continue
            href = await card.get_attribute("href")
            if not href and await card.locator("a[href]").count():
                href = await card.locator("a[href]").first.get_attribute("href")
            if href:
                href = urljoin(page_url, href)
            listing = self._parse_card(source.name, text, href)
            identity = listing.vin or listing.detail_url or f"{listing.vehicle}|{listing.listed_price}|{listing.mileage}"
            if identity not in seen:
                listings.append(listing)
                seen.add(identity)
        return listings

    async def _parse_avis_card(self, card, text: str, page_url: str) -> Listing:
        title_link = card.locator(".vehicle-card-title a[href]").first
        vehicle = " ".join((await title_link.inner_text()).split()) if await title_link.count() else None
        href = await title_link.get_attribute("href") if await title_link.count() else None
        price_node = card.locator("dd.final-price.askingPrice").first
        price_text = await price_node.inner_text() if await price_node.count() else ""
        price = PRICE_RE.search(price_text)
        mileage = MILEAGE_RE.search(text)
        location = re.search(r"(Avis Car Sales [A-Za-z ]+)", text)
        return Listing(
            site="Avis", vehicle=vehicle,
            listed_price=int(price.group(1).replace(",", "")) if price else None,
            mileage=(round(float(mileage.group(1).replace(",", "")) * (1000 if mileage.group(2) else 1)) if mileage else None),
            detail_url=urljoin(page_url, href) if href else None,
            dealership_location=location.group(1) if location else None,
        )

    @staticmethod
    def _parse_card(site: str, text: str, href: str | None) -> Listing:
        price = PRICE_RE.search(text)
        mileage = MILEAGE_RE.search(text)
        vin = VIN_RE.search(text)
        # The opening words normally contain the title; retain it rather than guessing missing trim data.
        vehicle = re.split(r"\$\s*[\d,]+|\b(?:mileage|vin)\b", text, flags=re.I)[0].strip() or None
        status_match = re.match(r"^(JUST ADDED|COMING SOON|JUST SOLD|PURCHASE IN PROGRESS)\s+", vehicle or "", re.I)
        status = status_match.group(1).title() if status_match else None
        if status_match:
            vehicle = vehicle[status_match.end():]
        return Listing(
            site=site, vehicle=vehicle,
            listed_price=int(price.group(1).replace(",", "")) if price else None,
            mileage=(round(float(mileage.group(1).replace(",", "")) * (1000 if mileage.group(2) else 1)) if mileage else None),
            vin=vin.group(1).upper() if vin else None, detail_url=href, availability_status=status,
        )

    async def _protection_message(self, page: Page) -> str | None:
        text = (await page.title() + " " + await page.locator("body").inner_text()).lower()
        for phrase in ("captcha", "access denied", "unusual traffic", "verify you are human"):
            if phrase in text:
                return phrase
        return None

    async def _save_diagnostics(self, page: Page, source_key: str) -> str | None:
        try:
            self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(CHICAGO).strftime("%Y%m%dT%H%M%S")
            base = self.diagnostics_dir / f"{source_key}_{stamp}"
            await page.screenshot(path=f"{base}.png", full_page=True)
            html = await page.content()
            # No cookies/local storage are persisted; strip scripts to keep failure captures compact.
            html = re.sub(r"<script[\\s\\S]*?</script>", "", html, flags=re.I)
            (base.with_suffix(".html")).write_text(html, encoding="utf-8")
            return str(base)
        except Exception:
            return None
