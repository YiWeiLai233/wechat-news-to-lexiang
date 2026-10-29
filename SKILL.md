---
name: wechat-news-to-lexiang
display_name: 微信资讯精读归档
display_name_en: WeChat News Deep-Read Archive
description: 当用户要把公众号文章做内容精读并归档时调用。抓取公众号正文全文，由 AI 提炼要点写成精读稿，存入 OneDrive 目录并上传腾讯乐享知识库。触发词：微信资讯、公众号精读、文章精读、乐享归档、资讯入库、文章浓缩、资讯日报。
description_zh: 抓公众号正文全文，AI 提炼成精读稿，双存储到 OneDrive 与乐享知识库。
description_en: Fetch WeChat article full text, summarize into deep-read notes, archive to OneDrive and Lexiang.
category: knowledge-management
version: 2.4.0
author: WorkBuddy
agent_created: true
---

# 微信资讯精读归档

拿到链接 → 抓公众号正文 → AI 提炼成精读稿 → 双存储（OneDrive + 乐享）。

不是"记个标题加一句推荐语"。是真的读全文，提炼出数据、机制和判断。

## 能力边界

| 环节 | 可行性 | 说明 |
|---|---|---|
| 拿到链接 | **靠人工投喂** | 个人微信没有官方 API，也不读本地聊天库。用户贴链接，或把链接清单存成文件喂进来 |
| 抓公众号正文 | **完全可以** | 纯 HTTP 请求即可，不需要 Playwright 或浏览器 |
| AI 提炼内容 | 可以 | 这一步决定整份产出的价值 |
| 写 OneDrive | 可以 | 写本地同步目录，客户端自动上传，无需 Microsoft 授权 |
| 上传乐享 | 可以 | 乐享官方 MCP |

**抓正文不需要浏览器。** 带浏览器 UA 请求 `mp.weixin.qq.com`，返回 200 且是完整 HTML。不要因为「图片要懒加载」就误判必须上 Playwright —— 文字内容不依赖 JS。

**视频号（`weixin.qq.com/sph/`）抓不到正文。** 纯 SPA，只记标题和链接，标注「视频，未精读」，禁止编造内容。

---

## 快速开始

```bash
# 0. 环境自检（首次必做，看清哪些已就绪、哪些要问用户）
python scripts/check_env.py

# 1. 配置输出位置（自检里报未配置时再做）
python scripts/setup_onedrive.py

# 2. 抓正文
python scripts/fetch_articles.py --url "https://mp.weixin.qq.com/s/xxx" --out articles/2026-10-29

# 3. 读 articles/*.txt，一篇写一个 md（这一步由 AI 完成，见下方写作规范）
#    文件名就用标题简写，例如 output/资讯精读/2026/六大具身路线详解.md

# 4. 同步到 OneDrive（一篇一个文件，文件名自动取正文 H1 的简写）
python scripts/publish.py --dir output/资讯精读/2026

# 5. 上传乐享（见「上传乐享」一节）
```

## 前置条件

**必需**：Python 3.9+，无第三方依赖。乐享连接器（若要上传知识库）。

**首次使用或刚装好，先跑 `python scripts/check_env.py`**：它逐项检查 Python 版本、config、OneDrive 目录是否存在可写、是否真的在同步根下、乐享配置是否完整，用 `[OK]`/`[!]`/`[X]` 标出状态，退出码 1 表示有阻断问题。乐享连接器的授权状态脚本查不到，需要自己调 `mcp__lexiang__whoami` 确认。

**然后读同目录的 `安装与配置.md`**：里面有自检命令、两个可选依赖的逐项确认清单、配置回读和试跑流程。用户说「配置一下这个技能」时，就按那份清单走。

---

## 完整流程

### Step 1 · 拿到链接

只有两条路：

```bash
# A. 用户直接贴链接 —— 跳过本步，直接进 Step 2（最常见）

# B. 链接清单存成文件，解析成结构化 JSON
python scripts/collect.py --path ./inbox.md --out links.json
```

投喂文件就是纯文本，一行一条，三种写法都认：微信链接卡片 XML（能连标题和摘要一起拿到）、「标题 + 链接」的纯文本、《书名号》里的书名当标题。加 `--format markdown` 直接输出可读清单。

**这个 skill 不读微信聊天记录。** 要归档哪几篇，由用户给出哪几篇——知识库是共享空间，替用户推断「群里哪些内容值得传」既不安全也不准。

