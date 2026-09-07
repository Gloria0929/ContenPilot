"""腾讯云开发者社区平台 Adapter（浏览器自动化）。

腾讯云开发者社区无公开稳定的个人发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/tencent_cloud.py。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("tencent_cloud")
class TencentCloudAdapter(BrowserModeAdapter):
    pass
