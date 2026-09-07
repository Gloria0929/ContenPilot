"""51CTO 平台 Adapter（浏览器自动化）。

51CTO 博客无公开稳定的发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/cto51.py。

模块目录名用 cto51（Python 标识符不能以数字开头），平台注册 key 为 51cto。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("51cto")
class Cto51Adapter(BrowserModeAdapter):
    pass
