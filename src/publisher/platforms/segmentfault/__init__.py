"""思否（SegmentFault）平台 Adapter（浏览器自动化）。

思否无公开稳定的发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/segmentfault.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("segmentfault")
class SegmentFaultAdapter(BrowserModeAdapter):
    pass
