FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HEADLESS=true

# 系统依赖：Xvfb（虚拟显示）+ 浏览器运行库 + 中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# 安装 Playwright Chromium
RUN python -m playwright install --with-deps chromium

# 运行目录
RUN mkdir -p /data /uploads /logs
ENV PUBLISHER_DATA_DIR=/data \
    PUBLISHER_UPLOADS_DIR=/uploads \
    PUBLISHER_LOGS_DIR=/logs \
    PUBLISHER_DATABASE_URL=sqlite:////data/publisher.db

EXPOSE 8000 6080

# 启动脚本：同时拉起 Xvfb + noVNC + Web
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]