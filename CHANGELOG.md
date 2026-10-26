# Changelog

## 0.3.3 — 2026-10-26

摘掉 Stop 存储检查：每轮干完活被催一次「记忆检查」，噪音大于收益，哥哥明确不要。

- `hooks/hooks.json` 移除 `Stop` 事件注册（只留 SessionStart 简则 + UserPromptSubmit 每轮召回）；`respire.py` 的 `on_stop` 分支保留，供需要者手动加回
- `store_nudge_every` 默认 `1` → `0`；`on_stop` 取值缺省同步改 0——即使手滑加回 Stop 也不会默认开催
- `validate_plugin.py`：`Stop` 由必需事件降为可选（allowed 保留、required 只留 SessionStart / UserPromptSubmit）
- 测试补断言「hooks.json 默认不注册 Stop」；修 `respire.py` VERSION 落后（0.2.0 → 0.3.3）
- README「装上后发生什么」与调优表同步改口径

## 0.3.2 — 2026-10-23

数据存储安全三点说明：安装时说，不每轮说。

- README 新增「数据存储安全」节：① 可离线使用（本地库，不联网不注册不登录照常召回与落库，离线写入留队列联网补同步）② 上云只有密文（本地加密后上传，服务端只存加密记录、无解密密钥）③ 企业可自建同步服务器（respire-server，Docker Compose + Postgres 内网部署，数据不出企业网络）
- 钩子侧落点：三点说明并入 `NO_RSRS`（引擎未装、安装时注入），**撤出 `RULES` 每会话简则**——常态零打扰，安装/缺引擎时才说明
- SKILL.md 增「数据安全（对用户直说）」小节；插件清单 `description` 追加同义句（插件页安装前可见）

## 0.3.1 — 2026-10-22

GitHub 远端市场为缺省分发源：外部用户无需克隆即可安装。

- `install.sh` 源选择三级：`--github` 强制远端 → 本地有 `.codebuddy-plugin/marketplace.json` 用本地（开发/测试）→ 否则回落 `risense-ai/respire-workbuddy`（owner/repo，git 型市场）；升级路径改先 `marketplace update` 拉 origin 再 `plugin update`
- README 安装段置顶一行装：`curl -fsSL https://raw.githubusercontent.com/risense-ai/respire-workbuddy/main/install.sh | bash`（仓已核实 PUBLIC）
- 测试补「远端市场源存在」断言

## 0.3.0 — 2026-10-22

安装脚本落地：WorkBuddy 桌面端 GUI 未证实有插件安装入口，补一条脚本化官方装载链路。

- 新增仓根 `install.sh`：自动定位 `codebuddy` CLI（`CODEBUDDY_BIN` 环境变量 → PATH → Linux 桌面端捆绑位 `/var/opt/apps/workbuddy/resources/app.asar.unpacked/cli/bin/codebuddy`），`plugin marketplace add --name risense-workbuddy` 注册本地市场（已注册则 `marketplace update` 刷新）、`plugin install`/`plugin update` 安装或升级、读 `installed_plugins.json` 与缓存目录双重验证；WorkBuddy 运行中给出覆盖风险提示；`--uninstall` 卸载并保留市场注册。不手改注册表，全走官方 CLI。
- 校验与测试同步翻转：`validate_plugin.py` 的 REPO_REQUIRED 收录 `install.sh`；`test_hooks.sh` 由「包内无自定义安装脚本」改为「仓根含安装脚本＋支持卸载＋走官方 CLI」三断言。
- README：安装段改脚本优先（GUI 入口标注未证实），卸载段首选脚本、搬移法降为兜底。

## 0.2.0 — 2026-10-22

对齐 respire-qoder v0.6.2 方案，移植其演进项；WorkBuddy 侧适配（中文提示、Stop 协议、`${CODEBUDDY_PLUGIN_ROOT}`）保持不变。

