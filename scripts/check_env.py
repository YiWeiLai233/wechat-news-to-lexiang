#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首次安装后的环境自检。

本地能查的全部查掉：配置是否存在、OneDrive 目录在不在、能不能写。
乐享连接器只能在 agent 侧验证（脚本碰不到 MCP），所以这里只核对配置，
并在结尾明确提示下一步该调哪个工具。

用法：
    python scripts/check_env.py             # 人看的报告
    python scripts/check_env.py --json      # 机器读，字段见输出
    python scripts/check_env.py --mkdir     # OneDrive 目标目录不存在时顺手建出来

退出码：
    0 = 可以跑（允许带警告，例如没配 OneDrive 就只写本地）
    1 = 有阻断问题，先修再跑
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"

OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"


class Report:
    def __init__(self):
        self.items = []
        self.blocking = 0

    def add(self, section, status, message, hint=""):
        self.items.append(
            {"section": section, "status": status, "message": message, "hint": hint}
        )
        if status == FAIL:
            self.blocking += 1

    def dump(self):
        icon = {OK: "[OK]  ", WARN: "[!]   ", FAIL: "[X]   ", SKIP: "[-]   "}
        cur = None
        for it in self.items:
            if it["section"] != cur:
                cur = it["section"]
                print(f"\n{cur}")
                print("-" * max(12, len(cur) * 2))
            print(f"  {icon[it['status']]}{it['message']}")
            if it["hint"]:
                for line in it["hint"].splitlines():
                    print(f"        {line}")
        print()
        block = [i for i in self.items if i["status"] == FAIL]
        warn = [i for i in self.items if i["status"] == WARN]
        if block:
            print(f"结论：有 {len(block)} 个阻断问题，先修再跑。")
        elif warn:
            print(f"结论：可以跑，有 {len(warn)} 处需要跟用户确认。")
        else:
            print("结论：全部就绪。")


def check_python(r):
    v = sys.version_info
    s = f"Python {v.major}.{v.minor}.{v.micro}"
    if v < (3, 9):
        r.add("Python", FAIL, f"{s}（需要 3.9+）", "升级 Python 后再试")
    else:
        r.add("Python", OK, s)


