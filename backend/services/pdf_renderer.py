"""HTML/CSS → PDF renderer (Playwright Chromium + Jinja2).

Lifecycle is managed by the FastAPI `lifespan` handler in `app.py`:
    await pdf_renderer.startup()      # at app start
    await pdf_renderer.shutdown()     # at app stop

A SINGLE `Browser` is launched per backend process. Per-render isolation
is achieved by spawning a fresh `BrowserContext` for every request — this
guarantees no cookie/storage/cache bleeds across tenants (threat-model R1).

POOL_SIZE bounds the number of concurrent renders via an `asyncio.Semaphore`.
Beyond that we queue, and beyond `QUEUE_LIMIT` we 503 to shed load before
the event loop drowns.

Security posture:
  - Jinja2 SandboxedEnvironment + autoescape (R2)
  - File loader rooted at `templates_html/` — Jinja blocks `..` traversal (R4)
  - Asset helper resolves only files INSIDE the template root (R3)
  - CSP injected by the template itself; we DO NOT depend on the renderer
    to inject it because that would let a malicious template strip it
  - PDF metadata stripped → deterministic bytes (R6)
"""

from __future__ import annotations

import asyncio
import hashlib
import html as _htmlesc
import io
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import pikepdf
from jinja2 import FileSystemLoader, StrictUndefined, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from playwright.async_api import Browser, BrowserContext, async_playwright

from templates_html._registry import (
    TEMPLATES_HTML_ROOT,
    TemplateEntry,
    get_entry,
    is_known_doc_type,
)

log = logging.getLogger("aminra.pdf_renderer")

# ── Tunables (env-overridable) ──────────────────────────────────────────────

POOL_SIZE = int(os.getenv("PDF_RENDERER_POOL_SIZE", "3"))
QUEUE_LIMIT = int(os.getenv("PDF_RENDERER_QUEUE_LIMIT", "10"))
RENDER_TIMEOUT_S = float(os.getenv("PDF_RENDERER_TIMEOUT_S", "30"))
JINJA_RENDER_BUDGET_BYTES = int(os.getenv("PDF_RENDERER_HTML_LIMIT", str(5 * 1024 * 1024)))


# ── Errors ──────────────────────────────────────────────────────────────────


class TemplateNotFoundError(LookupError):
    """doc_type unknown to the registry."""


class TemplateNotImplementedError(NotImplementedError):
    """doc_type known but HTML template not yet shipped."""


class RenderTimeoutError(TimeoutError):
    pass


class RenderConcurrencyError(RuntimeError):
    pass


class RenderHTMLTooLargeError(ValueError):
    pass


# ── Renderer ────────────────────────────────────────────────────────────────


