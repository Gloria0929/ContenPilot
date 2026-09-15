"""微信公众号文章排版渲染引擎。

内置支持 6 种经典主题风格（基于 gzh-design-skill 设计规范）：
- graphite: 石墨极简风
- slacking_green: 摸鱼绿
- red_white: 红白色系
- zen_white: 留白禅意风
- ticket_receipt: 摸鱼票据风
- olive_note: 橄榄手记

输出内联样式（Inline CSS）HTML，可直接粘贴进微信公众号后台或通过草稿箱 API 发布。
"""
from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt

# 6 种排版主题配置
THEMES: dict[str, dict[str, str]] = {
    "graphite": {
        "name": "石墨极简风",
        "primary": "#2B2B2B",
        "secondary": "#555555",
        "accent": "#000000",
        "bg_quote": "#F8F8F8",
        "border_quote": "#2B2B2B",
        "bg_code": "#F3F4F6",
        "text": "#333333",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif",
    },
    "slacking_green": {
        "name": "摸鱼绿",
        "primary": "#07C160",
        "secondary": "#059669",
        "accent": "#10B981",
        "bg_quote": "#F0FDF4",
        "border_quote": "#07C160",
        "bg_code": "#ECFDF5",
        "text": "#1F2937",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif",
    },
    "red_white": {
        "name": "红白色系",
        "primary": "#D93025",
        "secondary": "#BE123C",
        "accent": "#E11D48",
        "bg_quote": "#FFF1F2",
        "border_quote": "#D93025",
        "bg_code": "#FFF5F5",
        "text": "#27272A",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif",
    },
    "zen_white": {
        "name": "留白禅意风",
        "primary": "#44403C",
        "secondary": "#78716C",
        "accent": "#A8A29E",
        "bg_quote": "#FAFAF9",
        "border_quote": "#D6D3D1",
        "bg_code": "#F5F5F4",
        "text": "#292524",
        "font_family": "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
    },
    "ticket_receipt": {
        "name": "摸鱼票据风",
        "primary": "#1E293B",
        "secondary": "#475569",
        "accent": "#0F172A",
        "bg_quote": "#F1F5F9",
        "border_quote": "#94A3B8",
        "bg_code": "#E2E8F0",
        "text": "#0F172A",
        "font_family": "'Courier New', Consolas, 'PingFang SC', monospace, sans-serif",
    },
    "olive_note": {
        "name": "橄榄手记",
        "primary": "#556B2F",
        "secondary": "#6B8E23",
        "accent": "#4D5D28",
        "bg_quote": "#F4F6F0",
        "border_quote": "#556B2F",
        "bg_code": "#EEF1E6",
        "text": "#2F3E1B",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', serif, sans-serif",
    },
}


