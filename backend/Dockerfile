# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    libmagic1 \
    libreoffice-writer-nogui && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only torch first to avoid pulling CUDA (~8GB)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

# Python deps
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Pre-download correct embedding model (intfloat/multilingual-e5-base, 768-dim)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('intfloat/multilingual-e5-base')"

# Copy source
COPY pipeline/ ./pipeline/
COPY auth/ ./auth/
COPY templates_docx/ ./templates_docx/
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/docs /app/data /app/doc_text_cache

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "app:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "240"]
