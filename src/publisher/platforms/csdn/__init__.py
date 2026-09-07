"""CSDN 平台 Adapter（浏览器自动化）。

CSDN 无公开稳定的发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/csdn.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("csdn")
class CsdnAdapter(BrowserModeAdapter):
    pass