class WechatRenderer:
    """将 Markdown 转换为带内联样式的微信公众号 HTML。"""

    def __init__(self, theme: str = "graphite"):
        self.theme_name = theme if theme in THEMES else "graphite"
        self.theme = THEMES[self.theme_name]
        self.md = MarkdownIt("commonmark").enable("table")

    def render(self, markdown_text: str, title: str = "", digest: str = "") -> str:
        """核心渲染入口：将 markdown 转为内联样式的完整微信图文 HTML。"""
        raw_html = self.md.render(markdown_text)
        styled_html = self._apply_inline_styles(raw_html)

        header_html = ""
        if title:
            header_html = (
                f'<section style="margin-bottom: 24px; text-align: left;">'
                f'<h1 style="font-size: 22px; font-weight: bold; color: {self.theme["primary"]}; line-height: 1.4; margin: 0 0 10px 0;">{title}</h1>'
            )
            if digest:
                header_html += (
                    f'<p style="font-size: 14px; color: {self.theme["secondary"]}; line-height: 1.6; margin: 0; padding-bottom: 12px; border-bottom: 1px dashed #E5E7EB;">{digest}</p>'
                )
            header_html += '</section>'

        footer_html = (
            f'<section style="margin-top: 36px; padding-top: 20px; border-top: 1px solid #EEEEEE; text-align: center;">'
            f'<p style="font-size: 12px; color: #888888; line-height: 1.6;">本文由敖行客 <strong>AT Work Agent 研发工作台</strong> 智造分发</p>'
            f'</section>'
        )

        container = (
            f'<section class="contentpilot-wechat-article" style="font-family: {self.theme["font_family"]}; color: {self.theme["text"]}; font-size: 15px; line-height: 1.8; letter-spacing: 0.5px; word-break: break-word; padding: 10px;">'
            f'{header_html}'
            f'{styled_html}'
            f'{footer_html}'
            f'</section>'
        )
        return container

    def _apply_inline_styles(self, html: str) -> str:
        """对常用 HTML 标签注入符合微信渲染标准的内联 CSS。"""
        # H1
        html = re.sub(
            r'<h1>(.*?)</h1>',
            rf'<h1 style="font-size: 20px; font-weight: bold; color: {self.theme["primary"]}; border-left: 4px solid {self.theme["primary"]}; padding-left: 10px; margin: 26px 0 14px 0; line-height: 1.4;">\1</h1>',
            html,
            flags=re.DOTALL,
        )
        # H2
        html = re.sub(
            r'<h2>(.*?)</h2>',
            rf'<h2 style="font-size: 18px; font-weight: bold; color: {self.theme["primary"]}; border-bottom: 2px solid {self.theme["bg_quote"]}; padding-bottom: 6px; margin: 22px 0 12px 0; line-height: 1.4;">\1</h2>',
            html,
            flags=re.DOTALL,
        )
        # H3
        html = re.sub(
            r'<h3>(.*?)</h3>',
            rf'<h3 style="font-size: 16px; font-weight: 600; color: {self.theme["secondary"]}; margin: 18px 0 10px 0; line-height: 1.4;">\1</h3>',
            html,
            flags=re.DOTALL,
        )
        # P
        html = re.sub(
            r'<p>(.*?)</p>',
            rf'<p style="font-size: 15px; line-height: 1.85; margin: 0 0 16px 0; text-align: justify;">\1</p>',
            html,
            flags=re.DOTALL,
        )
        # Strong / Bold
        html = re.sub(
            r'<strong>(.*?)</strong>',
            rf'<strong style="font-weight: bold; color: {self.theme["primary"]};">\1</strong>',
            html,
            flags=re.DOTALL,
        )
        # Blockquote
        html = re.sub(
            r'<blockquote>\s*<p>(.*?)</p>\s*</blockquote>',
            rf'<blockquote style="margin: 18px 0; padding: 12px 16px; background-color: {self.theme["bg_quote"]}; border-left: 4px solid {self.theme["border_quote"]}; border-radius: 4px; font-size: 14px; color: {self.theme["secondary"]}; line-height: 1.7;">\1</blockquote>',
            html,
            flags=re.DOTALL,
        )
        # Ul & Ol
        html = re.sub(
            r'<ul>',
            r'<ul style="margin: 0 0 16px 0; padding-left: 20px; list-style-type: disc;">',
            html,
        )
        html = re.sub(
            r'<ol>',
            r'<ol style="margin: 0 0 16px 0; padding-left: 20px; list-style-type: decimal;">',
            html,
        )
        html = re.sub(
            r'<li>(.*?)</li>',
            r'<li style="margin-bottom: 6px; line-height: 1.75; font-size: 15px;">\1</li>',
            html,
            flags=re.DOTALL,
        )
        # Code block (pre code)
        html = re.sub(
            r'<pre><code(?: class="language-(.*?)")?>(.*?)</code></pre>',
            rf'<section style="margin: 16px 0; background-color: {self.theme["bg_code"]}; border-radius: 6px; padding: 12px 14px; overflow-x: auto;"><pre style="margin: 0; font-family: Consolas, Monaco, monospace; font-size: 13px; color: #1E293B; line-height: 1.6;"><code>\2</code></pre></section>',
            html,
            flags=re.DOTALL,
        )
        # Inline code
        html = re.sub(
            r'<code>(.*?)</code>',
            rf'<code style="background-color: {self.theme["bg_code"]}; color: {self.theme["primary"]}; padding: 2px 5px; border-radius: 3px; font-family: Consolas, Monaco, monospace; font-size: 13px;">\1</code>',
            html,
            flags=re.DOTALL,
        )
        # Table
        html = re.sub(
            r'<table>',
            r'<table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; text-align: left;">',
            html,
        )
        html = re.sub(
            r'<th>(.*?)</th>',
            rf'<th style="background-color: {self.theme["bg_quote"]}; border: 1px solid #E5E7EB; padding: 8px 10px; font-weight: bold; color: {self.theme["primary"]};">\1</th>',
            html,
            flags=re.DOTALL,
        )
        html = re.sub(
            r'<td>(.*?)</td>',
            r'<td style="border: 1px solid #E5E7EB; padding: 8px 10px; line-height: 1.5;">\1</td>',
            html,
            flags=re.DOTALL,
        )
        return html


def render_wechat_article(
    markdown_content: str,
    title: str = "",
    digest: str = "",
    theme: str = "graphite",
) -> str:
    """便捷函数：渲染微信公众号富文本。"""
    renderer = WechatRenderer(theme=theme)
    return renderer.render(markdown_content, title=title, digest=digest)
