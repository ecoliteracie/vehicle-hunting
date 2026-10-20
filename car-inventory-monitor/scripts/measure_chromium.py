"""Hold a headless Chromium process open for an external memory measurement."""
import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        print("Chromium started; measuring window is 30 seconds.", flush=True)
        await asyncio.sleep(30)
        await browser.close()


asyncio.run(main())
