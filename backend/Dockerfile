ARG BACKEND_BASE_IMAGE=aminra-backend-base:local
FROM ${BACKEND_BASE_IMAGE}

WORKDIR /app

# Copy only app/runtime source on top of the heavyweight base. Keep this list
# explicit so deploy builds are deterministic and do not ingest host caches,
# venvs, docs/qa output, or other generated artifacts.
COPY pipeline/ ./pipeline/
COPY auth/ ./auth/
COPY services/ ./services/
COPY contracts/ ./contracts/
COPY templates/ ./templates/
COPY templates_docx/ ./templates_docx/
COPY templates_html/ ./templates_html/
COPY supply_chain/ ./supply_chain/
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app.py .
COPY pytest.ini .
COPY tests/ ./tests/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/docs /app/data /app/doc_text_cache

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "gunicorn app:app \
    --workers ${WEB_CONCURRENCY:-2} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout ${WORKER_TIMEOUT:-240} \
    --max-requests ${MAX_REQUESTS:-1000} \
    --max-requests-jitter ${MAX_REQUESTS_JITTER:-100}"]
