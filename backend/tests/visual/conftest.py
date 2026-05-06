"""Shared fixtures for visual-regression tests.

Renders PDF via the real `PDFRenderer` (Playwright Chromium), so this
suite must run inside a container that has Chromium installed — same
image as production, which is exactly the parity we want.

CI invokes: `pytest backend/tests/visual -v`
Update baselines locally: `pytest backend/tests/visual --update-baseline`
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
import pytest_asyncio

from services.pdf_renderer import PDFRenderer

BASELINE_DIR = Path(__file__).parent / "baselines"
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "pdf_render"


def pytest_addoption(parser):
    parser.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="Replace baseline PNGs instead of asserting equality.",
    )


@pytest.fixture(scope="session")
def update_baseline(request):
    return request.config.getoption("--update-baseline")


@pytest_asyncio.fixture
async def renderer():
    """Fresh renderer per test (function-scoped).

    Session-scoped doesn't work cleanly with pytest-asyncio's per-function
    event loop (the browser process binds to the loop it was launched on).
    Cost is ~3s per test for browser launch, acceptable for a small suite.
    """
    r = PDFRenderer()
    await r.startup()
    try:
        yield r
    finally:
        await r.shutdown()


@pytest.fixture(scope="session")
def fixture_loader():
    def _load(rel: str) -> dict:
        with (FIXTURE_DIR / rel).open(encoding="utf-8") as f:
            return json.load(f)
    return _load
