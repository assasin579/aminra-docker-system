"""Tiny Prometheus exporter for per-container Docker memory stats.

Replaces cAdvisor for this host because Docker 28+ `overlayfs` storage driver
breaks cAdvisor's layerdb lookup, so it cannot populate the `name=` label
required for container-name-filtered alert rules.

Reads via Docker socket (/var/run/docker.sock). Polls every 30s and exposes
`/metrics` on :9417. One metric family per dimension; container name is the
only label (image, id deliberately omitted — keep cardinality low).
"""

from __future__ import annotations

import os
import time

import docker
from prometheus_client import Gauge, start_http_server

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "9417"))

mem_usage = Gauge(
    "docker_container_memory_usage_bytes",
    "Container memory usage (working set ≈ usage − inactive_file).",
    ["name"],
)
mem_limit = Gauge(
    "docker_container_memory_limit_bytes",
    "Container memory hard limit; 0 if unconstrained.",
    ["name"],
)
mem_pct = Gauge(
    "docker_container_memory_usage_pct",
    "Memory usage as fraction of limit (0.0–1.0). 0 if unconstrained.",
    ["name"],
)


def collect_once(client: docker.DockerClient) -> None:
    seen: set[str] = set()
    for c in client.containers.list():
        try:
            s = c.stats(stream=False)
        except Exception:
            continue
        m = s.get("memory_stats") or {}
        usage = int(m.get("usage") or 0)
        inactive = int((m.get("stats") or {}).get("inactive_file") or 0)
        working = max(usage - inactive, 0)
        limit = int(m.get("limit") or 0)
        name = c.name
        seen.add(name)
        mem_usage.labels(name=name).set(working)
        mem_limit.labels(name=name).set(limit)
        mem_pct.labels(name=name).set(working / limit if limit > 0 else 0.0)
    # Drop series for containers that disappeared so stale labels don't linger.
    for g in (mem_usage, mem_limit, mem_pct):
        for sample in list(g._metrics.keys()):
            (name,) = sample
            if name not in seen:
                g.remove(name)


def main() -> None:
    client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
    start_http_server(LISTEN_PORT)
    while True:
        try:
            collect_once(client)
        except Exception as e:
            print(f"collect_once failed: {e}", flush=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
