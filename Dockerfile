# Google Reviews Scraper Pro, with Chromium and its driver included.
# Build:  docker build -t google-reviews-scraper-pro .
# Run:    mkdir -p data && docker run --rm --shm-size=1g -v "$PWD/data:/data" google-reviews-scraper-pro --url "<maps url>"
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CHROME_BIN=/usr/bin/chromium

# Debian's Chromium ships for amd64 and arm64, with a driver of the same version.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY start.py api_server.py config.sample.yaml ./
COPY modules ./modules
COPY docker ./docker

# Run as a normal user (ID 1000), and keep working under any other ID passed
# with `docker run --user`, so files in a mounted folder can belong to whoever
# runs the container. For that, three folders must be writable by everyone:
# /data, the home folder (Chromium's cache) and SeleniumBase's driver folder,
# where it keeps its patched copy of the driver.
ENV HOME=/home/scraper
RUN useradd --create-home --uid 1000 scraper \
    && mkdir /data \
    && chmod -R a+rwX /data /home/scraper \
        "$(python -c 'import os, seleniumbase; print(os.path.join(os.path.dirname(seleniumbase.__file__), "drivers"))')"
USER scraper

# config.yaml is read from /data, and the database, images, logs and exports are written there.
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8000

ENTRYPOINT ["python", "/app/start.py"]
