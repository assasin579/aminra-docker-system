FROM qdrant/qdrant:v1.17.1

# Patch OS-level CVEs (OpenSSL, libcap, etc.) without waiting for upstream image release.
# Qdrant runs as root on Debian 13 (trixie) — apt-get upgrade is safe here.
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD bash -c '>/dev/tcp/127.0.0.1/6333' 2>/dev/null || exit 1
