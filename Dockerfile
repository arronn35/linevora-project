FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV LINEVORA_ENV=prod LINEVORA_DB_PATH=/data/linevora.db LINEVORA_BLOB_DIR=/data/blobs
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health')"
CMD ["python", "-m", "uvicorn", "linevora.main:app", "--host", "0.0.0.0", "--port", "8000"]
