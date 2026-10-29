# -*- coding: utf-8 -*-
"""验证 publish.py 的命名与同名冲突处理，不写用户的真实目录（用临时目录）。"""
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "publish", Path(__file__).parent / "publish.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# ---------------------------------------------------------------- 标题简写
print("=== 标题简写 ===")
TITLE_CASES = [
    ("六大具身路线详解：模块化、技能编排、IL、RL、VLA、世界模型，到底在“吵”什么", "六大具身路线详解"),
    ("DeepSeek 发布 V4.1 —— 推理成本下降 80%", "DeepSeek 发布 V4.1"),
    ("A/B 测试：模型上线后 CTR 提升 <5> | 复盘", "AB 测试"),
    ("《具身智能白皮书》", "具身智能白皮书"),
]
title_ok = True
for raw, expect in TITLE_CASES:
    got = mod.short_title(raw)
    passed = got == expect
    title_ok = title_ok and passed
    print(f"{'PASS' if passed else 'FAIL'}  {got!r}  (期望 {expect!r})")

# ---------------------------------------------------------------- 同名冲突
tmp = Path(tempfile.mkdtemp(prefix="pubtest_"))
dest = tmp / "资讯精读" / "2026"
dest.mkdir(parents=True)

A = "# 大模型周报：10 月第一周\n\n**原文**：<https://mp.weixin.qq.com/s/aaa>\n\n第一篇正文。\n"
A_REV = A + "\n补了一段修订。\n"
B = "# 大模型周报：10 月第二周\n\n**原文**：<https://mp.weixin.qq.com/s/bbb>\n\n完全不同的第二篇。\n"
C = "# 大模型周报：10 月第三周\n\n**原文**：<https://mp.weixin.qq.com/s/ccc>\n\n第三篇。\n"
NAME = "大模型周报"


def plan(text, stamp):
    return mod.plan_dest(dest, NAME, text, text.encode("utf-8"), stamp)


print("\n=== 同名冲突处理 ===")
cases = []

# 1. 首篇 → 用标题简写
p, action = plan(A, "2026-10-29")
cases.append(("首篇用标题简写", action == "new" and p.name == "大模型周报.md"))
p.write_bytes(A.encode("utf-8"))

# 2. 同内容重跑 → 幂等
p, action = plan(A, "2026-10-30")
cases.append(("同内容重跑跳过", action == "same" and p.name == "大模型周报.md"))

# 3. 同一篇（原文链接相同）改稿 → 覆盖原文件
p, action = plan(A_REV, "2026-10-31")
cases.append(("同链接改稿覆盖", action == "update" and p.name == "大模型周报.md"))

# 4. 不同文章撞同一个主标题 → 另存，不覆盖
p, action = plan(B, "2026-10-29")
cases.append(("撞名另存不覆盖", action == "conflict" and p.name == "大模型周报-2026-10-29.md"))
p.write_bytes(B.encode("utf-8"))

# 5. 第二篇自己再同步一次 → 认得出是同一篇
p, action = plan(B, "2026-11-02")
cases.append(("另存后仍可识别同一篇", action == "update" and p.name == "大模型周报-2026-10-29.md"))

# 6. 第三篇也撞名且同一天 → 加序号，仍不覆盖
p, action = plan(C, "2026-10-29")
cases.append(("同一天第三次撞名加序号", action == "conflict" and p.name == "大模型周报-2026-10-29-2.md"))

conflict_ok = True
for name, passed in cases:
    print(f"{'PASS' if passed else 'FAIL'}  {name}")
    conflict_ok = conflict_ok and passed

print("\n=== 落盘结果 ===")
for f in sorted(dest.iterdir()):
    print(f"  {f.name}  ({f.stat().st_size} 字节)")
first = (dest / "大模型周报.md").read_text(encoding="utf-8")
print(f"  原文件名内容是否仍是第一篇: {first == A}")

shutil.rmtree(tmp, ignore_errors=True)

ok = title_ok and conflict_ok and first == A
print(f"\n总计：{'全部通过' if ok else '有失败项'}")
sys.exit(0 if ok else 1)
