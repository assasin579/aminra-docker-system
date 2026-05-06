"""Visual regression: render each doc_type, diff against baseline PNG.

Solo-founder governance: this is the second-pair-of-eyes that catches
unintended visual drift. Updates require explicit `--update-baseline`
flag, so an accidental edit of `_base/base.css` will fail CI loudly
instead of silently degrading 13 templates.

Tolerance: 0.5% pixel diff (DIFF_THRESHOLD). Adjust if Chromium's font
hinting changes deterministic-enough between versions; do NOT raise it
to mask real drift.
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz                                                # pymupdf
import pytest
from PIL import Image, ImageChops

from .conftest import BASELINE_DIR

DIFF_THRESHOLD = 0.005           # 0.5%
PAGE_WIDTH_PX = 1240             # 150 dpi A4 ≈ 1240 × 1754 px

# (doc_type, fixture relative path under tests/fixtures/pdf_render/)
CASES = [
    ("_style_guide",   "_style_guide/sample.json"),
    ("company_profile", "company_profile/sample.json"),
]


def _pdf_to_pages_png(pdf_bytes: bytes) -> list[bytes]:
    """Rasterize a PDF byte buffer page-by-page to PNG bytes (150 dpi)."""
    out: list[bytes] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=150, alpha=False)
            out.append(pix.tobytes("png"))
    return out


def _pixel_diff_ratio(png_a: bytes, png_b: bytes) -> float:
    """Return fraction of non-zero pixels in the difference image (0..1)."""
    img_a = Image.open(io.BytesIO(png_a)).convert("RGB")
    img_b = Image.open(io.BytesIO(png_b)).convert("RGB")
    if img_a.size != img_b.size:
        return 1.0  # complete mismatch
    diff = ImageChops.difference(img_a, img_b)
    bbox = diff.getbbox()
    if bbox is None:
        return 0.0
    # Count pixels with any channel > 4 (Chromium font sub-pixel jitter is ≤3)
    pixels = diff.load()
    w, h = diff.size
    changed = 0
    threshold = 4
    for y in range(h):
        for x in range(w):
            p = pixels[x, y]
            if p[0] > threshold or p[1] > threshold or p[2] > threshold:
                changed += 1
    return changed / (w * h)


@pytest.mark.asyncio
@pytest.mark.parametrize("doc_type,fixture_path", CASES, ids=[c[0] for c in CASES])
async def test_pdf_visual_baseline(
    renderer, fixture_loader, update_baseline, doc_type, fixture_path,
):
    """Render and compare every page to its committed baseline.

    Fail modes:
    - Baseline missing → write it (only if --update-baseline) else fail.
    - Page count drift → fail (template grew/shrunk pages).
    - Per-page pixel diff > DIFF_THRESHOLD → fail.
    """
    fixture = fixture_loader(fixture_path)
    pdf_bytes = await renderer.render(
        doc_type=doc_type, data=fixture, cfg={},
        title=f"Baseline {doc_type}", is_draft=False,
    )

    new_pages = _pdf_to_pages_png(pdf_bytes)

    base_dir = BASELINE_DIR / doc_type
    base_dir.mkdir(parents=True, exist_ok=True)

    if update_baseline:
        # Write all pages, removing stale ones from previous version
        for old in base_dir.glob("page-*.png"):
            old.unlink()
        for i, png in enumerate(new_pages, start=1):
            (base_dir / f"page-{i:02d}.png").write_bytes(png)
        pytest.skip(f"baseline updated for {doc_type} ({len(new_pages)} pages)")
        return

    baseline_files = sorted(base_dir.glob("page-*.png"))
    if not baseline_files:
        pytest.fail(
            f"no baseline for {doc_type} — run with --update-baseline "
            f"after a manual visual review."
        )

    assert len(new_pages) == len(baseline_files), (
        f"{doc_type}: page count drift "
        f"(rendered={len(new_pages)}, baseline={len(baseline_files)}). "
        f"If intentional, run with --update-baseline."
    )

    for i, (new_png, base_path) in enumerate(zip(new_pages, baseline_files), start=1):
        base_png = base_path.read_bytes()
        diff = _pixel_diff_ratio(new_png, base_png)
        assert diff < DIFF_THRESHOLD, (
            f"{doc_type} page {i}: visual drift {diff:.3%} "
            f"(threshold {DIFF_THRESHOLD:.1%}). "
            f"Inspect {base_path}; if intentional, run with --update-baseline."
        )
