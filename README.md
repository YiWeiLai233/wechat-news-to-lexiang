# 微信资讯精读 Skill

`wechat-news-to-lexiang` 是一个 WorkBuddy Skill：把公众号文章读完全文，提炼成结构化精读稿，同时存到 OneDrive 和腾讯乐享知识库。

**当前版本 v2.4.0** · 纯 Python 标准库，无第三方依赖 · 解压即用的 39 KB 自包含包

[博客项目档案](https://yiweilai233.github.io/projects/wechat-news-to-lexiang/) · [架构复盘](https://yiweilai233.github.io/logs/wechat-news-skill-architecture/) · [版本迭代踩坑](https://yiweilai233.github.io/logs/wechat-news-skill-pitfalls/)

---

## 它解决什么

群里每天发一堆公众号和技术资讯，看到了、存了链接，然后从不回看。这个 Skill 想让机器把正文读完提炼成能检索的精读稿，而不是再造一个链接清单。

产出不是「标题 + 链接」，是五段结构：

```
## 一句话            这篇到底做了什么
## 它解决什么问题      为什么需要这个东西，现有方案缺什么
## 怎么做            讲清机制，不要罗列名词
## 关键数据          具体数字、对比、阈值
## 值不值得读         给出判断，并指出局限
```

## 链路

```
链接 → 抓正文 → AI 读全文 → 精读稿（一篇一文件）→ OneDrive + 乐享
```

| 环节 | 可行性 | 说明 |
|---|---|---|
| 拿到链接 | **靠人工投喂** | 个人微信无官方 API，也不读本地聊天库 |
| 抓公众号正文 | **完全可以** | 纯 HTTP + 浏览器 UA，不需要浏览器 |
| AI 提炼内容 | 可以 | 这一步决定整份产出的价值 |
| 写 OneDrive | 可以 | 写本地同步目录，无需 Microsoft 授权 |
| 上传乐享 | 可以 | 乐享官方 MCP |
| 抓视频号内容 | **不行** | 纯 SPA，只记标题，禁止编造 |

## 安装

### 方式一：交给 AI 配（推荐）

把整个文件夹放进 `%USERPROFILE%\.workbuddy\skills\`，形成这个路径：

```
%USERPROFILE%\.workbuddy\skills\wechat-news-to-lexiang\SKILL.md
```

然后对 WorkBuddy 说：

> 按 `安装与配置.md` 帮我配置这个技能

它会跑环境自检、逐项问你要不要接 OneDrive 和乐享，最后拿一篇公开文章试跑。**装完要新开一个会话**，当前会话不会重新加载技能。

### 方式二：命令行直接用

脚本都是纯标准库，不装 WorkBuddy 也能跑，只是没有 AI 写精读稿那一步：

```bash
git clone https://github.com/YiWeiLai233/wechat-news-to-lexiang.git
cd wechat-news-to-lexiang

python scripts/check_env.py                                  # 环境自检
python scripts/fetch_articles.py --url "https://mp.weixin.qq.com/s/xxx" --format text
python scripts/publish.py --dir output/资讯精读/2026          # 同步到 OneDrive
```

要求 Python 3.9+。

## 快速开始

```bash
# 0. 环境自检（首次必做）
python scripts/check_env.py

# 1. 配置输出位置（自检报未配置时再做）
python scripts/setup_onedrive.py

# 2. 抓正文
python scripts/fetch_articles.py --url "https://mp.weixin.qq.com/s/xxx" --out articles/2026-10-29

# 3. 读 articles/*.txt，一篇写一个 md（这步由 AI 完成）

# 4. 同步到 OneDrive
python scripts/publish.py --dir output/资讯精读/2026

# 5. 上传乐享（见 SKILL.md「上传乐享」一节）
```

## 设计取舍

**一篇一个文件，不做一天一份合并 md。** 一篇塞十条，知识库检索时 RAG 召回会返回一整天的流水账。

**标题简写命名。** 取正文 H1 冒号前的主标题，清掉 Windows 非法字符，超长截断。`六大具身路线详解：模块化、技能编排、IL、RL、VLA…` 落成 `六大具身路线详解.md`。

**同名不覆盖。** 四步判据区分「同篇重跑」和「不同文章撞名」，后者另存为 `<简写>-<日期>.md`，不丢文章。

**能力边界写死进文档。** 视频号那条写的不是「抓不到」，而是「只记标题和链接，标注未精读，**禁止编造内容**」——「抓不到」是描述，AI 会尝试绕；「禁止编造」是约束，AI 会停下来标注。

**不读聊天记录。** 只处理用户主动给出的链接。知识库是共享空间，替用户推断「群里哪些内容值得传」既不安全也不准。

## 已知边界与踩坑

| 坑 | 现象 | 处理 |
|---|---|---|
| 乐享整页写入 | `structurally unstable after round trip` | 先写一个纯文本段落，再分段追加 |
| 追加位置错位 | 段落跑到文档末尾，接口仍返回 `succeeded` | 改用 `replace_blocks`；回读用 `render_mode=mdx` |
| 行内加粗丢失 | `update_content` 写入的 `**粗体**` 变纯文本 | 要强调的判断写成独立段落 |
| 风控 | 提示「环境异常」 | 降低频率，加间隔重试 |
| 图片型文章 | 正文抓到 0 字 | 只记标题和链接，不编造 |

更多细节见 [SKILL.md](SKILL.md) 和博客的[版本迭代踩坑](https://yiweilai233.github.io/logs/wechat-news-skill-pitfalls/)。

## 目录

```
wechat-news-to-lexiang/
├── SKILL.md                      主指令：流程、写作规范、踩坑、排错
├── 安装说明.md                    给人看的使用说明
├── 安装与配置.md                  给 agent 的执行清单
├── config.example.json           配置模板（不含个人数据）
├── scripts/
│   ├── check_env.py              环境自检
│   ├── collect.py                投喂文件解析（不读聊天记录）
│   ├── fetch_articles.py         抓公众号正文
│   ├── publish.py                同步 OneDrive，标题简写命名，同名不覆盖
│   ├── setup_onedrive.py         路径配置向导
│   ├── test_collect.py           投喂解析自测（7 项）
│   └── test_publish.py           命名与同名冲突自测（10 项）
└── references/
    └── lexiang-mcp-setup.md      乐享 MCP 配置
```

`config.json` 首次运行脚本时从 `config.example.json` 自动生成，含本地路径与知识库 ID，**已在 `.gitignore` 中排除，不要外发**。

## 自测

```bash
python scripts/test_collect.py    # 7 项 PASS
python scripts/test_publish.py    # 10 项 PASS，只写系统临时目录
```

## 合规

1. 只处理自己账号可访问的内容，不绕过任何权限。
2. 只处理用户主动给出的链接，不读取本地聊天记录。
3. 精读稿会进入团队知识库，涉及内部信息的文章先确认可公开范围。
4. 先小范围验证：一个群、一天、一两篇，确认内容和权限都正常再扩量。

## License

MIT