def check_config(r):
    created = False
    if not CONFIG_PATH.exists():
        if not EXAMPLE_PATH.exists():
            r.add("配置文件", FAIL, "config.json 和 config.example.json 都不在", "技能包不完整，重新解压")
            return None
        CONFIG_PATH.write_text(EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        created = True
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        r.add("配置文件", FAIL, f"config.json 解析失败：{e}", "检查 JSON 格式，或删掉重新生成")
        return None
    if created:
        r.add(
            "配置文件",
            WARN,
            f"原来没有 config.json，已从模板生成：{CONFIG_PATH}",
            "此时所有可选项都是默认值，需要逐项跟用户确认（见下）",
        )
    else:
        r.add("配置文件", OK, f"config.json 可读（{CONFIG_PATH}）")
    return cfg


def try_write(d, create=False):
    """在目录里真写一个临时文件，比 os.access 可靠。

    create=False 时不会新建目录，避免「报不存在却顺手建出来」。
    """
    try:
        if create:
            d.mkdir(parents=True, exist_ok=True)
        if not d.exists():
            return False, "目录不存在"
        with tempfile.NamedTemporaryFile(dir=str(d), prefix=".wbtest_", delete=True):
            pass
        return True, ""
    except Exception as e:
        return False, str(e)


def onedrive_roots():
    """从环境变量拿本机 OneDrive 同步根，比路径里有没有 'onedrive' 字样可靠。"""
    roots = []
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        v = os.environ.get(key)
        if v and Path(v).exists():
            roots.append(Path(v))
    return roots


def check_onedrive(r, cfg, mkdir):
    raw = ((cfg or {}).get("onedrive_dir") or "").strip()
    sub = ((cfg or {}).get("onedrive_subdir") or "资讯精读").strip()

    if not raw:
        r.add(
            "OneDrive",
            WARN,
            "onedrive_dir 未配置 —— 精读稿只会写到本地 output/",
            "要归档到 OneDrive 就问用户拿同步目录路径，然后跑：\n"
            'python scripts/setup_onedrive.py --path "C:\\Users\\他\\OneDrive\\某个目录"',
        )
        return

    base = Path(raw)
    target = base / sub if sub else base
    year_dir = target / str(date.today().year)

    if not base.exists():
        if mkdir:
            ok, err = try_write(base, create=True)
            if not ok:
                r.add("OneDrive", FAIL, f"目录建不出来：{base}", f"原因：{err}\n换一个有写权限的目录")
                return
            r.add("OneDrive", OK, f"基线目录原来不存在，已创建：{base}")
        else:
            r.add(
                "OneDrive",
                FAIL,
                f"目录不存在：{base}",
                "1) 确认用户是不是装了 OneDrive 客户端、用哪个账号登录\n"
                "2) 路径写错就重配：python scripts/setup_onedrive.py\n"
                "3) 想把技能目录建在这个路径下，加 --mkdir 即可新建\n"
                "4) 只想要本地目录也可以，改用任意可写文件夹",
            )
            return
    else:
        r.add("OneDrive", OK, f"基线目录存在：{base}")

    if not target.exists():
        if mkdir:
            ok, err = try_write(target, create=True)
            if ok:
                r.add("OneDrive", OK, f"已创建目标目录：{target}")
            else:
                r.add("OneDrive", FAIL, f"创建目录失败：{err}")
                return
        else:
            r.add(
                "OneDrive",
                WARN,
                f"子目录还不存在：{target}",
                "第一次同步会自动创建，不用手动建；想现在建就加 --mkdir",
            )
    else:
        r.add("OneDrive", OK, f"子目录存在：{target}")

    probe = target if target.exists() else base
    ok, err = try_write(probe)
    if ok:
        r.add("OneDrive", OK, f"可写，今年落盘位置：{year_dir}")
    else:
        r.add("OneDrive", FAIL, f"目录不可写：{err}", "换一个有写权限的目录，或以管理员身份重试")

    # 确认这个目录真的在 OneDrive 同步范围内
    roots = onedrive_roots()
    inside = None
    try:
        for rt in roots:
            base.resolve().relative_to(rt.resolve())
            inside = rt
            break
    except Exception:
        pass
    if inside:
        r.add("OneDrive", OK, f"在 OneDrive 同步根下：{inside}")
    elif roots:
        r.add(
            "OneDrive",
            WARN,
            f"不在任何 OneDrive 同步根下（本机同步根：{roots[0]}）",
            "文件会写进普通本地目录，不会上云。确认用户是想这样，还是要换到同步目录里",
        )
    else:
        r.add(
            "OneDrive",
            WARN,
            "本机没检测到 OneDrive 同步根（环境变量为空）",
            "可能没装客户端或没登录。问用户是否接受「只存本地」",
        )


def check_lexiang(r, cfg):
    if cfg is None:
        r.add("乐享知识库", SKIP, "配置读不到，跳过")
        return
    enabled = cfg.get("lexiang_enabled")
    space = (cfg.get("lexiang_space_id") or "").strip()
    folder = (cfg.get("lexiang_folder") or "每日资讯").strip()

    if not enabled:
        r.add(
            "乐享知识库",
            WARN,
            "lexiang_enabled = false —— 不会上传知识库",
            "用户想传就改成 true，并确认连接器已授权",
        )
        return

    r.add("乐享知识库", OK, f"已启用，目录「{folder}」，下面按 YYYY-MM 分月")
    if space:
        r.add("乐享知识库", OK, f"space_id 已固化：{space}（不用每次查）")
    else:
        r.add(
            "乐享知识库",
            WARN,
            "space_id 留空 —— 会自动选账号下第一个可写知识库",
            "很可能是他的个人库。要传团队库就必须问清是哪个，再把 ID 填进去",
        )
    r.add(
        "乐享知识库",
        SKIP,
        "连接器授权状态脚本查不到，需要 agent 侧调用 whoami 确认",
        "调 mcp__lexiang__whoami：返回用户信息=已授权；401=让用户去连接器里续期",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON，便于程序解析")
    ap.add_argument("--mkdir", action="store_true", help="OneDrive 目标目录不存在时自动创建")
    args = ap.parse_args()

    r = Report()
    check_python(r)
    cfg = check_config(r)
    check_onedrive(r, cfg, args.mkdir)
    check_lexiang(r, cfg)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": r.blocking == 0,
                    "blocking": r.blocking,
                    "items": r.items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        r.dump()
    return 0 if r.blocking == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
