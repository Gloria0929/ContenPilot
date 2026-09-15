"""今日头条 / 头条号平台 Adapter（浏览器自动化）。

通过 Playwright 在今日头条创作平台发布：
selector / 页面操作在 browser/scripts/toutiao.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("toutiao")
class ToutiaoAdapter(BrowserModeAdapter):
    pass
