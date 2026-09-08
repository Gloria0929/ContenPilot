"""浏览器发布脚本注册表。

平台特定的 selector / 页面操作流程只放在本目录（§73-3：浏览器代码只能在
Browser 层），Core 与 Adapter 不出现任何 selector。新增浏览器平台时：
1. 在本目录新增 <platform>.py，实现 BrowserScript 子类并暴露模块级 `script` 实例；
2. 在 _MODULES 注册平台名，Adapter 的 publish/create_draft 即可走真实流程。
"""
from __future__ import annotations

import importlib


class BrowserScript:
    """平台浏览器脚本基类。"""

    platform: str = ""
    creator_url: str = ""
    # 平台特有的人工接管特征词（§25），叠加在通用关键词之上
    manual_keywords: tuple[str, ...] = ()
    # 无头模式偏好：None = 用全局配置；False = 必须有头（如思否无头下
    # React 不挂载编辑器）；True = 强制无头
    headless: bool | None = None

    async def is_logged_in(self, page) -> bool:
        raise NotImplementedError

    async def publish(self, page, version, mode: str = "publish"):
        """执行内容填写与提交，返回 PublishResult。

        已点击发布但无法确认成功时，必须返回 unconfirmed=True（§26）。
        """
        raise NotImplementedError


_MODULES = {
    "juejin": "publisher.browser.scripts.juejin",
    "csdn": "publisher.browser.scripts.csdn",
    "segmentfault": "publisher.browser.scripts.segmentfault",
    "freebuf": "publisher.browser.scripts.freebuf",
    "baijiahao": "publisher.browser.scripts.baijiahao",
    "qiehao": "publisher.browser.scripts.qiehao",
    "51cto": "publisher.browser.scripts.cto51",
    "tencent_cloud": "publisher.browser.scripts.tencent_cloud",
}


def get_script(platform: str) -> BrowserScript | None:
    mod_path = _MODULES.get(platform)
    if not mod_path:
        return None
    module = importlib.import_module(mod_path)
    return module.script
