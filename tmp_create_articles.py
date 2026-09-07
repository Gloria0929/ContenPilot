#!/usr/bin/env python3
"""批量创建文章并置为 ready。"""
import json
import subprocess

ARTICLES = json.load(open("/Users/fuhao/AIProjects/ContentPilot/tmp_cp_articles.json", encoding="utf-8"))

results = []
for a in ARTICLES:
    r = subprocess.run(
        ["publisher", "article", "create",
         "--title", a["title"],
         "--content", a["content"],
         "--summary", a["summary"],
         "--source", "manual",
         "--json"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"创建失败 [{a['target']}] {a['title']}:\n{r.stdout}\n{r.stderr}")
        raise SystemExit(1)
    out = r.stdout.strip()
    # 输出形如 {"id": 10, ...} 或含 id 的 JSON 行
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # 尝试从输出中提取 JSON 部分
        start = out.find("{")
        data = json.loads(out[start:])
    article_id = data.get("id") or data.get("article_id")
    if not article_id:
        print(f"无法解析文章 id: {out}")
        raise SystemExit(1)
    r2 = subprocess.run(
        ["publisher", "article", "update", str(article_id), "--status", "ready"],
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        print(f"置 ready 失败 #{article_id}: {r2.stdout}\n{r2.stderr}")
        raise SystemExit(1)
    results.append({"id": article_id, "target": a["target"], "title": a["title"]})
    print(f"#{article_id} ready [{a['target']}] {a['title']}")

with open("/Users/fuhao/AIProjects/ContentPilot/tmp_cp_created.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("全部创建完成")