### Step 2 · 抓正文

```bash
# 批量
python scripts/fetch_articles.py --from-json links.json --out articles/2026-10-29

# 单篇调试
python scripts/fetch_articles.py --url "https://mp.weixin.qq.com/s/xxx" --format text
```

每篇产出 `.txt`（正文纯文本）+ `.json`（标题、公众号、发布时间、字数），另有 `_index.json` 汇总。

失败会写明原因：文章已删除、被风控拦截、图片型内容（正文过短）、页面结构变更。**不要跳过失败项，在成稿末尾单列「未抓取」并写明原因。**

### Step 3 · 提炼成精读稿

**一篇一个 md，不要合成日报。** 文件放 `output/资讯精读/<年份>/<标题简写>.md`，文件名就是这篇的标题简写（和 OneDrive 落盘名一致，省得同步时再改名）。

单篇结构（H1 是文章标题，正文用二级标题）：

```markdown
# 文章标题

**来源**：公众号名 · 发布日期
**原文**：<链接>

## 一句话        这篇到底做了什么
## 它解决什么问题  为什么需要这个东西，现有方案缺什么
## 怎么做        讲清机制，不要罗列名词
## 关键数据      具体数字、对比、阈值
## 值不值得读     给出判断，并指出局限
```

标题简写怎么取：优先用冒号/破折号之前的主标题，再砍掉次要修饰。

- `六大具身路线详解：模块化、技能编排、IL、RL、VLA、世界模型，到底在"吵"什么` → `六大具身路线详解`
- `让假肢界面同时记录接触位置与刺激累积：一套触觉和类痛觉并行传感器` → `让假肢界面同时记录接触位置与刺激累积`

`publish.py` 会自动做同样的截断，但**自己先把文件名定好**更可控，也省得脚本兜底的截断砍在半个词上。

**这五条决定产出质量：**

- **讲机制不讲名词。** 不写「采用了 X 技术和 Y 架构」，要写「X 靠什么原理起作用」。
- **抓具体数字。** 灵敏度、阈值、样本量、提升幅度 —— 这些是精读稿和摘要的分界线。
- **给判断并指出局限。** 只说好话的精读没有价值，要点明受试者只有几人、某个区间精度掉档、离产品化还差什么。
- 不复述原文的章节结构，原文小标题不该出现在精读稿里。
- 禁用套话：「值得注意的是」「综上所述」「首先其次最后」「赋能」「闭环」。

> **对照示例**
> 差：该研究提出了一种多模态传感器，采用压电和压阻双通道设计，性能优异。
> 好：压电层管定位，压阻层接突触晶体管，靠质子迁移的衰减特性做记忆 —— 记忆不是算出来的，是材料自带的。

### Step 4 · 落 OneDrive

一篇一个 md，文件名取正文 H1 的标题简写：

```bash
# 单篇
python scripts/publish.py --src output/资讯精读/2026/六大具身路线详解.md

# 批量（目录下所有 md 一次同步，推荐）
python scripts/publish.py --dir output/资讯精读/2026

# 手动指定文件名（H1 太长或想统一命名时）
python scripts/publish.py --src xxx.md --title "六大具身路线"
```

最终路径：`<onedrive_dir>\<onedrive_subdir>\<年份>\<标题简写>.md`。写进同步目录后客户端自动上传，不需要任何 Microsoft 授权。

命名规则（`short_title`，可预测、不做语义猜测）：取 H1 → 去 markdown 标记和书名号 → 冒号/破折号后的副标题丢掉 → 清掉 Windows 非法字符 → 超 50 字截断。

**同名不直接覆盖**（因为标题简写只留主标题，系列文撞名很常见）：

| 情况 | 处理 |
|---|---|
| 原文链接相同 | 同一篇改过稿，覆盖旧版 |
| 内容一字不差 | 幂等重跑，跳过不动 |
| 链接、内容都不同 | 不同文章撞了同一个主标题，存为 `<标题简写>-<日期>.md`，已有文章不被动 |

所以重跑同一篇不会堆版本，而「每周一期的同名周报」也不会互相吃掉。`--dry-run` 会先告诉你每篇会落到哪个文件名。

`--dir` 批量模式会跳过纯日期命名的 md（`2026-10-29.md`），那是旧版「一天一份合并日报」的格式，不当作单篇文章同步。

