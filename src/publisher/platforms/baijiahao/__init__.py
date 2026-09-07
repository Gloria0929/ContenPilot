"""百家号平台 Adapter（浏览器自动化）。

百家号无公开稳定的发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/baijiahao.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("baijiahao")
class BaijiahaoAdapter(BrowserModeAdapter):
    pass
