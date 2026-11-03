# respire 连接器（WorkBuddy · MCP 形态）

把 `rsrs` 记忆库接成 WorkBuddy 连接器：模型直接拿到 16 个 `memory_*` 原生工具（召回、落库、因果链、日记……），不用拼 shell。
本目录是官方开放平台（open.workbuddy.cn）提交格式的源，也能在上架前先挂到本机试用。

## 目录

| 文件 | 用途 |
| --- | --- |
| `connector-meta.json` | 市场条目（中英名/描述/各 3 条示例/`type=mcp`/`minWorkbuddyVersion=5.0.0`）——提交审核的主体 |
| `mcp.json` | MCP Server 配置：`stdio` ＋ `npx -y rsrs-cli@latest mcp` ＋ `runtime node >=18` |
| `icon.svg` | 卡片图标 |
| `skills/respire-memory/SKILL.md` | 给模型看的操作法（落库规矩、16 工具表、红线） |
| `validate_connector.py` | 提交前自检（29 项，含真机 MCP 握手） |

**为什么是 MCP 而不是 CLI**：MCP 给模型原生工具，参数与返回值有标准描述，不依赖模型自己拼命令行；`npx` 首次运行自动拉包，用户无需先装 CLI。CLI 形态（`cli.json` ＋ `statusMatch`）的实现留在 git 历史里，需要时可取回。

## 本机试用（未上架前）

往 `~/.workbuddy/mcp.json` 写一条（该文件是官方「自定义连接器 → 配置 MCP」读写的同一个）：

```json
{
  "mcpServers": {
    "respire": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "rsrs-cli@latest", "mcp"],
      "runtime": { "type": "node", "version": ">=18" },
      "timeout": 60000
    }
  }
}
```

写完**完全退出并重开 WorkBuddy**，`自定义连接器 → 我的 MCP` 里应出现 `respire`（16 个工具）。也可在该对话框点「配置 MCP」直接粘贴——面板保存会立即重载，不必重启。

要撤：把上面这条从 `mcpServers` 删掉即可（改动前先备份该文件）。

## 测试（提交前必跑）

```bash
python3 connector/validate_connector.py            # 全检（会真跑 MCP 握手）
python3 connector/validate_connector.py --offline  # 只查静态，不碰外部命令
```

四层，对应审核最容易打回的地方：

| 层 | 查什么 | 不过的后果 |
| --- | --- | --- |
| 市场条目 | 中英名/描述 20–100 字/各 2–5 条示例/`source` 是 kebab-case/`auth_mode` 合法 | 审核退回补材料 |
| 包结构 | meta/mcp/icon/skills 齐；`SKILL.md` 的 `name` 与目录名一致；description 够长 | 模型选不中技能，目录扫不出来 |
| 接入契约 | `mcpServers` 只有一个 Server；stdio 有 `command`；**真机握手拿到 `serverInfo` 与 `tools/list`**；Skill 覆盖 ≥ 半数工具 | 连不上，或连上了但 AI 不会用 |
| 打包 | zip 顶层是 `connector-meta.json`，不能多套一层目录 | 上传解析失败 |

**为什么单独测握手**：MCP 连接器的「连接成功」就是握手本身——`initialize` 不回 `serverInfo`、`tools/list` 拿不到工具，平台会一直显示连接失败，而 `npx` 拉包失败的报错藏在 stderr 里最难查。

**为什么测 Skill 覆盖率**：MCP 方案里 Skill 是可选的，但一旦写了却漏掉大半工具，模型会只用它读到的那几个。

## 三层验收（从弱到强）

1. **契约层**：`validate_connector.py` 全绿（29 项）
2. **平台层**：重启后 `我的 MCP` 出现 `respire`，状态为已连接、16 个工具启用
3. **功能层**：随便问一句「翻一下我以前关于 X 的记忆」，看模型是否调 `memory_recall`

## 提交官方开放平台

```bash
cd connector && zip -qr ../respire-connector-1.0.0.zip connector-meta.json mcp.json icon.svg skills
```

到 open.workbuddy.cn 控制台 → 连接器 → 新建 → 上传 zip。审核关注三处：

1. `minWorkbuddyVersion=5.0.0`——`mcp.json` 的 `runtime` 字段要 v5.0.0 起（本机 5.6.2 已验）
2. `auth_mode` 省略＝官方口径「无需认证，点击连接即可用」——rsrs 本地优先、离线可用，平台侧确实不涉及用户身份；跨设备同步由用户自己跑 `rsrs login`，连接器不经手口令
3. 资质：个人认证能否发连接器，以创建页实际口径为准（官方文与第三方指南口径不一）

## 命名

- 市场 `source`：`respire`（全局唯一，kebab-case）
- 本地插件名（若走插件装载）：`respire-connector`——不能叫 `respire`，会与仓库里的记忆插件 `plugins/respire` 撞名
- 技能名：`respire-memory`

## 已知边界

1. `npx -y rsrs-cli@latest mcp` 首次运行要拉包（约几秒），`timeout` 给到 60000 ms；已装过则走缓存
2. `mcp.json` 官方只读 `mcpServers` 里**第一个** Server，别往里塞第二个
3. 该连接器与平台自带「记忆工程」定位重叠，上架文案需说明差异：本地加密、可离线、可自建同步服务
