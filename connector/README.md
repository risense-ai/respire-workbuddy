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

```bash
python3 connector/install_local.py              # 装 / 升级（幂等）
python3 connector/install_local.py --uninstall  # 卸（备份保留）
```

装完**完全退出并重开 WorkBuddy**。

**别只往 `~/.workbuddy/mcp.json` 塞一条 server**——那样只注册了「自定义 MCP」，16 个工具能用，但随包的 `SKILL.md` **不会加载**，模型看不到「每轮先召回」的操作法，记忆就是死的。`install_local.py` 按连接器包布局落盘七处（市场清单、连接器包、插件缓存、安装条目与启用、连接器索引与卡片与图标、启用态 `{bound,enabled}`、并摘掉 `mcp.json` 里的重复条目），工具与技能同时生效。

改动前一律备份到 `~/.workbuddy/.bak-install/connector-mcp-<时间戳>/`。

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
2. **平台层**：重启后连接器页出现「睿思记忆」、状态已连接；技能列表里出现 `respire-memory`（**技能没出现＝只装了 MCP，没装包，记忆不会被触发**）
3. **触发层**：**不提任何记忆相关的词**，直接问一件具体的事（如「上次那个部署怎么修的」），看模型是否**主动**先调 `memory_recall`——调了才算通；要你明说「查一下记忆」才调，说明技能没加载

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
