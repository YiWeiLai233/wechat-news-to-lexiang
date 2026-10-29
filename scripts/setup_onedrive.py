#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置 OneDrive 输出位置。

用法：
    python setup_onedrive.py                      # 交互式，一步一步问
    python setup_onedrive.py --check              # 只看当前配置
    python setup_onedrive.py --path "C:\\Users\\你\\OneDrive\\知识库"
    python setup_onedrive.py --path "..." --subdir "资讯精读"
    python setup_onedrive.py --reset              # 清空，只写本地 output
"""

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"


def load():
    """读配置；首次使用没有 config.json 时，自动从模板生成一份。"""
    if not CONFIG_PATH.exists():
        if not EXAMPLE_PATH.exists():
            sys.exit(f"缺少 config.json，也没找到 config.example.json（应在 {ROOT}）")
        CONFIG_PATH.write_text(
            EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print(f"首次运行：已从 config.example.json 生成 {CONFIG_PATH}\n")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save(cfg):
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def show(cfg):
    raw = (cfg.get("onedrive_dir") or "").strip()
    sub = (cfg.get("onedrive_subdir") or "").strip()
    print(f"onedrive_dir     : {raw or '(未设置)'}")
    print(f"onedrive_subdir  : {sub or '(未设置)'}")
    if raw:
        target = Path(raw) / sub if sub else Path(raw)
        print(f"实际落盘目录     : {target}")
        print(f"目录是否存在     : {'是' if target.exists() else '否（首次写入时会自动创建）'}")
        exists_parent = target if target.exists() else target.parent
        print(f"上级目录可写     : {'是' if exists_parent.exists() else '否'}")
    else:
        print("实际落盘目录     : 未设置，只写本地 output/资讯精读/")
    print()
    print(f"lexiang_enabled  : {cfg.get('lexiang_enabled')}")
    print(f"乐享目录         : {cfg.get('lexiang_folder')}")


def looks_like_onedrive(p):
    return "onedrive" in str(p).lower() or "sharepoint" in str(p).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只看当前配置")
    ap.add_argument("--path", default="", help="新的 OneDrive 目录")
    ap.add_argument("--subdir", default="", help="子目录名")
    ap.add_argument("--reset", action="store_true", help="清空配置，只写本地")
    args = ap.parse_args()

    cfg = load()

    if args.check:
        show(cfg)
        return 0

    if args.reset:
        cfg["onedrive_dir"] = ""
        save(cfg)
        print("已清空 onedrive_dir，之后只写本地 output/资讯精读/")
        return 0

    new_path = args.path
    new_sub = args.subdir

    if not new_path:
        print("当前配置：")
        show(cfg)
        print("-" * 50)
        print("直接回车保持原值。路径可以粘贴资源管理器地址栏里复制的那串。")
        try:
            entered = input("OneDrive 目录（如 C:\\Users\\你\\OneDrive\\知识库）: ").strip()
            sub_entered = input(f"子目录名（回车保持 {cfg.get('onedrive_subdir') or '资讯精读'}）: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return 1
        if entered:
            new_path = entered
        if sub_entered:
            new_sub = sub_entered

    if new_path:
        p = Path(new_path.strip().strip('"').strip("'"))
        if not looks_like_onedrive(p):
            print(f"\n提醒：这个路径里没有 onedrive/sharepoint 字样，确认它不是普通本地目录？")
            print(f"      如果只是想放本地，这样也可以，只是不会自动同步到云端。")
        if not p.exists():
            print(f"\n目录不存在：{p}")
            try:
                ans = input("要现在创建吗？(Y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans in ("", "y", "yes"):
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    print(f"已创建：{p}")
                except OSError as e:
                    print(f"创建失败：{e}")
                    return 1
            else:
                print("已取消，配置未修改")
                return 1
        cfg["onedrive_dir"] = str(p)

    if new_sub:
        cfg["onedrive_subdir"] = new_sub.strip()

    save(cfg)
    print("\n已保存。新配置：")
    show(cfg)
    print("\n下次运行 publish.py 或定时任务时生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
