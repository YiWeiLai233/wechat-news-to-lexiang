# -*- coding: utf-8 -*-
"""验证 collect.py 的投喂文件解析逻辑，不依赖任何外部服务。"""
import importlib.util
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "collect", Path(__file__).parent / "collect.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE = """<!-- 投喂人：我 -->
<msg><appmsg appid="" sdkver="0"><title>半年增长复盘：从 0 到 1 的完整路径</title><des>数据很扎实，方法可复用</des><type>5</type><url><![CDATA[https://mp.weixin.qq.com/s/abc123]]></url></appmsg></msg>
<msg><appmsg><title>视频：AI 记忆机制到底怎么回事</title><url>https://weixin.qq.com/sph/xyz789</url></appmsg></msg>
1. 这个也不错 https://mp.weixin.qq.com/s/plain001 值得一看
推荐语：《具身智能白皮书》 https://mp.weixin.qq.com/s/book002 讲得很全
<msg><appmsg><title>半年增长复盘（转）</title><url>https://mp.weixin.qq.com/s/abc123?chksm=deadbeef</url></appmsg></msg>
"""

items = mod.parse_text(SAMPLE, author="我")

print(f"条目数: {len(items)}\n")
print("=== 解析结果 ===")
for it in items:
    print(f"[{it['kind']:8}] {it['title']}")
    print(f"           note={it['note'] or '(空)'}")
    print(f"           url={it['url']}  origin={it['origin']}")

print("\n=== 断言 ===")
checks = [
    ("卡片标题解析", any(i["title"] == "半年增长复盘：从 0 到 1 的完整路径" for i in items)),
    ("卡片摘要解析", any(i["note"] == "数据很扎实，方法可复用" for i in items)),
    ("视频号分类", any(i["kind"] == "channels" for i in items)),
    ("纯文本解析", any(i["origin"] == "text" and "plain001" in i["url"] for i in items)),
    ("列表序号被清掉", any(i["title"] == "这个也不错" for i in items)),
    ("书名号取标题", any(i["title"] == "具身智能白皮书" for i in items)),
    ("重复链接去重", len([i for i in items if "abc123" in i["url"]]) == 1),
]
ok = True
for name, passed in checks:
    print(f"{'PASS' if passed else 'FAIL'}  {name}")
    ok = ok and passed

print("\n=== Markdown 输出 ===")
print(mod.to_markdown(items, "投喂示例", "2026-10-29"))
sys.exit(0 if ok else 1)
