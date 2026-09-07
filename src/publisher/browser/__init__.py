"""浏览器自动化层（Playwright）。

文档对应：
- §23 浏览器自动化：加载 storage_state、登录检查、内容填写、发布、成功确认、截图/Trace
- §24 浏览器登录：run_browser_login 打开可见浏览器保存登录态
- §25 人工接管：验证码/风控 → needs_manual（本机显示窗口 / 容器经 noVNC 操作）
- §26 发布成功判断：无法确认 → unconfirmed，由 Worker 置为 blocked 防止重复发布

Playwright 代码只存在于本层与 browser/scripts/（§73-3），平台 selector 不进 Core。
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..platforms.base import PublishResult


class LoginError(Exception):
    """浏览器登录流程失败。"""


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))


def diagnostics_dir() -> Path:
    """诊断信息目录（截图 / Trace），位于 logs 下（§56 Volume 约定）。"""
    d = Path(settings.logs_dir) / "diagnostics"
    d.mkdir(parents=True, exist_ok=True)
    return d


def storage_state_path(platform: str, account_key: str) -> Path:
    """某账号在某平台的登录态文件路径（§24 storage_state）。"""
    return (
        Path(settings.data_dir)
        / "browser"
        / _safe_name(platform)
        / f"{_safe_name(account_key)}.json"
    )


def detect_manual_intervention(content: str, extra_keywords=()) -> str | None:
    """通用人工接管特征检测（§25）。返回命中的关键词或 None。"""
    keywords = [
        "验证码", "captcha", "verify", "滑块", "风险", "risk", "手机验证", "安全验证",
        *extra_keywords,
    ]
    for kw in keywords:
        if kw and kw in content:
            return kw
    return None


def _blog(event: str, task_id: int | None, level: str = "info", message: str = "") -> None:
    """浏览器过程日志（§51：browser_started/login_checked/...）。

    独立短事务写入，失败静默 —— 过程日志不能影响发布主流程。
    """
    try:
        from ..database import SessionLocal
        from ..services.log_service import LogService

        s = SessionLocal()
        try:
            LogService(s).log(event, task_id=task_id, level=level, message=message)
        finally:
            s.close()
    except Exception:
        pass


async def _screenshot(page, name: str) -> str | None:
    """保存诊断截图，失败不影响主流程。"""
    try:
        path = diagnostics_dir() / f"{_safe_name(name)}_{_ts()}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None


class BrowserWorker:
    """一次浏览器任务专用的 Playwright 实例。

    V1 采用「一任务一浏览器」：任务结束即释放，天然满足同账号浏览器互斥（§50）。
    """

    def __init__(self, headless: bool | None = None):
        self._headless = settings.headless if headless is None else headless
        self._pw = None
        self._browser = None
        self._context = None
        self._tracing = False

    async def start(self, storage_state: str | None = None):
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        # 反自动化检测：禁用 AutomationControlled 特征（navigator.webdriver 等），
        # 降低 CSDN 等风控严格平台登录/发布时的验证失败率
        self._browser = await self._pw.chromium.launch(
            headless=self._headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        kwargs: dict = {"viewport": {"width": 1440, "height": 900}, "locale": "zh-CN"}
        if storage_state:
            kwargs["storage_state"] = storage_state
        self._context = await self._browser.new_context(**kwargs)
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return self._context

    async def start_tracing(self) -> None:
        """开启 Trace，任务失败时保留诊断文件（§23、§75-20）。"""
        try:
            await self._context.tracing.start(screenshots=True, snapshots=True)
            self._tracing = True
        except Exception:
            self._tracing = False

    async def stop_tracing(self, save: bool, name: str) -> None:
        if not self._tracing:
            return
        self._tracing = False
        try:
            if save:
                path = diagnostics_dir() / f"{_safe_name(name)}_trace_{_ts()}.zip"
                await self._context.tracing.stop(path=str(path))
            else:
                await self._context.tracing.stop()
        except Exception:
            pass

    async def stop(self) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    await closer.close()
            except Exception:
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._context = self._browser = self._pw = None


async def run_browser_publish(
    platform: str,
    version,
    account=None,
    task_id: int | None = None,
    mode: str = "publish",
) -> PublishResult:
    """浏览器平台发布入口（由平台 Adapter 调用）。

    结果语义：
    - success + remote_id/remote_url：已确认发布成功（§26）
    - needs_auth：登录态缺失/失效（§24）
    - needs_manual：验证码/风控，等待人工接管（§25）
    - unconfirmed：已点击发布但无法确认结果 → Worker 置为 blocked（§26，防重复发布）
    - 其余：可自动重试的普通失败（§29）
    """
    from .scripts import get_script

    _blog("browser_started", task_id, message=f"platform={platform} mode={mode}")

    script = get_script(platform)
    if script is None:
        return PublishResult(
            success=False,
            error_code="no_browser_script",
            error_message=f"platform {platform} 没有可用的浏览器发布脚本",
        )

    if account is None:
        return PublishResult(
            success=False,
            error_code="account_required",
            error_message="浏览器平台发布必须绑定账号",
        )

    state_path = storage_state_path(platform, account.key)
    if not state_path.exists():
        _blog("login_checked", task_id, level="warning", message="no storage_state")
        return PublishResult(
            success=False,
            needs_auth=True,
            error_code="login_required",
            error_message=f"未找到登录态文件，请先执行 publisher browser login {platform}",
        )

    diag = f"{platform}_{task_id or 'na'}"
    result: PublishResult | None = None
    worker = BrowserWorker()
    page = None
    try:
        ctx = await worker.start(storage_state=str(state_path))
        await worker.start_tracing()
        page = await ctx.new_page()

        _blog("page_opened", task_id, message=script.creator_url)
        await page.goto(script.creator_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)  # SPA 渲染缓冲

        # 登录检查（§24）：失效 → waiting_auth
        logged_in = await script.is_logged_in(page)
        _blog("login_checked", task_id, message=f"logged_in={logged_in}")
        if not logged_in:
            shot = await _screenshot(page, f"{diag}_login_expired")
            result = PublishResult(
                success=False,
                needs_auth=True,
                error_code="login_expired",
                error_message=f"登录态已失效，请重新执行 browser login（截图: {shot}）",
            )
            return result

        # 人工接管检测（§25）：验证码/风控 → waiting_manual
        try:
            body = await page.content()
        except Exception:
            body = ""
        reason = detect_manual_intervention(body, script.manual_keywords)
        if reason:
            shot = await _screenshot(page, f"{diag}_manual_{_safe_name(reason)}")
            result = PublishResult(
                success=False,
                needs_manual=True,
                error_code="manual_intervention",
                error_message=f"检测到需人工处理的页面特征: {reason}（截图: {shot}）",
            )
            return result

        # 平台脚本执行填写与提交（选择器、上传、成功确认都在 scripts/ 内）
        _blog("content_filled", task_id, message="正在提交发布请求")
        result = await script.publish(page, version, mode=mode)
        _blog(
            "submit_clicked", task_id,
            level="info" if result.success else "warning",
            message=f"success={result.success} code={result.error_code or 'ok'}",
        )
        if not result.success:
            await _screenshot(page, f"{diag}_failed_{_safe_name(result.error_code or 'unknown')}")
        return result
    except Exception as exc:  # noqa: BLE001
        result = PublishResult(success=False, error_code="browser_error", error_message=str(exc))
        return result
    finally:
        ok = bool(result and result.success)
        # 失败/无法确认时保留 Trace 供诊断（§75-20）
        await worker.stop_tracing(save=(not ok) and page is not None, name=diag)
        await worker.stop()


async def run_browser_login(
    platform: str,
    account_key: str,
    timeout: int | None = None,
) -> Path:
    """打开可见浏览器等待用户完成登录，保存 storage_state（§24）。

    本机部署：直接显示 Chromium 窗口（§25 方案 B）；
    容器部署：窗口渲染在 Xvfb 上，用户通过 noVNC(:6080) 操作（§25 方案 A）。

    登录成功后返回 storage_state 保存路径；失败抛 LoginError。
    """
    from .scripts import get_script

    script = get_script(platform)
    if script is None:
        raise LoginError(f"platform {platform} 没有可用的浏览器登录脚本")

    timeout = timeout if timeout and timeout > 0 else settings.browser_login_timeout
    state_path = storage_state_path(platform, account_key)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    worker = BrowserWorker(headless=False)  # 登录必须可视化（§25）
    try:
        ctx = await worker.start()
        page = await ctx.new_page()
        await page.goto(script.creator_url, wait_until="domcontentloaded", timeout=60000)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if page.is_closed():
                raise LoginError("浏览器窗口被关闭，登录未完成")
            try:
                if await script.is_logged_in(page):
                    await ctx.storage_state(path=str(state_path))
                    return state_path
            except LoginError:
                raise
            except Exception:
                pass  # 页面跳转中，下一轮再查
            await asyncio.sleep(2)
        raise LoginError(f"登录等待超时（{timeout}s）")
    finally:
        await worker.stop()