配置：

```bash
python scripts/setup_onedrive.py --check                                    # 查当前配置
python scripts/setup_onedrive.py                                            # 交互式设置
python scripts/setup_onedrive.py --path "C:\\Users\\你\\OneDrive\\知识库"   # 一条命令
python scripts/setup_onedrive.py --reset                                    # 只写本地
```

输入路径时**直接粘资源管理器地址栏那串**，不用手写双反斜杠，脚本会自动处理。

`onedrive_dir` 为空时只写本地 `output/`，不报错。

### Step 5 · 上传乐享

前置：连接器里已授权「乐享知识库」，或 `mcp.json` 配好了 `lexiang` 服务。先调 `whoami()` 验证。

按顺序调用，**每步检查结果，不要跳步**：

| 顺序 | 工具 | 目的 |
|---|---|---|
| 1 | `whoami` | 验证连通，401 就让用户续期后跳过 |
| 2 | `space_describe_space` | 拿 `root_entry_id`；config 里有 space_id 就直接用 |
| 3 | `entry_create_entry` | 建 `<folder>/<YYYY-MM>` 目录（folder 类型），已存在则跳过 |
| 4 | `entry_list_children` | 按标题查重，已存在的跳过 |
| 5 | `entry_create_entry` | 建 page，name 用文章标题，parent 用月份目录 ID |
| 6 | `block_update_page` | 写入正文（见下方关键约束） |

**一条资讯一篇文档，不要合成大文档。** 知识库的价值在检索，一篇塞十条会让 RAG 召回变成流水账。

#### 写入正文的关键约束（踩过的坑）

`block_update_page` 的 `replace_content` **不能一次性写入带结构的整篇正文**，会报：

```
replacement content is structurally unstable after round trip;
use smaller update_content replacements or fetched canonical snippets
```

可靠做法是两步：

1. 用 `replace_content` 只写**一个纯文本段落**（无标题、无列表、无表格）
2. 再用 `update_content` 分段追加，每次 1～2 个小节

追加时的锚点技巧：用「上一段结尾的那句话」作为 `old_str`，`new_str` = 结尾句 + 新内容。

```json
{
  "entry_id": "xxx",
  "command": "update_content",
  "content_format": "markdown",
  "content_updates": [{
    "old_str": "这是上一段的结尾句。",
    "new_str": "这是上一段的结尾句。\n\n## 新小节\n\n正文…"
  }]
}
```

**但这个锚点技巧只在「往文档最末尾追加」时可靠。** 实测过一个反例：锚点句后面还有别的块时，新内容会被追加到**文档末尾**而不是锚点后面，原来锚点后面那个块反而被推到了新内容之后——结果是某段结论跑到了全文最后。这种情况 `update_content` 返回的仍然是 `succeeded`，不报错，只能靠回读发现。

**要在文档中间插入，改用 `replace_blocks`**（配 `content_format=mdx`）：把锚点块原样重写、保留它原来的 `data-id`，再在它后面补新块。

```json
{
  "entry_id": "xxx",
  "command": "replace_blocks",
  "content_format": "mdx",
  "block_replacements": [{
    "block_id": "9dd9c5af39c240118a3a8f84e0104ebb",
    "new_str": "<Paragraph data-id=\"9dd9c5af39c240118a3a8f84e0104ebb\">原文整段照抄。</Paragraph><Paragraph>要插在它后面的新段落。</Paragraph>"
  }]
}
```

生成正文时更省事的做法是**严格从前往后追加**：每次锚点都取文档当前的最后一句，这样永远不需要中间插入。只有事后补内容才动用 `replace_blocks`（必要时也可以先 `delete_blocks` 删掉错位的块再重建）。

**回读校验必须用 `render_mode=mdx`，不要用默认的 markdown。** markdown 回读看不到块边界，顺序错了很容易看漏；mdx 回读能直接看到每个块的 `data-id` 和先后次序，上面那个错位就是这样定位的。

另外两个已知损耗：

- `update_content` 写入的段落里，**行内 `**加粗**` 有一部分不生效**，回读变纯文本。不影响可读，但某个判断必须突出时，把它写成独立段落，别指望行内加粗。
- **表格和引用块最容易触发结构不稳定**，优先用有序列表和加粗段落替代。

#### 元工具模式

