"""企鹅号（腾讯内容开放平台 om.qq.com）Adapter（浏览器自动化）。

企鹅号无公开稳定的发布 API，实际发布走浏览器自动化：
selector / 页面操作在 browser/scripts/qiehao.py。
发布内容自动分发到腾讯网 / 腾讯新闻 / QQ浏览器等腾讯系渠道。
"""
from .._browser import BrowserModeAdapter
from ..registry import register


@register("qiehao")
class QiehaoAdapter(BrowserModeAdapter):
    pass
