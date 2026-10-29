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
