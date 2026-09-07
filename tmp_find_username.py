#!/usr/bin/env python3
"""分析博客园博客页面，寻找博主用户名线索。"""
import re
import subprocess

html = subprocess.run(
    ["curl", "-s", "-L", "https://www.cnblogs.com/Allthinker/", "-m", "10"],
    capture_output=True, text=True,
).stdout

m = re.search(r"currentBlogApp\s*=\s*['\"]([^'\"]+)", html)
print("currentBlogApp:", m.group(1) if m else None)

# 博主显示名
for pat, label in [
    (r"<h1[^>]*>(.*?)</h1>", "H1"),
    (r"<h2[^>]*>(.*?)</h2>", "H2"),
    (r'href="(https?://i\.cnblogs\.com[^"]*)"', "i.cnblogs链接"),
    (r'href="(https?://home\.cnblogs\.com/u/[^"]*)"', "home链接"),
    (r'href="(https?://www\.cnblogs\.com/[^"]+/)"', "博客链接"),
    (r"blogTitle", "blogTitle存在"),
]:
    for mm in re.findall(pat, html, re.S)[:6]:
        text = mm if isinstance(mm, str) else mm
        text = re.sub(r"\s+", " ", text.strip())[:120]
        print(f"[{label}] {text}")
