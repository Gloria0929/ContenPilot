"""FreeBuf 平台 Adapter（浏览器自动化）。

FreeBuf 无公开稳定的发布 API（文章需投稿审核），实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/freebuf.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("freebuf")
class FreebufAdapter(BrowserModeAdapter):
    pass
