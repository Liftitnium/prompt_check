# syntax=docker/dockerfile:1
# Built from this folder: docker build -t promptcheck-evals services/evals
FROM python:3.14.10-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /srv

# unprivileged user; the service never needs root at runtime
RUN useradd --create-home --uid 10001 appuser

# dependencies before code: editing a source file does not reinstall packages
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# only what the service needs to run: no tests, no dev tools, no .env
COPY app/ ./app/
COPY migrations/ ./migrations/

# the commit this image was built from, reported by GET /health
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=3)" || exit 1

CMD ["python", "-m", "app"]
