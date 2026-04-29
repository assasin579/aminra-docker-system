FROM qdrant/qdrant:v1.17.1

# Copy custom configuration if needed
# COPY config.yaml /qdrant/config/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD bash -c '>/dev/tcp/127.0.0.1/6333' 2>/dev/null || exit 1
