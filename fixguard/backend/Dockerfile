# Playwright's own image ships Chromium plus every system library it needs.
# Building on python:slim instead means hand-maintaining ~40 apt packages.
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FIXGUARD_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data && chown -R pwuser:pwuser /data /app
USER pwuser

# No EXPOSE. It publishes nothing and is not needed for the web container
# to reach this one - containers on a shared network resolve each other
# by name - but Coolify reads it as "this service is web-facing" and
# gives the api its own public hostname, which routes around nginx and
# therefore around the rate limiting and real-client-address resolution.
# The port the app listens on is stated by the CMD below.

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"

# Single worker: one browser at a time is all a 1 vCPU box can serve honestly.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