- `skip_prefixes` 配置（默认 `[]`）：宿主内部提示白名单——prompt 以列表中任一前缀开头（大小写不敏感）则本轮不召回也不落库；qoder 侧用于跳过 Qoder 任务监控的 Recap 提示，WorkBuddy 侧默认空、按需配置。
- 落库前缀扩为 `记|存|记录|记住|remember|store`（新增英文 `store:`）。
- 新增 `data_dir()`：运行时数据（hook.log / .nudge_counter）路径统一走 `RESPITE_DATA` → `CODEBUDDY_PLUGIN_DATA` → 脚本目录回退（WorkBuddy 未文档化插件数据目录，实际仍落脚本目录，与 0.1.0 行为一致）。
- 事件名回退：环境变量之外，stdin JSON 的 `hook_event_name` 亦可定事件。
- `.gitignore` 修正锚定：`hooks/hook.log` 只匹配仓根，改裸名 `hook.log`/`.nudge_counter` 使插件子目录日志同样被忽略。
- 测试：新增 `store:` 前缀、白名单跳过（含大小写不敏感）、白名单不影响普通 prompt 五断言；修复「包内无自定义安装脚本」断言依赖英文 ls 报错的 locale 问题（改为直接判文件不存在）。

## 0.1.0 — 2026-10-20

首版：respire 由 Dim 插件移植为 WorkBuddy 标准插件。

- 形态：标准两层——仓根 `.codebuddy-plugin/marketplace.json`（市场清单，市场名 `risense-workbuddy`）＋ `plugins/respire/.codebuddy-plugin/plugin.json`（插件清单），市场条目 `source: "./plugins/respire"`。按 WorkBuddy 插件市场标准安装，无自定义 install.sh。（初版曾把两份清单挤在同一 `.codebuddy-plugin/` 下、`source: "./"`，插件根＝市场根，与官方两层形态不符，已改。）
- 钩子三事件（与 Dim 版同源，协议按 WorkBuddy 改写）：
  - `SessionStart`（matcher `startup|resume|clear|compact`）：注入记忆层简则；未装引擎则注入安装引导（`npm i -g rsrs-cli@latest`，agent 代装）；已装则一次探测三态（未登录/空库/缺模型）按需附引导，常态零打扰。
  - `UserPromptSubmit`：每轮 `rsrs recall --titles` 标题档注入（分数＋8 位短 id＋标题，`superseded_by` 标「已被取代」）；prompt 以「记：/存：/remember:」开头直接落库并回执，判后即存判相似时转述候选待模型决断；`/nomem` 关本轮。
  - `Stop`：存储检查续跑一轮（`hookSpecificOutput.permissionDecision`，不用已弃用的 `decision:"block"`）；`stop_hook_active=true` 防循环；`store_nudge_every` 节流；近 10 分钟已落库不催。
- 协议适配：事件名/字段走 WorkBuddy 信封（`hook_event_name`/`prompt`/`stop_hook_active`/`source`），占位符用 `${CODEBUDDY_PLUGIN_ROOT}`（兼容 `python3 || python` 回退链，无 `commandWindows`——WorkBuddy schema 不含该字段，改由 `shell` 字段与回退链兜底）。
- 文案：`rules`/`empty`/`login` 引导改指 `~/.workbuddy/`（SOUL.md、USER.md）而非 Dim 的 `~/.dimcode/`。
- 落库协议：`rsrs remember --importance important`（引擎判后即存：`status:"pending"` + `written:false` 时不写入，转述候选）；回执催 `retitle` 替换暂拟题。
- 引擎探测链扩展：`~/.npm-global/bin/rsrs`、`/usr/local/bin/rsrs` 入列（本机 npm 前缀安装与系统安装并存）。
- 模型体积口径：BGE-M3 量化版 onnx 件约 570 MB（tokenizer 约 17 MB），激活时同目录生成 cpu-v1.ort 再占约 543 MiB，目录总占用约 1.1 GB；非 fp16 的 1.1G 单件。
- 测试：桩引擎全分支 29 断言（不碰真库）＋真机只读分支，`--store` 显式写探针（写→断言→forget 自清理）；`plugins/respire/scripts/validate_plugin.py` 结构/清单/hooks 形状/fail-open/敏感扫描自检（跨市场根与插件根两处路径均校验）。
