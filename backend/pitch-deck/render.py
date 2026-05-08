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

# 16:9 landscape — 1920×1080 (AMINRA brand spec)
PAGE_WIDTH_PX = 1920
PAGE_HEIGHT_PX = 1080


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

            # Paper size = standard 16:9 slide (13.333"×7.5" = 960×540 pt).
            # Viewport stays 1920×1080 for design fidelity; Chromium scales the
            # rendered page to fit the smaller paper. PDF is fully vector so
            # quality is identical, but per-page area is 4× smaller — viewers
            # render & scroll much faster.
            await page.pdf(
                path=str(PDF_LOCAL),
                width="13.333in",
                height="7.5in",
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                print_background=True,
                prefer_css_page_size=False,
            )
        finally:
            await browser.close()

    raw_kb = PDF_LOCAL.stat().st_size // 1024
    print(f"✓ rendered  {PDF_LOCAL}  ({raw_kb} KB raw)")

    # Compress: pikepdf re-saves with object stream + content stream compression.
    try:
        import pikepdf
        with pikepdf.open(PDF_LOCAL, allow_overwriting_input=True) as doc:
            doc.save(
                PDF_LOCAL,
                compress_streams=True,
                stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                linearize=False,
            )
        opt_kb = PDF_LOCAL.stat().st_size // 1024
        print(f"✓ compressed {PDF_LOCAL}  ({opt_kb} KB · saved {raw_kb - opt_kb} KB)")
    except ImportError:
        print("note: pikepdf not installed — skipping compression")

    PDF_DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PDF_LOCAL, PDF_DOWNLOADS)
    print(f"✓ copied to {PDF_DOWNLOADS}")


if __name__ == "__main__":
    asyncio.run(render())
