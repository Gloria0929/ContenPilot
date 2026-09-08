"""掘金浏览器发布脚本（浏览器入口 §23）。

掘金无官方稳定发布 API，通过 Playwright 在站内 Markdown 编辑器发布
（https://juejin.cn/editor/drafts/new?v=2，老路由 /editor 已重定向首页）。
所有 selector 集中在本文件常量中，平台改版时只需更新这里。
流程：填标题 → 填 Markdown 正文 →（草稿：编辑器自动保存）→
点「发布」→ 面板选分类/标签 → 「确定并发布」→ 轮询跳转 /post/<id> 确认（§26）。

发布面板为字节组件体系（xitu-btn / byte-select），selector 按 2026-09 真实 DOM 探测落点：
- 打开面板：底部 button.xitu-btn 文案「发布」（草稿箱是 btn-drafts，按文案区分）
- 分类：.category-list .item（选中态 item active，新草稿默认无选中）
- 标签：.byte-select__placeholder（文案「请搜索添加标签」）打开下拉，
  选项为可见的 .byte-select-dropdown .byte-select-option
- 确认：.publish-popup 内 .btn.primary（文案「确定并发布」）
"""
from __future__ import annotations

import re

from ...platforms.base import PublishResult
from . import BrowserScript


class JuejinScript(BrowserScript):
    platform = "juejin"
    creator_url = "https://juejin.cn/editor/drafts/new?v=2"
    manual_keywords = ("安全验证", "滑块", "验证码", "captcha", "异常访问")

    # ---- selector 多候选，按顺序尝试 ----
    TITLE_SELECTORS = (
        "input.title-input",
        "input[placeholder*='标题']",
    )
    EDITOR_SELECTORS = (
        ".CodeMirror",
        "div[contenteditable='true']",
    )
    # 打开发布面板：编辑器底部「发布」（xitu-btn）；按文案精确匹配，
    # 「草稿箱」等其他 xitu-btn 不会被命中
    OPEN_PANEL_TEXTS = ("发布",)
    OPEN_PANEL_EXCLUDE = ("定时", "草稿", "取消")
    # 面板分类列表项（新草稿默认无选中；优先 CATEGORY_PREFERRED，兜底第一项）
    CATEGORY_ITEM_SELECTORS = (
        ".category-list .item",
        "[class*='category'] li",
        "[class*='category'] [class*='item']",
    )
    CATEGORY_PREFERRED = ("前端",)
    # 标签：byte-select 搜索下拉（点 placeholder 打开，input 不接收点击）
    TAG_PLACEHOLDER_TEXT = "请搜索添加标签"
    TAG_PLACEHOLDER_SELECTOR = ".byte-select__placeholder"
    TAG_OPTION_SELECTORS = (
        ".byte-select-dropdown .byte-select-option",
        ".byte-select-dropdown li",
        "[class*='byte-select'] [class*='option']",
    )
    # 面板内「编辑摘要」必填项（textarea，100 字上限；实测有 ≥50 字下限校验）
    SUMMARY_SELECTORS = (
        ".publish-popup textarea",
        "textarea[placeholder*='摘要']",
        "textarea[placeholder*='编辑摘要']",
    )
    SUMMARY_MAX = 100
    SUMMARY_MIN = 50  # console 实测：「摘要不满足最低50字的要求」
    # 面板内确认按钮：.publish-popup 里的 primary 按钮（文案「确定并发布」）
    CONFIRM_SELECTORS = (
        ".publish-popup button.btn.primary",
        ".publish-popup button[class*='primary']",
    )
    CONFIRM_TEXTS = ("确定并发布", "发布")
    CONFIRM_EXCLUDE = ("定时", "取消")
    SUCCESS_URL_PATTERN = re.compile(r"/post/([0-9]+)")
    PUBLISHED_URL_SUFFIX = "/published"  # 发布成功后 SPA 落地的「已发布」列表页
    # 发布接口（响应含 article_id / err_no），落地行为不稳定时的最优证据来源
    PUBLISH_API_PATTERN = re.compile(r"/article/publish", re.I)
    SUCCESS_TEXTS = ("发布成功", "文章发布成功")
    CONFIRM_TIMEOUT_MS = 25000

    # 平台硬限制（标题 100 字符上限，留缓冲）
    TITLE_MAX = 100

    # 登录会话 cookie 特征（字节跳动护照体系），跨页面稳定
    SESSION_COOKIE_HINTS = ("sessionid", "sid_tt", "sid_guard")

    async def is_logged_in(self, page) -> bool:
        """登录判定：session 类 cookie 优先，编辑器 UI 兜底。

        未登录时掘金可能停留在编辑器路由弹登录浮层（不一定跳 /login），
        所以既不能靠「没有登录特征」反推已登录，也不能只认编辑器 DOM。
        """
        if "login" in (page.url or "") or "/sign_up" in (page.url or ""):
            return False
        try:
            cookies = await page.context.cookies("https://juejin.cn")
            for c in cookies:
                name = (c.get("name") or "").lower()
                if any(h in name for h in self.SESSION_COOKIE_HINTS):
                    return True
        except Exception:
            pass
        for sel in self.TITLE_SELECTORS + (".CodeMirror",):
            try:
                if await page.locator(sel).first.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def publish(self, page, version, mode: str = "publish") -> PublishResult:
        # submitted 用可变容器传递：点击「确定并发布」后置 True，
        # 之后任何异常都无法确认是否已发布成功 → unconfirmed（§26）
        submitted = [False]
        try:
            await self._fill_title(page, version.title or "")
            await self._fill_content(page, version.content or "")

            if mode == "draft":
                # 掘金编辑器自动保存草稿（顶部显示「已保存」），无独立草稿按钮
                await page.wait_for_timeout(2000)
                return PublishResult(success=True)

            return await self._submit_and_confirm(page, submitted, version)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                success=False,
                error_code="script_failed",
                error_message=str(exc),
                unconfirmed=submitted[0],
            )

    # ---- 内部步骤 ----

    async def _first(self, page, selectors, timeout: int = 8000):
        """按顺序尝试多个 selector，返回第一个可见的 locator。"""
        per = max(1500, timeout // max(len(selectors), 1))
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=per)
                return loc
            except Exception:
                continue
        return None

    async def _button_by_text(self, page, texts, exclude=(), scope=None):
        """按按钮文案查找可见按钮（精确匹配），排除定时发布/取消等干扰项。"""
        root = scope if scope is not None else page
        buttons = root.locator("button")
        count = await buttons.count()
        for i in range(count):
            b = buttons.nth(i)
            try:
                text = (await b.inner_text()).strip()
            except Exception:
                continue
            if text in texts and not any(x in text for x in exclude):
                if await b.is_visible():
                    return b
        return None

    async def _fill_title(self, page, title: str) -> None:
        if not title:
            return
        loc = await self._first(page, self.TITLE_SELECTORS, timeout=10000)
        if loc is None:
            raise RuntimeError("未找到标题输入框")
        await loc.fill(title[: self.TITLE_MAX])

    async def _fill_content(self, page, content: str) -> None:
        if not content:
            return
        loc = await self._first(page, self.EDITOR_SELECTORS, timeout=10000)
        if loc is None:
            raise RuntimeError("未找到 Markdown 编辑器")
        await loc.click()
        # CodeMirror 通过隐藏 textarea 接收输入；insert_text 对中文友好
        await page.keyboard.insert_text(content)

    async def _submit_and_confirm(
        self, page, submitted: list[bool], version
    ) -> PublishResult:
        submitted_title = (version.title or "")[: self.TITLE_MAX]
        # 1. 点底部「发布」打开发布面板（文案匹配为主，无等待开销）
        opener = await self._button_by_text(
            page, self.OPEN_PANEL_TEXTS, exclude=self.OPEN_PANEL_EXCLUDE
        )
        if opener is None:
            await page.wait_for_timeout(2000)  # 编辑器还在渲染时再等一轮
            opener = await self._button_by_text(
                page, self.OPEN_PANEL_TEXTS, exclude=self.OPEN_PANEL_EXCLUDE
            )
        if opener is None:
            return PublishResult(success=False, error_code="publish_button_not_found")
        await opener.click()
        await page.wait_for_timeout(1500)  # 等面板渲染

        # 2. 分类：未选中时优先点「前端」
        await self._ensure_category(page)

        # 3. 标签：至少选一个（平台要求）
        await self._ensure_tag(page)

        # 4. 编辑摘要：面板必填项（截图实测红色星号，100 字上限），为空会被卡住
        await self._ensure_summary(page, version)

        # 5. 面板内确认发布（此后无法确认是否成功 → unconfirmed 语义分界）
        confirm = await self._first(page, self.CONFIRM_SELECTORS, timeout=6000)
        if confirm is None:
            confirm = await self._button_by_text(
                page, self.CONFIRM_TEXTS, exclude=self.CONFIRM_EXCLUDE
            )
        if confirm is None:
            return PublishResult(success=False, error_code="confirm_button_not_found")

        # 等按钮可用：草稿自动保存（article_draft/update）期间「确定并发布」
        # 处于 disabled 状态，点击无效（实测 2026-09，点击后停留编辑器无反应）
        for _ in range(30):  # 最多 ~15s
            try:
                if not await confirm.is_disabled():
                    break
            except Exception:
                break
            await page.wait_for_timeout(500)

        # 监听发布接口响应：掘金发布后的落地行为不稳定（实测可能跳
        # /published 列表、也可能停留编辑器），从 article/publish 的
        # 响应里直接拿 article_id / 错误信息最可靠。
        captured: dict[str, str] = {}

        async def _on_response(resp) -> None:
            try:
                if not self.PUBLISH_API_PATTERN.search(resp.url):
                    return
                data = await resp.json()
            except Exception:
                return
            if not isinstance(data, dict):
                return
            if data.get("err_no") not in (0, None):
                captured["error"] = str(data.get("err_msg") or f"err_no={data.get('err_no')}")
                return
            d = data.get("data") or {}
            if isinstance(d, dict):
                aid = d.get("article_id") or d.get("id")
                if aid:
                    captured["article_id"] = str(aid)

        page.on("response", _on_response)
        try:
            await confirm.click()
            submitted[0] = True  # 此后无法确认是否发布成功
            return await self._wait_publish_result(page, captured, submitted_title)
        finally:
            try:
                page.remove_listener("response", _on_response)
            except Exception:
                pass

    async def _wait_publish_result(
        self, page, captured: dict[str, str], submitted_title: str
    ) -> PublishResult:
        """轮询确认发布结果（§26）：接口响应 > URL 跳转 > 成功提示。"""
        elapsed = 0
        toast_seen = False
        while elapsed < self.CONFIRM_TIMEOUT_MS:
            await page.wait_for_timeout(1000)
            elapsed += 1000

            # 接口明确返回 article_id → 发布成功（最优证据）
            if "article_id" in captured:
                aid = captured["article_id"]
                return PublishResult(
                    success=True,
                    remote_id=aid,
                    remote_url=f"https://juejin.cn/post/{aid}",
                )
            # 接口明确报错 → 发布被拒（未发布成功，可安全重试）
            if "error" in captured and toast_seen:
                return PublishResult(
                    success=False,
                    error_code="publish_rejected",
                    error_message=captured["error"],
                )

            url = page.url or ""
            m = self.SUCCESS_URL_PATTERN.search(url)
            if m:
                post_id = m.group(1)
                return PublishResult(
                    success=True,
                    remote_id=post_id,
                    remote_url=f"https://juejin.cn/post/{post_id}",
                )
            if self.PUBLISHED_URL_SUFFIX in url:
                # 落地「已发布」列表页：等列表渲染后按标题定位新文章
                remote_url = await self._resolve_published_url(page, submitted_title)
                post_id = (
                    remote_url.rsplit("/post/", 1)[-1].split("?")[0]
                    if remote_url
                    else None
                )
                return PublishResult(success=True, remote_id=post_id, remote_url=remote_url)
            try:
                content = await page.content()
            except Exception:
                continue
            if any(t in content for t in self.SUCCESS_TEXTS):
                toast_seen = True
                # 成功提示已出；再给接口响应/跳转几秒时间拿链接
                for _ in range(6):
                    await page.wait_for_timeout(1000)
                    if "article_id" in captured:
                        aid = captured["article_id"]
                        return PublishResult(
                            success=True,
                            remote_id=aid,
                            remote_url=f"https://juejin.cn/post/{aid}",
                        )
                    url = page.url or ""
                    if self.PUBLISHED_URL_SUFFIX in url:
                        remote_url = await self._resolve_published_url(page, submitted_title)
                        post_id = (
                            remote_url.rsplit("/post/", 1)[-1].split("?")[0]
                            if remote_url
                            else None
                        )
                        return PublishResult(
                            success=True, remote_id=post_id, remote_url=remote_url
                        )
                    m = self.SUCCESS_URL_PATTERN.search(url)
                    if m:
                        post_id = m.group(1)
                        return PublishResult(
                            success=True,
                            remote_id=post_id,
                            remote_url=f"https://juejin.cn/post/{post_id}",
                        )
                return PublishResult(success=True)

        return PublishResult(
            success=False,
            unconfirmed=True,
            error_code="publish_unconfirmed",
            error_message="点击发布后未检测到跳转或成功提示，无法确认是否发布成功",
        )

    async def _ensure_summary(self, page, version) -> None:
        """填写面板内必填的「编辑摘要」：优先文章 summary，空则从正文提取。

        注意 ArticleVersion 模型没有 summary 字段（摘要在 articles 表），
        所以用 getattr 兼容，另尝试 metadata_json 里的 summary。
        正文提取：去掉 Markdown 标记与空白行，取第一段非标题文本截断。
        找不到摘要输入框时不阻断（交由平台校验报错）。
        """
        import json as _json

        paragraphs = self._extract_plain_paragraphs(version.content or "")
        text = (getattr(version, "summary", None) or "").strip()
        if not text:
            try:
                meta = _json.loads(getattr(version, "metadata_json", "") or "{}")
                text = str(meta.get("summary") or "").strip()
            except Exception:
                text = ""
        if not text and paragraphs:
            text = paragraphs.pop(0)
        if not text:
            return
        # 摘要不足下限时从正文剩余段落补足（平台校验 ≥50 字，不足会拦截发布）
        while paragraphs and len(text) < self.SUMMARY_MIN:
            text = (text + " " + paragraphs.pop(0)).strip()
        text = text[: self.SUMMARY_MAX]
        try:
            box = await self._first(page, self.SUMMARY_SELECTORS, timeout=4000)
            if box is None:
                return
            await box.click()
            await box.fill(text)
            await page.wait_for_timeout(200)
        except Exception:
            pass

    @staticmethod
    def _extract_plain_paragraphs(content: str) -> list[str]:
        """提取正文里的纯文本段落（去 Markdown 标记），用于补足摘要。"""
        out = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", ">", "-", "*", "!", "|", "```")):
                continue
            out.append(line.lstrip("#").strip())
        return out

    async def _resolve_published_url(self, page, title: str) -> str | None:
        """在「已发布」列表页定位刚发布的文章链接。

        /published 直开会被重定向回首页，只有发布成功后的 SPA 内部跳转
        能停留，所以这里不做导航，只等当前页列表渲染。
        优先按标题精确匹配，兜底取列表第一条（按发布时间倒序）。
        """
        for _ in range(6):  # 列表异步加载，最多等 ~6s
            links = page.locator("a[href*='/post/']")
            try:
                count = await links.count()
            except Exception:
                count = 0
            first_href = None
            for i in range(count):
                a = links.nth(i)
                try:
                    if not await a.is_visible():
                        continue
                    href = await a.get_attribute("href")
                    text = ((await a.inner_text()) or "").strip()
                except Exception:
                    continue
                if not href or "/post/" not in href:
                    continue
                if first_href is None:
                    first_href = href
                if title and title in text:
                    return self._abs_post_url(href)
            if count and first_href:
                # 有链接但没匹配上标题（可能被平台截断），兜底第一条
                return self._abs_post_url(first_href)
            await page.wait_for_timeout(1000)
        return None

    @staticmethod
    def _abs_post_url(href: str) -> str:
        href = (href or "").split("?")[0]
        if href.startswith("http"):
            return href
        return f"https://juejin.cn{href}"

    async def _ensure_category(self, page) -> None:
        """分类未选中时优先点 CATEGORY_PREFERRED 项；已选/找不到列表则跳过。"""
        items = None
        for sel in self.CATEGORY_ITEM_SELECTORS:
            loc = page.locator(sel)
            try:
                if await loc.count() > 0:
                    items = loc
                    break
            except Exception:
                continue
        if items is None:
            return
        try:
            count = await items.count()
            texts: list[tuple[int, str, object]] = []
            for i in range(count):
                item = items.nth(i)
                if not await item.is_visible():
                    continue
                class_attr = await item.get_attribute("class") or ""
                if "active" in class_attr or "selected" in class_attr:
                    return  # 已有选中项
                texts.append(
                    (i, ((await item.inner_text()) or "").strip(), item)
                )
            # 优先选偏好分类（如「前端」），否则第一项
            target = next(
                (it for _, text, it in texts if text in self.CATEGORY_PREFERRED),
                texts[0][2] if texts else None,
            )
            if target is not None:
                await target.click()
                await page.wait_for_timeout(300)
        except Exception:
            pass  # 分类失败不阻断：面板可能自带默认分类

    async def _ensure_tag(self, page) -> None:
        """标签必填：点 placeholder 打开下拉 → 点可见选项（优先偏好标签）。

        页面上有标签/专栏/话题三个 byte-select，用 placeholder 文案定位标签框；
        下拉选项仅点可见的（隐藏的专栏/话题下拉同时在 DOM 里）。
        """
        try:
            placeholder = page.locator(
                self.TAG_PLACEHOLDER_SELECTOR,
                has_text=self.TAG_PLACEHOLDER_TEXT,
            ).first
            if not await placeholder.is_visible():
                return  # 找不到标签入口时不强行失败，交由平台校验报错
            await placeholder.click()
            await page.wait_for_timeout(800)
            option = await self._visible_option(page)
            if option is not None:
                await option.click()
                await page.wait_for_timeout(300)
        except Exception:
            pass  # 标签失败不阻断：交由平台校验报错

    async def _visible_option(self, page):
        """在下拉选项中选第一项可见且文本命中的（优先 CATEGORY_PREFERRED）。"""
        for sel in self.TAG_OPTION_SELECTORS:
            opts = page.locator(sel)
            try:
                count = await opts.count()
            except Exception:
                continue
            visible = []
            for i in range(count):
                o = opts.nth(i)
                try:
                    if not await o.is_visible():
                        continue
                    text = ((await o.inner_text()) or "").strip()
                except Exception:
                    continue
                if not text:
                    continue
                visible.append((text, o))
            if not visible:
                continue
            preferred = next(
                (o for text, o in visible if text in self.CATEGORY_PREFERRED), None
            )
            return preferred or visible[0][1]
        return None


script = JuejinScript()
