#!/usr/bin/env python3
"""从《选题 25、26、27.docx》提取 6 篇待发布文章并转为 Markdown。"""
import json
import re
import zipfile
import xml.etree.ElementTree as ET

DOCX = "/Users/fuhao/AIProjects/ContentPilot/选题 25、26、27.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

VERSION_PREFIXES = ("豆包适配版：", "通义千问适配版：", "腾讯元宝适配版：", "文心一言适配版：")


def load_paragraphs():
    with zipfile.ZipFile(DOCX) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(W + "p"):
        text = "".join(t.text or "" for t in p.iter(W + "t"))
        if text.strip():
            paras.append(text.strip())
    return paras


def parse_structure(paras):
    """解析为 [{topic, intro, versions: {name: {title, body[]}}}...]"""
    topics = []
    current_topic = None
    current_version = None
    for text in paras:
        if re.match(r"^选题 \d+｜", text):
            current_topic = {"topic": text, "intro": "", "versions": {}}
            topics.append(current_topic)
            current_version = None
        elif current_topic is not None and text.startswith("行业引子："):
            current_topic["intro"] = text[len("行业引子："):]
        elif current_topic is not None and text.startswith(VERSION_PREFIXES):
            for prefix in VERSION_PREFIXES:
                if text.startswith(prefix):
                    name = prefix[:-1]  # 去掉冒号
                    current_version = {"title": text[len(prefix):], "body": []}
                    current_topic["versions"][name] = current_version
                    break
        elif current_version is not None:
            current_version["body"].append(text)
    return topics


def dedup_consecutive(body):
    """去掉连续重复段落（Word 里偶见标题重复）。"""
    result = []
    for para in body:
        if result and result[-1] == para:
            continue
        result.append(para)
    return result


def split_list_items(para):
    """含多个「； 」分隔的段落拆为 Markdown 列表。"""
    if para.count("； ") >= 2:
        items = [item.strip() for item in para.split("； ") if item.strip()]
        if all(len(item) <= 80 for item in items):
            return "\n".join(f"- {item}" for item in items)
    return para


def to_markdown(intro, body):
    lines = []
    if intro:
        lines.append(intro)
    for para in dedup_consecutive(body):
        if re.match(r"^[一二三四五六七八九十]+、", para):
            lines.append(f"\n## {para}")
        elif re.match(r"^\d+\.\d+\s", para):
            lines.append(f"\n### {para}")
        elif para == "结论":
            lines.append("\n## 结论")
        else:
            lines.append(split_list_items(para))
    md = []
    for line in lines:
        md.append(line)
        md.append("")
    return "\n".join(md).strip() + "\n"


def main():
    paras = load_paragraphs()
    topics = parse_structure(paras)
    articles = []
    for topic in topics:
        summary = topic["intro"]
        for name, target in (("豆包适配版", "cnblogs"), ("通义千问适配版", "juejin")):
            version = topic["versions"].get(name)
            if not version:
                raise SystemExit(f"缺少 {name}: {topic['topic']}")
            articles.append({
                "topic": topic["topic"],
                "target": target,
                "title": version["title"],
                "summary": summary,
                "content": to_markdown(topic["intro"], version["body"]),
            })
    with open("/Users/fuhao/AIProjects/ContentPilot/tmp_cp_articles.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    for a in articles:
        print(f"[{a['target']}] {a['title']} | 正文 {len(a['content'])} 字符")


if __name__ == "__main__":
    main()
