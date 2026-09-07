"""Publisher 配置加载。

配置优先级：环境变量 > .env 文件 > 默认值。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 统一数据根目录：数据库、日志、上传文件等全部落在 ~/.contentpilot/ 下。
# Docker 镜像内通过 ENV 显式覆盖为 /data 等（见 Dockerfile）。
_CONTENTPILOT_HOME = Path.home() / ".contentpilot"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PUBLISHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据目录
    data_dir: Path = _CONTENTPILOT_HOME / "data"
    uploads_dir: Path = _CONTENTPILOT_HOME / "uploads"
    logs_dir: Path = _CONTENTPILOT_HOME / "logs"

    # 数据库
    database_url: str = ""  # 留空则使用 data_dir 下的 SQLite

    # 服务监听。默认仅本机，暴露到公网前必须配置鉴权。
    host: str = "127.0.0.1"
    port: int = 8000

    # Web 登录
    admin_username: str = "admin"
    admin_password: str = "admin"  # 生产环境必须通过环境变量覆盖

    # 鉴权
    session_secret: str = "QnvlzGlE/lam7u/M7shMg27STNfMi+CQtyrpw3VUH4s="
    session_max_age: int = 60 * 60 * 24 * 7  # 7 天

    # Worker
    worker_poll_interval: float = 1.0
    max_attempts_default: int = 3

    # 超时（秒）
    waiting_auth_timeout: int = 24 * 3600
    waiting_manual_timeout: int = 24 * 3600
    review_stale_days: int = 3

    # 浏览器
    headless: bool = True
    browser_login_timeout: int = 300  # browser login 等待用户完成登录的超时（秒）

    # 风控与频率限制
    min_publish_interval_seconds: int = 300  # 默认 5 分钟
    max_consecutive_blocked: int = 3
    cooldown_seconds: int = 3600

    # 内容安全兜底检测
    content_safety_enabled: bool = True

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.data_dir}/publisher.db"

    @property
    def effective_database_url(self) -> str:
        return self.database_url or self.sqlite_url

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()