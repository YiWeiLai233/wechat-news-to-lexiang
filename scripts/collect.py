#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投喂文件解析器：把用户粘贴/整理的资讯清单，抽成结构化的条目。

读的是纯文本（粘贴也存成 .md/.txt 喂进来即可），每行一条，支持三种写法：
    - 微信链接卡片 XML（含 <appmsg>，能拿到标题+摘要）
    - 纯文本里夹链接（标题取《书名号》或链接前的文字，剩下当摘要）
    - 只有一行标题 + 链接

只用标准库。用法：

    python collect.py --path inbox.md --format markdown
    python collect.py --path inbox.md --out links.json
    python collect.py --path inbox.md --format markdown --out links.json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

URL_RE = re.compile(
    r"https?://[^\s<>\"'\uff08\uff09\u3000\u3001\u3002\uff0c\uff1b\uff01\uff1f\u300a\u300b\u3010\u3011]+"
)
TRAIL_PUNCT = ".,;:!?)）】》\"'、。，；：！？"
PAIR_RIGHT = {
    "\u300b": "\u300a",
    "\uff09": "(",
    "\u3011": "\u3010",
    "]": "[",
    ")": "(",
}
PLAIN_TAIL = "。，、；：！？.,;:!?'\"\u2026"
REC_LABEL = re.compile(r"^\s*(推荐语|推荐理由|理由|点评|备注|说明|要点)\s*[:：]\s*")
NOISE_PREFIX = re.compile(r"^\s*(\d{1,2}\s*[.、)]|[-*\u2022\u00b7\u25cf])\s*")
AUTHOR_TAG = re.compile(r"<!--\s*投喂人\s*[:：]\s*(.+?)\s*-->")
HTML_COMMENT = re.compile(r"<!--.*?-->")


# ---------------------------------------------------------------- 文本清洗

def safe_rstrip(s):
    while s:
        ch = s[-1]
        if ch in PAIR_RIGHT:
            if PAIR_RIGHT[ch] in s[:-1]:
                break
            s = s[:-1]
            continue
        if ch in PLAIN_TAIL:
            s = s[:-1]
            continue
        break
    return s


def clean_text(s):
    if not s:
        return ""
    s = s.strip()
    s = REC_LABEL.sub("", s)
    s = NOISE_PREFIX.sub("", s)
    return safe_rstrip(s.strip()).strip()


def classify(url):
    u = url.lower()
    if "/sph/" in u or "channels.weixin.qq.com" in u or "finder.video.qq.com" in u:
        return "channels"
    if "mp.weixin.qq.com" in u:
        return "article"
    return "web"


def norm_url(url):
    """去重键：微信链接的 query 全是来源追踪参数，一律丢掉。"""
    url = url.strip().rstrip(TRAIL_PUNCT)
    try:
        from urllib.parse import urlsplit

        p = urlsplit(url)
    except ValueError:
        return url
    if "weixin.qq.com" in p.netloc.lower():
        return f"{p.scheme}://{p.netloc.lower()}{p.path}"
    return url


# ---------------------------------------------------------------- 链接卡片解析

def parse_appmsg(content):
    """解析微信链接卡片 XML，拿到标题/摘要/链接。"""
    if not content or "<appmsg" not in content:
        return None
    text = content
    # 有些记录里的 XML 没有根节点，或者 & 未转义
    candidates = [text]
    if "<msg>" not in text:
        candidates.insert(0, "<root>" + text + "</root>")
    for cand in candidates:
        try:
            root = ET.fromstring(cand)
        except ET.ParseError:
            continue
        title = (root.findtext(".//title") or "").strip()
        des = (root.findtext(".//des") or root.findtext(".//digest") or "").strip()
        url = (root.findtext(".//url") or "").strip()
        if not url:
            u = root.find(".//url")
            if u is not None and u.text:
                url = u.text.strip()
        if url:
            return {"title": title, "note": des, "url": url}
    return None


# ---------------------------------------------------------------- 逐行解析

def parse_line(line, author=""):
    """解析一行，返回条目列表（一行可能夹多个链接）。"""
    items = []
    content = line.strip()
    if not content:
        return items

    # 1. 链接卡片：标题和摘要都是现成的
    card = parse_appmsg(content)
    if card:
        items.append({
            "title": card["title"][:80] or "未命名",
            "url": card["url"],
            "kind": classify(card["url"]),
            "note": card["note"][:300],
            "author": author,
            "origin": "card",
        })
        return items

    # 2. 纯文本里夹着链接
    for m in URL_RE.finditer(content):
        url = m.group(0).rstrip(TRAIL_PUNCT)
        if len(url) < 12:
            continue
        before = clean_text(content[: m.start()])
        after = clean_text(content[m.end():])
        book = re.search(r"\u300a([^\u300b]{1,80})\u300b", before)
        if book:
            title = book.group(1).strip()
        elif before:
            title = before[:40]
        else:
            title = "未命名"
        items.append({
            "title": title,
            "url": url,
            "kind": classify(url),
            "note": after[:300],
            "author": author,
            "origin": "text",
        })
    return items


def parse_text(text, author=""):
    """逐行解析整份投喂文件，按规范化 URL 去重。"""
    items, seen = [], set()
    for line in HTML_COMMENT.sub("", text).splitlines():
        for it in parse_line(line, author):
            key = norm_url(it["url"])
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    return items


def fetch_inbox(path):
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"投喂文件不存在：{p}")
    text = p.read_text(encoding="utf-8", errors="ignore")
    m = AUTHOR_TAG.search(text)
    author = m.group(1).strip() if m else ""
    return parse_text(text, author=author)


# ---------------------------------------------------------------- 输出

def to_markdown(items, title, date_str):
    cats = {"channels": "视频号", "article": "公众号", "web": "网页"}
    order = ["channels", "article", "web"]
    buckets = {k: [] for k in order}
    for it in items:
        buckets.setdefault(it["kind"], []).append(it)

    out = [f"# {title} · {date_str}", ""]
    summary = " · ".join(f"{cats[k]} {len(buckets[k])}" for k in order if buckets.get(k))
    out.append(f"> {len(items)} 条 · {summary}")
    out.append("")

    if not items:
        out.append("_没有采集到内容。_")
        return "\n".join(out) + "\n"

    idx = 0
    for k in order:
        group = buckets.get(k) or []
        if not group:
            continue
        out.append(f"## {cats[k]}")
        out.append("")
        for it in group:
            idx += 1
            out.append(f"### {idx}. {it['title']}")
            out.append("")
            if it["author"]:
                out.append(f"- **来源**：{it['author']}")
            if it["note"]:
                out.append(f"- **摘要**：{it['note']}")
            out.append(f"- **链接**：<{it['url']}>")
            out.append("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="解析投喂文件里的资讯链接")
    ap.add_argument("--path", default="./inbox.md", help="投喂文件路径")
    ap.add_argument("--format", choices=["json", "markdown"], default="json")
    ap.add_argument("--out", default="", help="输出文件，留空打印到屏幕")
    ap.add_argument("--title", default="", help="markdown 模式的标题")
    args = ap.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        items = fetch_inbox(args.path)
    except RuntimeError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    if args.format == "markdown":
        body = to_markdown(items, args.title or Path(args.path).stem, date_str)
    else:
        body = json.dumps({
            "source": "inbox",
            "path": str(args.path),
            "date": date_str,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(items),
            "items": items,
        }, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"已写入 {args.out}（{len(items)} 条）", file=sys.stderr)
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
