# Telegram 7z Bot - Docker image
# Alpine base keeps the image ~2x smaller than python:3.11-slim.
# Alpine's 7zip package provides /usr/bin/7z (symlink to 7zz) which the bot calls,
# and all Python dependencies ship musllinux / pure-Python wheels.
FROM python:3.11-alpine

WORKDIR /app

# System dependencies: 7zip for archives, aria2 for multi-connection downloads
RUN apk add --no-cache \
    7zip \
    aria2

# Python dependencies
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code
COPY . .

# Persistent data directory (hosted files + passwords)
RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "bot.py"]