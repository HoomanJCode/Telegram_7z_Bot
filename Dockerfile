# Telegram 7z Bot - Docker image
FROM python:3.11-slim

WORKDIR /app

# System dependencies: p7zip-full for archives, aria2 for multi-connection downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
    p7zip-full \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Persistent data directory (hosted files + passwords)
RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "bot.py"]