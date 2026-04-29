"""Load test skeleton for AMINRA backend.

Run:
    locust -f backend/tests/load/locustfile.py --host http://localhost:8100

Web UI at http://localhost:8089. Headless mode:
    locust -f backend/tests/load/locustfile.py --host http://localhost:8100 \\
        --users 50 --spawn-rate 5 --run-time 2m --headless

Coverage targets (Phase 1+, expand as Tier-1 modules ship):
- /auth/login            — burst SLO: p95 < 250ms @ 50 RPS
- /auth/me               — sustained: p95 < 80ms (it's a hot path)
- /api/dashboard/stats   — p95 < 500ms (DB-heavy)
- /api/notifications/    — p95 < 100ms (frontend polls)
- /metrics               — must be < 50ms (Prometheus scrape budget)

This file ships as a SKELETON: feature teams add a UserClass per workflow.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

# Demo seed credentials. Real load runs should use a pool of seeded users
# to avoid auth-cache hot-spotting.
DEMO_EMAIL = os.getenv("LOAD_DEMO_EMAIL", "biz-demo-1@demo.aminra.vn")
DEMO_PASSWORD = os.getenv("LOAD_DEMO_PASSWORD", "DemoP@ss2026")


class BusinessUser(HttpUser):
    """Simulates a logged-in business owner browsing the dashboard."""

    wait_time = between(1, 3)
    token: str | None = None

    def on_start(self):
        """One-time login per virtual user."""
        r = self.client.post(
            "/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "role": "business"},
            name="login",
        )
        if r.status_code == 200:
            self.token = r.json().get("access_token")

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def me(self):
        self.client.get("/auth/me", headers=self._auth(), name="GET /auth/me")

    @task(3)
    def dashboard_stats(self):
        self.client.get("/api/dashboard/stats", headers=self._auth(), name="GET /api/dashboard/stats")

    @task(3)
    def notifications(self):
        self.client.get(
            "/api/notifications/?limit=20",
            headers=self._auth(),
            name="GET /api/notifications/",
        )

    @task(1)
    def cert_timeline(self):
        self.client.get(
            "/api/submissions/cert-timeline",
            headers=self._auth(),
            name="GET /api/submissions/cert-timeline",
        )


class MetricsScraper(HttpUser):
    """Models Prometheus scrape pressure on /metrics."""

    wait_time = between(15, 15)  # match scrape_interval

    @task
    def metrics(self):
        self.client.get("/metrics", name="GET /metrics")