乐享 MCP 不直接暴露业务工具，而是三步：`search_tools` 找工具名 → `get_tool_schema` 拿参数 → `call_tool` 执行。只有 `whoami` 等少数工具可以直接调。

---

## 配置文件

`config.json` 与 SKILL.md 同级。首次运行 `publish.py` 或 `setup_onedrive.py` 时会自动从 `config.example.json` 生成，不用手动复制；也可以提前复制一份自己改。

| 字段 | 作用 |
|---|---|
| `onedrive_dir` | 本地已同步的 OneDrive 目录，留空则只写本地 |
| `onedrive_subdir` | 子目录名，默认「资讯精读」；其下按年份分目录，每篇文章一个 md |
| `lexiang_enabled` | 是否上传乐享，false 则跳过 |
| `lexiang_space_id` | 知识库 ID，留空则自动取第一个可写库 |
| `lexiang_folder` | 知识库顶层目录名，下面按 `YYYY-MM` 分月 |
| `lexiang_folder_id` | 顶层目录的 entry_id，缓存下来避免每次查找 |

---

## 降级路径

| 卡在哪 | 怎么办 |
|---|---|
| 用户没给链接清单 | 让他贴几篇过来，或把清单存成文件走 `collect.py` |
| 抓正文失败 | 保留标题+链接，标注原因，不要编造内容 |
| 乐享连不上 | 只写 OneDrive，明确告知用户，不要中断 |
| OneDrive 没配 | 只写本地 `output/`，提醒用户补配置 |

---

## 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| 正文抓到 0 字 | 页面结构变了或图片型文章 | 换选择器重试，或标注「图片内容」 |
| 出现「环境异常」 | 请求频率过高被风控 | 降低频率，加间隔重试 |
| 标题抓到「微信公众平台」 | 页面没渲染出真实标题 | 改用 `og:title` 或从正文首行取 |
| OneDrive 里文件名不对 | H1 太长或有非法字符 | 用 `--title "简短标题"` 手动指定 |
| 落盘成了 `2026-10-29.md` | 正文 H1 是日期而非文章标题 | 检查 Step 3 结构，H1 必须是文章标题 |
| 落盘成了 `标题-2026-10-29.md` | 另一篇不同文章撞了同一个主标题 | 正常行为，没丢文章；想消歧就改文章标题或用 `--title` 指定 |
| 发布时间是 10 位数字 | 只给了 Unix 时间戳 | 脚本已自动转 `YYYY-MM-DD` |
| 乐享 401 | token 过期 | 去 lexiangla.com/mcp 续期，不改配置 |
| 乐享整页写入失败 | 结构不稳定 | 见「写入正文的关键约束」 |
| 追加的内容跑到文档末尾 | 锚点在文档中间，后面还有别的块 | 改用 `replace_blocks`；回读用 `render_mode=mdx` |
| 加粗没生效 | `update_content` 的行内样式损耗 | 把要强调的判断写成独立段落 |
| 上传成功但搜不到 | 索引有延迟 | 等几分钟，或确认文档在正确目录 |
| 自检报 OneDrive 不可写 | 目录权限不足或路径写错 | 换可写目录，或加 `--mkdir` 让脚本建目录后重试 |
| 自检报「不在同步根下」 | 配成了普通本地目录 | 文件不会上云，换到 OneDrive 客户端同步的目录里 |

---

## 合规

1. 只处理自己账号可访问的内容，不绕过任何权限。
2. 只处理用户主动给出的链接，不读取本地聊天记录、不替用户猜测要传什么。
3. 精读稿会进入团队知识库，涉及内部信息的文章先确认可公开范围。
4. 先小范围验证：一个群、一天、一两篇，确认内容和权限都正常再扩量。

---

## 文件说明

```
scripts/collect.py         解析投喂文件里的链接清单（不读聊天记录）
scripts/fetch_articles.py  抓公众号正文
scripts/publish.py         同步到 OneDrive（一篇一个 md，标题简写命名）
scripts/setup_onedrive.py  OneDrive 路径配置向导
scripts/check_env.py       环境自检：配置、OneDrive 目录、乐享配置
scripts/test_collect.py    投喂解析自测（不依赖外部服务）
scripts/test_publish.py    命名与同名冲突自测（写临时目录，不碰真实文件）
references/lexiang-mcp-setup.md  乐享 MCP 配置
安装与配置.md              首次安装与可选依赖配置清单（装好后先读这个）
```
