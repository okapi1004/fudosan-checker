#!/bin/bash
# VPSセットアップスクリプト
# コンソールのテキスト送信で実行

cd /opt/fudosan-checker

# ディレクトリ構成
mkdir -p scrapers notifiers db data

# requirements.txt
cat > requirements.txt << 'REQEOF'
playwright==1.49.1
beautifulsoup4==4.12.3
lxml==5.3.0
requests==2.32.3
pyyaml==6.0.2
apscheduler==3.10.4
python-dotenv==1.0.1
REQEOF

# Dockerfile
cat > Dockerfile << 'DKEOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . .

CMD ["python", "main.py", "--daemon"]
DKEOF

# docker-compose.yml
cat > docker-compose.yml << 'DCEOF'
services:
  fudosan-checker:
    build: .
    container_name: fudosan-checker
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./data:/app/data
    environment:
      - TZ=Asia/Tokyo
DCEOF

# __init__.py files
touch scrapers/__init__.py notifiers/__init__.py db/__init__.py

echo "基本ファイル作成完了"
