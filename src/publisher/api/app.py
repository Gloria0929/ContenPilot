"""FastAPI 应用与路由。

- API 统一挂载在 /api 前缀下（前端 axios baseURL=/api，开发模式经 Vite 代理原样转发）
- 若存在 web/dist（前端构建产物），托管静态资源并做 SPA 路由回退
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..database import init_db
from . import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Content Publisher", version="2.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")  # 前端 baseURL=/api，生产/开发统一前缀

# ---- 前端静态托管（web/dist 存在时生效）----

_web_dist = Path.cwd() / "web" / "dist"
if (_web_dist / "index.html").is_file():
    _assets_dir = _web_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # 命中 dist 内的静态文件（favicon 等）直接返回，其余回退到 SPA 入口
        file = (_web_dist / full_path).resolve()
        if (
            full_path
            and file.is_file()
            and str(file).startswith(str(_web_dist.resolve()))
        ):
            return FileResponse(file)
        # SPA 入口禁缓存：资源文件名自带 hash 可长缓存，但入口必须
        # 每次重新验证，否则浏览器缓存旧 index.html 会一直引用旧资源
        return FileResponse(
            _web_dist / "index.html",
            headers={"Cache-Control": "no-cache"},
        )
