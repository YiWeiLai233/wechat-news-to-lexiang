#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把精读稿同步到 OneDrive 目标目录。

一篇一个 md，文件名用「文章标题简写」——从正文 H1 自动提取，也可以用
--title 手动指定简写。落盘结构：

    <onedrive_dir>\\<onedrive_subdir>\\<年份>\\<标题简写>.md

同名冲突怎么处理：
    1. 原文链接相同       → 同一篇文章改过稿，覆盖旧版
    2. 内容完全一致       → 幂等重跑，跳过
    3. 链接不同、内容不同 → 不同文章撞了同一个主标题，另存为
                           <标题简写>-<日期>.md，不覆盖已有文章

第 3 条是重点：标题简写只取冒号前的主标题，撞名很常见（比如系列周报），
直接覆盖会静默丢文章。

用法：
    # 单篇，标题从 md 的 H1 自动取
    python publish.py --src output/资讯精读/2026/六大具身路线详解.md

    # 单篇，手动给标题简写（H1 太长或想统一命名时用）
    python publish.py --src output/资讯精读/2026/xxx.md --title "六大具身路线"

    # 批量，把目录下所有 md 一次同步
    python publish.py --dir output/资讯精读/2026

    python publish.py --src xxx.md --dry-run     # 只看目标路径
    python publish.py --check                    # 只看配置
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"

# Windows 文件名非法字符 + 控制字符
ILLEGAL = r'[<>:"/\\|?*\x00-\x1f]'
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DATE_ONLY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# 标题里用来切出「主标题」的分隔符：全角冒号、破折号、竖线、带空格连字符
SPLIT_RE = re.compile(r"[：:\uFF5C|\u2014\u2013]+|\s+-\s+|\s+--\s+")
URL_RE = re.compile(
    r"https?://[^\s<>\"'\uFF08\uFF09\u300A\u300B\u3002\uFF0C\uFF1B\uFF1A\uFF01\uFF1F]+"
)
TRAIL_PUNCT = ".,;:!?)）】》\"'、。，；：！？"

ACTION_LABEL = {
    "new": "已同步",
    "update": "已更新（同一篇，覆盖旧版）",
    "same": "跳过（内容一致）",
    "conflict": "已另存（同名不同文，加日期后缀）",
}