class PDFRenderer:
    """Singleton-ish: one instance attached to `app.state.pdf_renderer`."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._sema = asyncio.Semaphore(POOL_SIZE)
        self._waiting = 0
        self._waiting_lock = asyncio.Lock()

        # Jinja2 sandboxed env. autoescape kicks in for .html / .htm.
        self._jinja = SandboxedEnvironment(
            loader=FileSystemLoader(str(TEMPLATES_HTML_ROOT), followlinks=False),
            autoescape=select_autoescape(["html", "htm"]),
            undefined=StrictUndefined,        # raise on missing var (catch typos in cfg)
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Asset helper exposed to templates: resolves to file:// URI inside
        # the template root. Refuses anything that escapes the root.
        self._jinja.globals["asset"] = self._asset_uri

    # ── Lifespan ────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        if self._browser is not None:
            return
        # Headless Chromium. Sandbox stays ON in prod (`--no-sandbox` would
        # be a privilege boundary downgrade — see threat-model R2.4).
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--font-render-hinting=none",
                # Required so set_content() with file:// asset URIs can
                # fetch local stylesheets/fonts/SVGs. Renderer is otherwise
                # network-isolated (offline=True on context), so this only
                # widens FS access — bound by template root via the asset()
                # helper which rejects paths outside templates_html/.
                "--allow-file-access-from-files",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--no-first-run",
            ],
        )
        log.info("[pdf_renderer] browser launched, pool_size=%d", POOL_SIZE)

    async def shutdown(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:  # noqa: BLE001 — best-effort shutdown
                log.warning("[pdf_renderer] browser close failed: %s", exc)
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as exc:  # noqa: BLE001
                log.warning("[pdf_renderer] playwright stop failed: %s", exc)
            self._playwright = None
        log.info("[pdf_renderer] shut down")

    # ── Health snapshot for /health endpoint ────────────────────────────────

    def health(self) -> dict:
        if self._browser is None:
            return {"browser": "down", "pool_size": POOL_SIZE}
        # Semaphore exposes _value as remaining permits (idle); CPython internals,
        # acceptable for monitoring use.
        idle = self._sema._value if hasattr(self._sema, "_value") else POOL_SIZE
        return {
            "browser": "ok",
            "pool_size": POOL_SIZE,
            "contexts_idle": idle,
            "contexts_busy": POOL_SIZE - idle,
            "queue_depth": self._waiting,
            "queue_limit": QUEUE_LIMIT,
        }

    # ── Public render API ───────────────────────────────────────────────────

    async def render(
        self,
        *,
        doc_type: str,
        data: dict,
        cfg: dict,
        title: str,
        is_draft: bool = True,
        content: str = "",
        lang: str = "vi",
    ) -> bytes:
        """Render a doc_type to PDF bytes. See module docstring for guarantees."""
        entry = self._resolve(doc_type)

        # Admission control before grabbing a browser context.
        async with self._waiting_lock:
            if self._waiting >= QUEUE_LIMIT:
                raise RenderConcurrencyError(
                    f"renderer queue full (waiting={self._waiting}, limit={QUEUE_LIMIT})"
                )
            self._waiting += 1
        try:
            return await asyncio.wait_for(
                self._render_locked(entry, data, cfg, title, is_draft, content, lang),
                timeout=RENDER_TIMEOUT_S,
            )
        except asyncio.TimeoutError as exc:
            raise RenderTimeoutError(
                f"PDF render exceeded {RENDER_TIMEOUT_S}s for doc_type={doc_type}"
            ) from exc
        finally:
            async with self._waiting_lock:
                self._waiting -= 1

    # ── Internal ────────────────────────────────────────────────────────────

    def _resolve(self, doc_type: str) -> TemplateEntry:
        if not is_known_doc_type(doc_type):
            raise TemplateNotFoundError(doc_type)
        entry = get_entry(doc_type)
        if entry is None:
            raise TemplateNotImplementedError(doc_type)
        return entry

    async def _render_locked(
        self,
        entry: TemplateEntry,
        data: dict,
        cfg: dict,
        title: str,
        is_draft: bool,
        content: str,
        lang: str,
    ) -> bytes:
        async with self._sema:
            t0 = time.monotonic()
            html = self._render_html(entry, data, cfg, title, is_draft, content, lang)
            t_html = time.monotonic() - t0

            if len(html.encode("utf-8")) > JINJA_RENDER_BUDGET_BYTES:
                raise RenderHTMLTooLargeError(
                    f"rendered HTML > {JINJA_RENDER_BUDGET_BYTES} bytes for "
                    f"doc_type={entry.doc_type}"
                )

            assert self._browser is not None, "renderer not started"
            context: BrowserContext = await self._browser.new_context(
                java_script_enabled=False,            # CSP also blocks; defense in depth
                bypass_csp=False,
                ignore_https_errors=False,
                offline=True,                          # no network at all
            )
            tmp_html: Optional[Path] = None
            try:
                # Write rendered HTML to a temp file INSIDE the template root
                # so the page itself loads as file:// and can fetch sibling
                # CSS/font/SVG assets without a cross-origin block.
                # `set_content` would put the page on about:blank, which the
                # browser treats as a different origin from file:// — so any
                # <link rel=stylesheet href="file://...">  silently fails.
                tmp_name = f".render-{secrets.token_hex(8)}.html"
                tmp_html = TEMPLATES_HTML_ROOT / tmp_name
                tmp_html.write_text(html, encoding="utf-8")

                page = await context.new_page()
                await page.goto(tmp_html.as_uri(), wait_until="load")
                await page.emulate_media(media="print")
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    display_header_footer=True,
                    header_template="<div></div>",       # CSS @page rules drive headers
                    footer_template=_build_footer_html(data),
                )
                await page.close()
            finally:
                await context.close()
                if tmp_html is not None and tmp_html.exists():
                    try:
                        tmp_html.unlink()
                    except OSError:
                        log.warning("[pdf_renderer] failed to unlink %s", tmp_html)

            t_render = time.monotonic() - t0 - t_html
            cleaned = _strip_pdf_metadata(pdf_bytes)
            log.info(
                "[pdf_renderer] doc_type=%s html_ms=%d render_ms=%d bytes=%d",
                entry.doc_type,
                int(t_html * 1000),
                int(t_render * 1000),
                len(cleaned),
            )
            return cleaned

    def _render_html(
        self,
        entry: TemplateEntry,
        data: dict,
        cfg: dict,
        title: str,
        is_draft: bool,
        content: str,
        lang: str,
    ) -> str:
        template = self._jinja.get_template(entry.template_relpath)
        # StrictUndefined catches `data.{typo}` in templates — but cfg JSON is
        # sparse by design (admin only sets the keys they care about). Pre-fill
        # cfg with sentinel defaults so cfg.* access never raises Undefined.
        cfg_filled = {
            "confidential_label": None,
            "doc_type_label": None,
            "cover_meta": None,
            "custom_sections": None,
            "show_approval_block": True,
            **(cfg or {}),
        }
        return template.render(
            title=title,
            data=data,
            cfg=cfg_filled,
            content=content,
            is_draft=is_draft,
            lang=lang,
        )

    # ── Asset URI helper (whitelist FS access) ──────────────────────────────

    def _asset_uri(self, relpath: str) -> str:
        """Resolve a template-relative asset path to a file:// URI.

        Refuses any path that escapes TEMPLATES_HTML_ROOT — defends against
        a designer accidentally writing `{{ asset('../../etc/passwd') }}`
        (or worse, `{{ asset(some_user_field) }}` which would be a SSRF
        primitive — but `data` is escaped so it can't even reach here).
        """
        resolved = (TEMPLATES_HTML_ROOT / relpath).resolve()
        try:
            resolved.relative_to(TEMPLATES_HTML_ROOT.resolve())
        except ValueError as exc:
            raise ValueError(f"asset path outside template root: {relpath}") from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"asset not found: {relpath}")
        return resolved.as_uri()


# ── Running footer (brand on every page) ───────────────────────────────────


def _build_footer_html(data: dict) -> str:
    """Build the Chromium native print footer with brand + doc_id + page number.

    Chromium's `footer_template` is a fragment-of-HTML strung that's injected
    on every page. It supports the special spans `pageNumber`, `totalPages`,
    `title`, `date` — but not Jinja, so we string-format the dynamic bits
    here. All `data` values are HTML-escaped to defend against an attacker
    who somehow lands user-controlled content into a name field.
    """
    business_name = (data.get("business_name") or "").strip()
    # Document ID falls back across schemas: SOP, policy, manual all expose
    # one of these keys per their Pydantic shape.
    doc_id = (
        data.get("sop_id")
        or data.get("policy_id")
        or data.get("manual_id")
        or ""
    ).strip()

    left = _htmlesc.escape(business_name)
    if doc_id:
        left += " &middot; " + _htmlesc.escape(doc_id)

    return (
        "<div style=\""
        "width:100%;font-size:7pt;color:#94a3b8;"
        "padding:0 15mm;font-family:Inter,sans-serif;"
        "display:flex;justify-content:space-between;align-items:center;"
        "letter-spacing:0.04em;"
        "\">"
        f"<span style=\"font-weight:600;\">{left}</span>"
        "<span>Trang <span class=\"pageNumber\"></span> / "
        "<span class=\"totalPages\"></span></span>"
        "</div>"
    )


# ── PDF metadata strip (deterministic output) ───────────────────────────────


def _strip_pdf_metadata(pdf_bytes: bytes) -> bytes:
    """Replace timestamp + producer fields with constants.

    Without this, every render embeds `CreationDate D:20260505...` and
    `Producer Chrome/<version>` which (a) leaks Chromium version and
    (b) breaks byte-level idempotency for cache hashes.
    """
    out = io.BytesIO()
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        with pdf.open_metadata() as meta:
            meta.clear()
        # docinfo dict is older legacy; clear what we can.
        if pdf.docinfo:
            for key in ("/Creator", "/Producer", "/CreationDate", "/ModDate", "/Author", "/Title", "/Subject"):
                if key in pdf.docinfo:
                    del pdf.docinfo[key]
            pdf.docinfo["/Producer"] = "AMINRA Halal Cert Platform"
            pdf.docinfo["/CreationDate"] = "D:00010101000000Z"
        pdf.save(out, deterministic_id=True)
    return out.getvalue()


# ── Convenience hash for ETag ───────────────────────────────────────────────


def etag_for(template_version: str, data_canonical: bytes) -> str:
    """Stable ETag = sha256(template_version || canonical_json(data))."""
    h = hashlib.sha256()
    h.update(template_version.encode("utf-8"))
    h.update(b"\x00")
    h.update(data_canonical)
    return f'"{h.hexdigest()}"'
