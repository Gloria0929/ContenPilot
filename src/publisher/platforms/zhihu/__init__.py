"""知乎平台 Adapter（浏览器自动化专栏/文章发布）。

无官方开放发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/zhihu.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("zhihu")
class ZhihuAdapter(BrowserModeAdapter):
    pass
