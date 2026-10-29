# respire 连接器（WorkBuddy）

把 `rsrs` 记忆库接成 WorkBuddy 的 **CLI 连接器**：连接器页可见、技能 `respire-memory` 随装随用。
本目录是官方开放平台（open.workbuddy.cn）提交格式的源，也能一键装到本机先行验证。

## 目录

| 文件 | 用途 |
| --- | --- |
| `connector-meta.json` | 市场条目（id/中英名/描述/各 3 条示例/type=cli）——提交审核的主体 |
| `cli.json` | 平台命令映射：`init` / `versionCheck` / `auth` / `unAuth` / `status` + `statusMatch` |
| `icon.svg` | 卡片图标 |
| `skills/respire-memory/SKILL.md` | 给模型看的操作法（技能名须与 `frontmatter.name` 一致） |
| `install_local.py` | 本机安装/卸载（桌面端未上架时用） |

## 本机安装（未上架前）

```bash
python3 connector/install_local.py              # 装 / 升级，幂等
python3 connector/install_local.py --uninstall  # 卸（保留市场注册，便于重装）
```

装完**完全退出并重开 WorkBuddy**——连接器与技能都在启动时装载。

脚本落盘六处（都以 `~/.workbuddy` 为根）：

1. `plugins/known_marketplaces.json` —— 注册 directory 型市场 `risense-respire-connector`
2. `plugins/cache/risense-respire-connector/respire-connector/<版本>/` —— 插件本体 ＋ `.codebuddy-directory-source.json`
3. `plugins/installed_plugins.json` —— 安装条目 `respire-connector@risense-respire-connector`
4. `settings.json` → `enabledPlugins` —— 启用插件
5. `connectors-marketplace/connectors/respire-connector/` ＋ `.codebuddy-connector/connectors.json` ＋ `icons/respire-connector.svg` —— 连接器页的卡片与索引
6. `connectors/<uid>/connector-states.json` —— 启用态 `{bound:true, enabled:true}`（v4 为准，v3 仅镜像）

为什么要脚本而不是命令：`codebuddy plugin` CLI 在桌面端运行期间会卡死（子进程 `epoll` 等主进程 IPC，`exit=124`），插件自带 hooks 也不被加载——只能直接写上述注册表。改动前一律备份到 `~/.workbuddy/.bak-install/connector-<时间戳>/`。

## 测试（提交前必跑）

```bash
python3 connector/validate_connector.py            # 全检（会真跑 status 探活）
python3 connector/validate_connector.py --offline  # 只查静态，不碰外部命令
```

四层，对应审核最容易打回的地方：

| 层 | 查什么 | 不过的后果 |
| --- | --- | --- |
| 包结构 | meta/cli/icon/skills 齐；`SKILL.md` 的 `name` 与目录名一致；description 够长 | 模型选不中技能，目录扫不出来 |
| 市场条目 | 中英名/描述/各 2–5 条示例/`type` | 审核退回补材料 |
| 命令契约 | `init`/`auth`/`unAuth`/`status` 三平台齐；`statusMatch` 是合法正则且**能命中真实输出**；`versionCheck` 版本达标 | 用户装上了却显示「未连接」或直接被判 needsUpgrade 跳过 |
| 打包 | zip 顶层是 `connector-meta.json`，不能多套一层目录 | 上传解析失败 |

**为什么单独测 `statusMatch`**：这是 CLI 连接器唯一的「连接判定」依据——平台只跑 `status` 命令再拿正则撞输出，撞不上就永远显示未连接，而命令本身是成功的，最难排查。

## 三层验收（从弱到强）

1. **契约层**：`validate_connector.py` 全绿（26 项）
2. **平台层**：重启后在应用日志里应看到
   ```
   [ConnectorService] CLI auto-connect: <id> authenticated, updating to connected
   [ConnectorService] CLI Connected: <id>
   ```
   （没这两行，说明平台压根没把它当 cli 连接器处理）
3. **功能层**：按 SKILL.md 的命令手跑一次，确认 `--json` 信封正常
   ```bash
   rsrs --client-only recall "关键词" --titles --limit 3 --json
   ```



## 提交官方开放平台

```bash
cd connector && zip -qr ../respire-connector-1.0.0.zip connector-meta.json cli.json icon.svg skills
```

到 open.workbuddy.cn 控制台 → 连接器 → 新建 → 上传 zip。审核关注两处：

1. `auth` 命令须能在 10 秒内输出登录 URL 且不依赖本地回调（本包用 `rsrs login --oauth --no-open`）
2. 资质：个人认证能否发连接器，以创建页实际口径为准（官方文与第三方指南口径不一）

## 命名

- 市场 id / `source`：`respire`（提交用）
- 本地插件名：`respire-connector`——不能叫 `respire`，会与仓库里的记忆插件（`plugins/respire`）撞名
- 技能名：`respire-memory`

## 已知边界

1. `init` 走 `npm i -g @rsrsai/cli@latest`；本机若已是自建二进制（`~/.local/bin/rsrs`），`versionCheck` 通过即不会触发 `init`
2. 官方市场刷新（`connectors-marketplace` 重拉 zip）会覆盖索引与镜像包，重跑 `install_local.py` 即可复原
3. 该连接器与平台自带「记忆工程」定位重叠，上架文案需说明差异（本地加密、可离线、可自建同步）
