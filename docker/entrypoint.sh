#!/usr/bin/env bash
set -e

# 启动 Xvfb 虚拟显示（用于可视化人工接管，文档第 57 节）
if [ "$HEADLESS" = "false" ]; then
  echo "Starting Xvfb on :99"
  Xvfb :99 -screen 0 1280x800x24 &
  export DISPLAY=:99
  echo "Starting x11vnc"
  # Xvfb 就绪需要一小段时间：x11vnc 抢跑会因打不开 :99 退出，
  # 用重试循环兜底，直到成功挂上 VNC 服务（否则 noVNC 永远"已断开连接"）
  (
    while true; do
      x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -xkb && break
      echo "x11vnc not ready (Xvfb starting?), retry in 0.5s"
      sleep 0.5
    done
  ) &
else
  echo "HEADLESS=true — 浏览器无头运行（人工接管不可视，按需切换）"
fi

# 启动 noVNC（可视化接入，V1 必须）
echo "Starting noVNC on :6080"
websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 &

# 后台 Worker
python -c "import asyncio; from publisher.workers import run_worker_loop; asyncio.run(run_worker_loop())" &

echo "Starting API on :8000"
exec python -m uvicorn publisher.api.app:app --host 0.0.0.0 --port 8000