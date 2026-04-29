"""Observability wiring — structured logs, Prometheus metrics, request IDs.

Usage in app.py:
    from services.observability import setup_observability
    setup_observability(app)

What this enables:
- Structured JSON logs to stdout (Loki via Promtail picks up)
- /metrics endpoint exposing per-route HTTP histogram + counter
- X-Request-ID middleware that propagates inbound or generates new
- structlog context binding so per-request log lines carry request_id,
  tenant_id, user_id (when JWT verified)

Design:
- Middleware order matters: request-id BEFORE prometheus so metrics
  labels can include request_id if extended later. CORS stays outermost.
- structlog configured ONCE at import; uvicorn workers inherit.
- Honors prefers-reduced-noise: log level via LOG_LEVEL env (default INFO).
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

import structlog
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ── Context vars (per-request, bound by middleware) ─────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


def _add_context(_, __, event_dict: dict) -> dict:
    """structlog processor: inject context vars into every log line."""
    rid = request_id_var.get()
    tid = tenant_id_var.get()
    uid = user_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    if tid:
        event_dict["tenant_id"] = tid
    if uid:
        event_dict["user_id"] = uid
    return event_dict


def _configure_structlog() -> None:
    """Configure structlog with JSON output for Loki ingestion.

    Stdlib `logging` is also routed through structlog so library log lines
    (uvicorn, asyncpg, httpx) end up in the same JSON stream.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_context,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors + [structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level, logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog formatter for uniform output
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # Quiet noisy libraries (still respect LOG_LEVEL for app loggers)
    for noisy in ("uvicorn.access", "httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Prometheus metrics ──────────────────────────────────────────────────────
HTTP_REQUESTS = Counter(
    "aminra_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "aminra_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Accept inbound X-Request-ID or mint a new uuid4. Bind to context.

    Echoes the ID back as a response header so clients can correlate
    across hops. Always sets the var even on exception paths.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token_rid = request_id_var.set(rid)
        request.state.request_id = rid
        try:
            response: Response = await call_next(request)
        finally:
            # Reset is best-effort; in a real ASGI stack each task has its own
            # ContextVar copy, but explicit reset prevents bleed in tests.
            try:
                request_id_var.reset(token_rid)
            except ValueError:
                pass
        response.headers["x-request-id"] = rid
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record HTTP method, route template, status, and duration.

    Uses route template (e.g. /api/audits/{vid}) where available so
    cardinality stays bounded. Falls back to raw path for static files.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        method = request.method
        # Compute route AFTER call_next so route resolution has run.
        try:
            response: Response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            HTTP_REQUESTS.labels(method=method, route="<exception>", status=status).inc()
            raise
        # Prefer matched route template (low cardinality)
        route_obj = request.scope.get("route")
        route = getattr(route_obj, "path", None) or request.url.path
        elapsed = time.perf_counter() - start
        HTTP_REQUESTS.labels(method=method, route=route, status=status).inc()
        HTTP_LATENCY.labels(method=method, route=route).observe(elapsed)
        return response


def setup_observability(app: FastAPI) -> None:
    """Wire structlog + middleware + /metrics into the FastAPI app.

    Call once during startup, after CORS and other top-level middleware.
    Order: outermost → innermost = CORS → RequestID → Metrics → routes.
    Add in REVERSE order (FastAPI middleware stack is LIFO).
    """
    _configure_structlog()
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def bind_user_context(*, user_id: str | None = None, tenant_id: str | None = None) -> None:
    """Call from auth middleware/dependency once JWT is verified.

    Subsequent log lines in the same request carry these IDs.
    """
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)


__all__ = [
    "setup_observability",
    "bind_user_context",
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
    "HTTP_REQUESTS",
    "HTTP_LATENCY",
]
