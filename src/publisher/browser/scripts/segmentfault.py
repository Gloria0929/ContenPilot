"""思否（SegmentFault）浏览器发布脚本（selector 已按 2026-09 真实 DOM 实测校准）。

思否无官方发布 API，通过 Playwright 在写作页发布
（https://segmentfault.com/write）。

实测 DOM 要点（2026-09，探测日志见会话记录）：
- 无头模式下思否 React 不挂载编辑器（.sf-editor-wrap 恒 hidden），
  必须有头运行（本机弹窗 / 容器走 Xvfb :99），故 headless=False。
- 标题：input#title（placeholder「请输入标题」），常规 fill 即可。
- 正文：CodeMirror（.CodeMirror，内部隐藏 textarea），点击聚焦 +
  insert_text；编辑器懒挂载，需先点「正文」区的「编辑」tab。
- 标签（必填，页面内非弹窗）：button#tags-toggle「+ 添加标签」→
  .dropdown-menu.show input.form-control（placeholder「搜索标签」）→
  #tagSearchResult a.dropdown-item.search-item 候选列表 → 点选后
  chip 出现、「还可添加 N 个标签」（.tags-left）减一。
  无匹配时候选显示「找不到相关标签」，可点下拉头部 a#createTag
  「创建」新标签——低权限账号会弹「提示」框（没有权限创建标签，
  取消/确定），脚本自动关闭后降级到下一个关键词
  （以 tags-left 减小为成功判据）。
- 主发布按钮：btn.btn-primary「提交」（注意不是「发布」），
  同排有「舍弃草稿」（exclude 排除）。
- 文章类型/版权等 radio/checkbox 有默认值（原创），无需处理。
- 成功：跳转 segmentfault.com/a/<id>。
"""
from __future__ import annotations

import json
import re

from ...platforms.base import PublishResult
from ._common import CommonScript


