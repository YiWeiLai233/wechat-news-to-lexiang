# 腾讯乐享 MCP 配置

乐享官方提供 MCP 服务，把知识库的读写能力暴露成工具，AI 可以直接调用建目录、建文档、上传文件。

## 获取凭证

打开 https://lexiangla.com/mcp 并登录，拿到两个值：

- `COMPANY_FROM` — 企业标识
- `LEXIANG_TOKEN` — 访问令牌，格式 `lxmcp_xxx`

Token 会过期，过期后在同一个页面点续期即可，**不需要重写整份配置**。

## 三种接入方式

### 方式一：WorkBuddy 连接器（推荐）

在 WorkBuddy 的「连接器 / 集成」里找到「乐享知识库」，点授权走 OAuth。

这种方式最省事，而且**连接器会覆盖手动安装的 MCP 配置**。用 `whoami()` 验证连通。

401 或断连时，回到同一入口点「重新授权」，不要去改配置文件。

### 方式二：官方 Skill 一键安装

```bash
npx @lexiang/skills install
```

CLI 会自动检测已安装的客户端，写入对应目录：

| 客户端 | 路径 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/` |
| CodeBuddy | `~/.codebuddy/skills/` |
| Claude Code | `~/.claude/skills/` |
| 通用标准 | `~/.agents/skills/` |

同时会配置 MCP 连接，写入 `~/.workbuddy/mcp.json`。

### 方式三：手动写 mcp.json

编辑 `~/.workbuddy/mcp.json`：

```json
{
  "mcpServers": {
    "lexiang": {
      "enabled": true,
      "url": "https://mcp.lexiang-app.com/mcp?company_from=你的COMPANY_FROM",
      "transportType": "streamable-http",
      "headers": {
        "Authorization": "Bearer 你的LEXIANG_TOKEN"
      }
    }
  }
}
```

也可以用环境变量：`COMPANY_FROM` 和 `LEXIANG_TOKEN`。

> 注意是 `~/.workbuddy/mcp.json`，不是 `~/.workbuddy/.mcp.json`（少了点号）。

## 常用工具

| 工具 | 用途 |
|---|---|
| `whoami` | 连通性检查，返回当前用户与租户 |
| `space_describe_space` | 知识库信息，含 `root_entry_id` |
| `entry_list_children` | 列子条目，用于查目录和查重 |
| `entry_create_entry` | 建目录（folder）或空白文档（page） |
| `entry_import_content` | 建在线文档并写入正文 |
| `file_apply_upload` → `curl PUT` → `file_commit_upload` | 三步上传文件（PDF、视频等） |

工具名以实际连接后列出的为准，版本间可能微调。

## 归档推荐结构

```
知识库根目录
└── 每日资讯
    ├── 2026-10
    │   ├── 半年增长复盘：从 0 到 1 的完整路径
    │   ├── AI 记忆机制到底怎么回事
    │   └── ...
    └── 2026-11
        └── ...
```

按「月份目录 + 单条资讯一篇文档」组织。不要把所有资讯合成一篇大文档——知识库的价值在检索，一篇塞十条会让 RAG 召回失准。

## 权限提醒

Agent 调用乐享时，访问范围受当前用户的知识权限约束。不同成员执行同一任务，能看到的库可能不同。

把资讯归档进团队共享空间前，确认内容适合公开给该空间的所有成员。

## 官方资源

- MCP 配置页面：https://lexiangla.com/mcp
- 官方 Skill 仓库：https://github.com/tencent-lexiang/lexiang-mcp-skill
- 开放 API 文档：https://lexiang.tencent.com/wiki/api/