def load_config():
    """读配置；首次使用没有 config.json 时，自动从模板生成一份。"""
    if not CONFIG_PATH.exists():
        if not EXAMPLE_PATH.exists():
            sys.exit(f"缺少 config.json，也没找到 config.example.json（应在 {ROOT}）")
        CONFIG_PATH.write_text(
            EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print(
            f"首次运行：已从 config.example.json 生成 {CONFIG_PATH}\n"
            f"          跑一遍 setup_onedrive.py 可以设置输出目录。",
            file=sys.stderr,
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def base_dir(cfg):
    """<onedrive_dir>/<onedrive_subdir>，未配置返回 None。"""
    raw = (cfg.get("onedrive_dir") or "").strip()
    if not raw:
        return None
    base = Path(raw)
    sub = (cfg.get("onedrive_subdir") or "资讯精读").strip()
    return base / sub if sub else base


def resolve_dest(cfg, year):
    b = base_dir(cfg)
    return None if b is None else b / year


def extract_title(text):
    """取正文第一个 H1；没有 H1 就取第一行非空内容。"""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s.lstrip("#").strip()
    return ""


def short_title(raw, maxlen=50):
    """把标题压成适合作文件名的简写。

    规则（可预测优先，不做语义猜测）：
      1. 去 markdown 标记与书名号
      2. 冒号 / 破折号之后的副标题丢掉，只留主标题
      3. 去掉 Windows 非法字符，压缩空白
      4. 超过 maxlen 字截断
    """
    t = raw.strip()
    t = re.sub(r"^#+\s*", "", t)
    t = re.sub(r"\*\*|__|`", "", t)
    t = t.replace("《", "").replace("》", "")
    t = SPLIT_RE.split(t)[0]
    t = re.sub(ILLEGAL, "", t)
    t = re.sub(r"\s+", " ", t).strip(" .。、，,")
    if len(t) > maxlen:
        t = t[:maxlen].rstrip(" .。、，,")
    return t or "未命名"


def norm_url(u):
    """比对用的链接规范形：微信链接的 query 全是来源追踪参数，去掉。"""
    u = u.rstrip(TRAIL_PUNCT)
    if "weixin.qq.com" in u:
        u = u.split("#")[0].split("?")[0]
    return u


def extract_urls(text):
    return {norm_url(m) for m in URL_RE.findall(text or "")}


def file_urls(p):
    try:
        return extract_urls(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return set()


def doc_date(text, src, fallback=None):
    """给冲突后缀用的日期：正文里的首个日期 → 源文件名日期 → 今天。"""
    m = DATE_RE.search((text or "")[:800])
    if m:
        return m.group(0)
    m = DATE_RE.search(Path(src).name)
    if m:
        return m.group(0)
    return fallback or date.today().isoformat()


def same_slug(p, name):
    """判断 p 是不是 name 这个标题派生出来的文件（name.md / name-xxx.md / name (2).md）。"""
    stem = p.stem
    return stem == name or stem.startswith(name + "-") or stem.startswith(name + " (")


def candidates(dest_dir, name):
    if not dest_dir.is_dir():
        return []
    return sorted(
        p for p in dest_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md" and same_slug(p, name)
    )


def plan_dest(dest_dir, name, text, src_bytes, stamp):
    """决定写到哪个文件，返回 (路径, 动作)。

    动作：new / update（同一篇改稿）/ same（内容一致）/ conflict（同名不同文）
    """
    base = dest_dir / f"{name}.md"
    existing = candidates(dest_dir, name)

    # 1. 原位置内容一字不差 → 幂等，不动文件
    if base.exists():
        try:
            if base.read_bytes() == src_bytes:
                return base, "same"
        except OSError:
            pass

    # 2. 原文链接相同 → 同一篇文章改过稿，覆盖它（包括上次因撞名另存出去的那份）
    src_urls = extract_urls(text)
    if src_urls:
        for p in existing:
            if src_urls & file_urls(p):
                return p, "update"

    # 3. 原位置空着 → 直接用标题简写
    if not base.exists():
        return base, "new"

    # 4. 同名不同文 → 加日期后缀，再撞就加序号
    for i in range(1, 100):
        cand = dest_dir / (f"{name}-{stamp}.md" if i == 1 else f"{name}-{stamp}-{i}.md")
        if not cand.exists():
            return cand, "conflict"
        try:
            if cand.read_bytes() == src_bytes:
                return cand, "same"
        except OSError:
            continue
    return dest_dir / f"{name}-{stamp}-99.md", "conflict"


def guess_year(src, explicit=""):
    """年份：--date 优先，其次源文件名里的日期，最后取今天。"""
    if explicit:
        return explicit[:4]
    m = DATE_RE.search(Path(src).name)
    return m.group(1) if m else str(date.today().year)


def publish_one(cfg, src, title=None, year="", dry_run=False, quiet=False):
    """同步单个 md，返回 (状态, 目标路径, 动作)。状态：ok / same / fail。"""
    src = Path(src)
    try:
        src_bytes = src.read_bytes()
    except OSError as e:
        return "fail", None, f"读不到源文件：{e}"
    text = src_bytes.decode("utf-8", errors="replace")
    name = short_title(title or extract_title(text) or src.stem)
    dest_dir = resolve_dest(cfg, year or guess_year(src))
    if dest_dir is None:
        return "fail", None, "onedrive_dir 未配置"

    dest, action = plan_dest(dest_dir, name, text, src_bytes, doc_date(text, src))

    if dry_run:
        print(f"[dry-run] {src.name}  ->  {dest.name}  （{ACTION_LABEL[action]}）")
        return ("same" if action == "same" else "ok"), dest, action

    if action != "same":
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    if not quiet:
        print(f"{ACTION_LABEL[action]}：{dest}")
    return ("same" if action == "same" else "ok"), dest, action


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="", help="源 md 文件")
    ap.add_argument("--dir", default="", help="源目录，批量同步其中所有 .md")
    ap.add_argument("--title", default="", help="手动指定标题简写（单篇时用）")
    ap.add_argument("--date", default="", help="归档日期 YYYY-MM-DD，默认从文件名取或今天")
    ap.add_argument("--check", action="store_true", help="只检查目标目录配置")
    ap.add_argument("--dry-run", action="store_true", help="只打印目标路径，不复制")
    args = ap.parse_args()

    cfg = load_config()

    if args.check:
        raw = (cfg.get("onedrive_dir") or "").strip()
        sub = (cfg.get("onedrive_subdir") or "").strip()
        print(f"onedrive_dir  = {raw or '(未配置，只写本地 output)'}")
        print(f"onedrive_subdir = {sub}")
        if raw:
            target = Path(raw) / sub if sub else Path(raw)
            print(f"实际落盘目录 = {target}")
            print(f"目录存在     = {target.exists() or target.parent.exists()}")
            parent = target.parent if not target.exists() else target
            print(f"父目录可写   = {parent.exists() and parent.is_dir()}")
        print("文件命名     = <标题简写>.md（一篇一个文件）")
        print("同名处理     = 同一篇改稿覆盖；不同文章撞名则存为 <标题简写>-<日期>.md")
        print()
        print(f"lexiang_enabled = {cfg.get('lexiang_enabled')}")
        print(f"lexiang_folder  = {cfg.get('lexiang_folder')}")
        print(f"lexiang_space_id = {cfg.get('lexiang_space_id') or '(自动选第一个可写库)'}")
        return 0

    if not args.src and not args.dir:
        ap.error("需要 --src、--dir 或 --check")

    # 收集待同步文件
    if args.dir:
        d = Path(args.dir)
        if not d.is_absolute():
            d = ROOT / d
        if not d.is_dir():
            print(f"目录不存在：{d}", file=sys.stderr)
            return 1
        files = []
        for p in sorted(d.glob("*.md")):
            if p.name.startswith("_"):
                continue
            # 旧版「一天一份合并日报」的命名是纯日期，别当成单篇文章同步
            if DATE_ONLY_RE.fullmatch(p.stem):
                print(f"  跳过旧版合并日报：{p.name}（一篇一文件后不再同步）", file=sys.stderr)
                continue
            files.append(p)
        if not files:
            print(f"目录里没有可同步的 .md：{d}", file=sys.stderr)
            return 1
    else:
        src = Path(args.src)
        if not src.is_absolute():
            src = ROOT / src
        if not src.exists():
            print(f"源文件不存在：{src}", file=sys.stderr)
            return 1
        files = [src]

    if base_dir(cfg) is None:
        print("onedrive_dir 未配置，跳过同步（只保留本地副本）", file=sys.stderr)
        return 0

    batch = len(files) > 1
    ok = same = failed = 0
    for f in files:
        status, info, action = publish_one(
            cfg,
            f,
            title=args.title if not batch else "",
            year=guess_year(f, args.date),
            dry_run=args.dry_run,
            quiet=batch,
        )
        if status == "ok":
            ok += 1
            if batch:
                tag = {"new": "新增", "update": "更新", "conflict": "另存"}.get(action, "写入")
                print(f"  [{tag}] {'[dry-run] ' if args.dry_run else ''}{Path(info).name}  <-  {f.name}")
        elif status == "same":
            same += 1
            if batch:
                print(f"  [跳过] {f.name}：内容已一致")
        else:
            failed += 1
            print(f"  失败 {f.name}：{action}", file=sys.stderr)

    if batch or same or failed:
        print()
        if batch:
            print(f"共 {len(files)} 篇：成功 {ok}，内容一致跳过 {same}，失败 {failed}")
        elif same:
            print("全部内容已一致，没有文件被改动。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