class SegmentFaultScript(CommonScript):
    platform = "segmentfault"
    creator_url = "https://segmentfault.com/write"
    manual_keywords = ("安全验证", "验证码")
    # 无头模式下 React 不挂载编辑器，必须有头运行
    headless = False

    TITLE_SELECTORS = ("input#title", "input[placeholder*='标题']")
    # CodeMirror 编辑器（实测页面无裸 textarea / contenteditable）
    EDITOR_SELECTORS = (".CodeMirror",)
    # 主按钮是「提交」而非「发布」
    PUBLISH_TEXTS = ("提交",)
    PUBLISH_EXCLUDE = ("定时", "草稿", "取消", "舍弃")
    CONFIRM_TEXTS = ("确认发布", "发布文章", "确认并发布", "确认", "发布")
    CONFIRM_EXCLUDE = ("定时", "取消", "舍弃")
    # 标签（页面内）：+ 添加标签 → 搜索框 → 候选列表（#tagSearchResult）
    TAG_TOGGLE = "button#tags-toggle"
    TAG_SEARCH = ".dropdown-menu.show input.form-control"
    TAG_RESULT = "#tagSearchResult a.dropdown-item.search-item"
    # 无匹配时候选固定显示「找不到相关标签」，创建入口在下拉头部 a#createTag
    TAG_NO_RESULT = "找不到相关标签"
    TAG_CREATE = "a#createTag"
    # 无独立草稿按钮（编辑器自动保存）
    DRAFT_TEXTS = ()
    SUCCESS_URL_PATTERN = re.compile(r"/a/(\d{6,})")
    LOGIN_URL_MARKS = ("login", "signin", "userauth")
    CONFIRM_TIMEOUT_MS = 30000

    async def publish(self, page, version, mode: str = "publish") -> PublishResult:
        submitted = [False]
        try:
            # 编辑器懒挂载：先点「编辑」tab 确保 CodeMirror 渲染
            await self._activate_editor(page)
            await self._fill_title(page, version.title or "")
            await self._fill_content(page, version.content or "")
            # 标签是页面内必填项，必须在点「提交」之前选好
            if mode == "publish":
                await self._add_tags(page, version)
                return await self._submit_and_confirm(page, submitted, version)
            return await self._save_draft(page)
        except Exception as exc:  # noqa: BLE001
            return PublishResult(
                success=False,
                error_code="script_failed",
                error_message=str(exc),
                unconfirmed=submitted[0],
            )

    # ---- 思否特有步骤 ----

    async def _activate_editor(self, page) -> None:
        """编辑器懒挂载：.sf-editor-wrap 带 hidden 时点「编辑」tab 激活。"""
        try:
            hidden = await page.evaluate(
                """() => {
                  const w = document.querySelector('.sf-editor-wrap');
                  if (!w || !w.classList.contains('hidden')) return false;
                  const a = [...document.querySelectorAll('a')]
                    .find(x => (x.textContent || '').trim() === '编辑');
                  if (a) { a.click(); return true; }
                  return false;
                }"""
            )
        except Exception:
            hidden = False
        if hidden:
            await page.wait_for_timeout(1500)

    async def _tag_keywords(self, version) -> list[str]:
        """标签搜索关键词：metadata tags 优先，其次标题截断，兜底常见标签。"""
        kws: list[str] = []
        try:
            meta = json.loads(version.metadata_json or "{}")
            tags = meta.get("tags") or []
            kws.extend(str(t)[:20] for t in tags if str(t).strip())
        except Exception:
            pass
        title = (version.title or "").strip()
        if title:
            kws.append(title[:10])
            # 标题里抽个像标签的词（英文/数字段）
            m = re.search(r"[A-Za-z][A-Za-z0-9.+#-]{2,}", title)
            if m:
                kws.append(m.group(0))
        kws.append("程序员")  # 必然存在的兜底标签
        return kws

    async def _add_tags(self, page, version) -> None:
        """页面内选标签：+ 添加标签 → 搜索 → 有候选点选；无候选点「创建」
        （部分账号无创建权限，创建失败自动降级到下一个关键词）。
        以「还可添加 N 个标签」计数减小为准判断选中成功；全部失败不阻断主流程。"""
        for kw in await self._tag_keywords(version):
            try:
                before = await self._tags_left(page)
                toggle = page.locator(self.TAG_TOGGLE).first
                await toggle.wait_for(state="visible", timeout=5000)
                await toggle.click()
                await page.wait_for_timeout(1000)

                search = page.locator(self.TAG_SEARCH).first
                await search.wait_for(state="visible", timeout=4000)
                await search.click()
                await search.fill(kw)
                await page.wait_for_timeout(1500)

                # 1) 优先点选已有候选（跳过「找不到相关标签」占位项）
                picked = False
                opts = page.locator(self.TAG_RESULT)
                for i in range(min(await opts.count(), 5)):
                    o = opts.nth(i)
                    try:
                        if not await o.is_visible():
                            continue
                        if self.TAG_NO_RESULT in (await o.inner_text()).strip():
                            continue
                        await o.click()
                        picked = True
                        break
                    except Exception:
                        continue

                # 2) 无候选：尝试「创建」标签；无权限账号会弹「提示」框
                #    （「没有权限创建标签」，取消/确定均可关闭），需自动关闭
                if not picked:
                    try:
                        create = page.locator(self.TAG_CREATE).first
                        if await create.is_visible():
                            await create.click()
                            await page.wait_for_timeout(1000)
                            await self._dismiss_dialog(page)
                    except Exception:
                        pass

                # 3) 用 tags-left 计数验证是否真的加上了
                after = await self._tags_left(page)
                if before is not None and after is not None and after < before:
                    await page.keyboard.press("Escape")  # 收起下拉
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue
        # 全部关键词都没选上：收起下拉，不阻断主流程
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    async def _tags_left(self, page) -> int | None:
        """读「还可添加 N 个标签」计数，失败返回 None。"""
        try:
            txt = await page.locator(".tags-left").first.inner_text()
            digits = re.sub(r"\D", "", txt)
            return int(digits) if digits else None
        except Exception:
            return None

    async def _dismiss_dialog(self, page) -> None:
        """关闭创建标签相关的弹窗（如「没有权限创建标签」提示框）。
        优先点「确定」（有权限账号的确认创建场景），其次「取消」。"""
        try:
            await page.evaluate(
                """() => {
                    const m = [...document.querySelectorAll('.modal.show, [role=dialog]')]
                        .find(x => x.offsetParent || x.getClientRects().length);
                    if (!m) return;
                    const btn = [...m.querySelectorAll('button')]
                        .find(b => ['确定', '取消', 'OK'].includes((b.textContent || '').trim()));
                    if (btn) btn.click();
                }"""
            )
            await page.wait_for_timeout(500)
        except Exception:
            pass


script = SegmentFaultScript()
