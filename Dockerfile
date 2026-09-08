# ---- 阶段一：前端构建（web/dist）----
FROM node:20-alpine AS web-builder
WORKDIR /web
# 国内网络走 npmmirror；先拷 lock 文件利用层缓存
COPY web/package.json web/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY web ./
RUN npm run build

# ---- 阶段二：后端镜像 ----
FROM python:3.12-slim

# 国内网络直连 PyPI / Playwright CDN 容易读超时：走镜像源 + 放宽超时
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HEADLESS=false \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

# 系统依赖：Xvfb（虚拟显示）+ 浏览器运行库 + 中文字体
# 官方 deb.debian.org 国内极慢，先替换为清华镜像源（trixie 为 DEB822 格式）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null || true

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
    tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# 前端构建产物（app.py 按 cwd/web/dist 探测托管）
COPY --from=web-builder /web/dist ./web/dist

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