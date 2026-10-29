#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号正文抓取：给链接，拿到标题、公众号名、发布时间和正文纯文本，
交给 AI 做内容浓缩。

只用标准库，不需要 Playwright 或浏览器。

用法：
    python fetch_articles.py --url "https://mp.weixin.qq.com/s/xxx"
    python fetch_articles.py --url "https://..." --out state/articles/2026-10-29
    python fetch_articles.py --from-json items.json --out state/articles/2026-10-29
    python fetch_articles.py --url "https://..." --format text
"""

import argparse
import hashlib
import html as htmlmod
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BLOCK_END = re.compile(r"</(p|section|div|h[1-6]|li|blockquote|tr)\s*>|<br\s*/?>", re.I)
TAG = re.compile(r"<[^>]+>")
SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def http_get(url, timeout=25):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = "utf-8"
        ctype = resp.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            charset = m.group(1)
        return raw.decode(charset, errors="ignore")


def strip_tags(fragment):
    """把 HTML 片段转成保留段落的纯文本。"""
    frag = SCRIPT_STYLE.sub(" ", fragment)
    frag = BLOCK_END.sub("\n", frag)
    frag = TAG.sub("", frag)
    frag = htmlmod.unescape(frag)
    frag = frag.replace("\u200b", "").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in frag.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def first_match(patterns, text, flags=re.S):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            val = strip_tags(m.group(1)).strip()
            if val:
                return val
    return ""


def fetch_article(url):
    result = {
        "url": url,
        "title": "",
        "account": "",
        "publish_time": "",
        "chars": 0,
        "ok": False,
        "error": "",
        "text": "",
    }

    try:
        page = http_get(url)
    except (HTTPError, URLError, OSError) as e:
        result["error"] = f"请求失败：{type(e).__name__}: {e}"
        return result

    if "环境异常" in page or "去验证" in page:
        result["error"] = "被微信风控拦截（环境异常），需要降低频率或改用浏览器抓取"
        return result
    if "该内容已被发布者删除" in page or "此内容因违规无法查看" in page:
        result["error"] = "文章已删除或不可访问"
        return result

    result["title"] = first_match([
        r'id="activity-name"[^>]*>(.*?)</',
        r'<h1[^>]*class="[^"]*rich_media_title[^"]*"[^>]*>(.*?)</h1>',
        r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"',
    ], page)

    result["account"] = first_match([
        r'id="js_name"[^>]*>(.*?)</',
        r'class="[^"]*rich_media_meta_nickname[^"]*"[^>]*>(.*?)</',
        r'<meta[^>]*property="og:article:author"[^>]*content="([^"]*)"',
    ], page)

    result["publish_time"] = first_match([
        r'id="publish_time"[^>]*>(.*?)</',
        r'<em[^>]*id="publish_time"[^>]*>(.*?)</em>',
        r'var\s+ct\s*=\s*"(\d{10})"',
    ], page)

    # 有些页面只给 Unix 时间戳，转成日期
    if re.fullmatch(r"\d{10}", result["publish_time"] or ""):
        try:
            result["publish_time"] = datetime.fromtimestamp(
                int(result["publish_time"])
            ).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass

    body = ""
    for pat in (
        r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*<script',
        r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*</div>',
        r'<div[^>]*class="[^"]*rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script',
    ):
        m = re.search(pat, page, re.S)
        if m and len(m.group(1)) > 200:
            body = m.group(1)
            break

    if not body:
        result["error"] = "没找到正文块（可能是图片消息、视频或新版页面结构）"
        return result

    text = strip_tags(body)
    # 去掉正文里重复的标题行
    if result["title"] and text.startswith(result["title"]):
        text = text[len(result["title"]):].lstrip("\n")

    result["text"] = text
    result["chars"] = len(text)
    result["ok"] = len(text) >= 80
    if not result["ok"]:
        result["error"] = f"正文过短（{len(text)} 字），可能是图片型内容"
    return result


def load_urls(args):
    urls = []
    if args.url:
        urls.append(args.url)
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        items = data.get("items", data) if isinstance(data, dict) else data
        for it in items:
            if isinstance(it, dict) and it.get("url"):
                urls.append(it["url"])
            elif isinstance(it, str):
                urls.append(it)
    # 去重保序
    seen, out = set(), []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="", help="单个链接")
    ap.add_argument("--from-json", default="", help="从 JSON 读多个链接（支持 items 数组）")
    ap.add_argument("--out", default="", help="输出目录，逐篇存 .json + .txt")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    ap.add_argument("--min-chars", type=int, default=80)
    args = ap.parse_args()

    urls = load_urls(args)
    if not urls:
        ap.error("需要 --url 或 --from-json")

    results = []
    for i, u in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] 抓取 {u}", file=sys.stderr)
        r = fetch_article(u)
        status = f"OK {r['chars']} 字" if r["ok"] else f"失败：{r['error']}"
        print(f"          {status}", file=sys.stderr)
        results.append(r)

    if args.out:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        for r in results:
            if not r["ok"]:
                continue
            slug = hashlib.md5(r["url"].encode()).hexdigest()[:10]
            (outdir / f"{slug}.txt").write_text(r["text"], encoding="utf-8")
            meta = {k: v for k, v in r.items() if k != "text"}
            (outdir / f"{slug}.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        summary = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(results),
            "ok": sum(1 for r in results if r["ok"]),
            "outdir": str(outdir),
            "articles": [{k: v for k, v in r.items() if k != "text"} for r in results],
        }
        (outdir / "_index.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n已写入 {outdir}（成功 {summary['ok']}/{summary['total']}）", file=sys.stderr)

    if args.format == "text":
        for r in results:
            print("=" * 60)
            print(f"标题：{r['title']}")
            print(f"公众号：{r['account']}　发布：{r['publish_time']}")
            print(f"链接：{r['url']}")
            print("-" * 60)
            print(r["text"] if r["ok"] else f"[抓取失败] {r['error']}")
            print()
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 0 if any(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
