#!/usr/bin/env bash
set -e

# 启动 Xvfb 虚拟显示（用于可视化人工接管，文档第 57 节）
if [ "$HEADLESS" = "false" ]; then
  echo "Starting Xvfb on :99 (supervised)"
  # Xvfb 崩溃（如 OOM 被杀）后自动重启；残留锁文件会让重启报
  # "Server is already active"，先清理再拉起
  (
    set +e
    while true; do
      rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null
      Xvfb :99 -screen 0 1280x800x24
      echo "Xvfb exited (code $?), restarting in 1s" >&2
      sleep 1
    done
  ) &
  export DISPLAY=:99
  # 等待 X 就绪：登录/发布进程依赖 DISPLAY 可用，避免抢跑
  i=0
  while [ ! -S /tmp/.X11-unix/X99 ] && [ "$i" -lt 20 ]; do
    sleep 0.5
    i=$((i + 1))
  done
  echo "Starting x11vnc (supervised)"
  # x11vnc 失败/Xvfb 重启期间短暂失联都会退出，同样自动重试
  (
    set +e
    while true; do
      x11vnc -display :99 -forever -nopw -listen 0.0.0.0 -xkb
      echo "x11vnc exited (code $?), retry in 1s" >&2
      sleep 1
    done
  ) &
else
  echo "HEADLESS=true — 浏览器无头运行（人工接管不可视，按需切换）"
fi

# 启动 noVNC（可视化接入，V1 必须），同样守护重启
echo "Starting noVNC on :6080 (supervised)"
(
  set +e
  while true; do
    websockify --web=/usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900
    echo "websockify exited (code $?), retry in 1s" >&2
    sleep 1
  done
) &

# 后台 Worker
python -c "import asyncio; from publisher.workers import run_worker_loop; asyncio.run(run_worker_loop())" &

echo "Starting API on :8000"
exec python -m uvicorn publisher.api.app:app --host 0.0.0.0 --port 8000
