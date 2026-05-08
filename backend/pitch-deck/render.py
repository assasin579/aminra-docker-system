"""
AMINRA Pitch Deck — standalone Playwright renderer.

Loads slides.html → emits aminra-pitch-deck.pdf (1280×720 per page, 16:9).
Reuses AMINRA design tokens via slides.css; Inter fonts served from
templates_html/_shared/fonts via relative URL.

Run:
    cd backend/pitch-deck
    python render.py

Output:
    ./aminra-pitch-deck.pdf
    ~/Downloads/aminra-pitch-deck.pdf  (copy)
"""
import asyncio
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
SLIDES_HTML = HERE / "slides.html"
PDF_LOCAL = HERE / "aminra-pitch-deck.pdf"
PDF_DOWNLOADS = Path.home() / "Downloads" / "aminra-pitch-deck.pdf"

# 16:9 landscape — 1280×720 logical px
PAGE_WIDTH_PX = 1280
PAGE_HEIGHT_PX = 720


async def render() -> None:
    if not SLIDES_HTML.exists():
        sys.exit(f"slides.html not found at {SLIDES_HTML}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": PAGE_WIDTH_PX, "height": PAGE_HEIGHT_PX},
                device_scale_factor=2,  # crisp text + SVG
            )
            page = await context.new_page()

            # Forward console errors so font/CSS issues surface
            page.on("pageerror", lambda exc: print(f"[pageerror] {exc}", file=sys.stderr))
            page.on(
                "console",
                lambda msg: (
                    print(f"[console.{msg.type}] {msg.text}", file=sys.stderr)
                    if msg.type in ("error", "warning")
                    else None
                ),
            )

            await page.goto(SLIDES_HTML.as_uri(), wait_until="networkidle")
            # Ensure web fonts are fully loaded before rendering
            await page.evaluate("() => document.fonts.ready")

            await page.pdf(
                path=str(PDF_LOCAL),
                width=f"{PAGE_WIDTH_PX}px",
                height=f"{PAGE_HEIGHT_PX}px",
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            await browser.close()

    size_kb = PDF_LOCAL.stat().st_size // 1024
    print(f"✓ rendered  {PDF_LOCAL}  ({size_kb} KB)")

    PDF_DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PDF_LOCAL, PDF_DOWNLOADS)
    print(f"✓ copied to {PDF_DOWNLOADS}")


if __name__ == "__main__":
    asyncio.run(render())
