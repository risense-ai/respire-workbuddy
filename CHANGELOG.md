# Changelog

## 0.4.3 — 审计整改：写结果状态机＋Stop fail-open＋请求级免催凭证（WB-01~WB-06）

### Fixed

- **WB-01 Stop fail-open**：查库 `list` 失败/超时/坏信封时直接放行，不再 deny——记忆层故障不得强迫主任务续跑。**同步翻转旧测试错误期望**（`failed→deny` 曾被当正确结果）。
- **WB-02 未知写结果只读核实**：超时/坏回执/无输出归为 **unknown**——回执明令「`rsrs list`/`rsrs show` 只读核实、禁止重发 remember」（旧文案「手动 rsrs remember 核实」有重复写风险）；秒回坏回执自动 `list` 核对并报告可能已写（附只读 id）。`warn`+有效 id 是**已写入带警告**，如实回执不误报失败。
- **WB-03 快存回执闭环**：ok/warn 后 `show` 写后回读核验（R11，verified/mismatch/unavailable 如实标注）；pending 保留候选短 id 与引擎建议动作全量（改＞并＞挂＞存，§7.2）。
- **WB-04 请求级免催凭证**：废除「近 10 分钟任意写入」全局抑制（跨轮误抑制）；改为 `.store_turn`——同会话、本轮 prompt 之后的成功写回执或引擎侧写入才免催。
- **WB-05 一次收尾锁**：宿主未带 `stop_hook_active` 时同一请求也至多 deny 一次；新 prompt 重新武装。

### Changed

- 测试：CI 桩白名单升级为有序调用序列（remember→show 回读链），spy 支持 warn/pending/silent/hang/show_mismatch；新增 8 个契约测试。bash 套件加 rst 场景复位与状态机/warn/unknown 断言（55/0 → 67/0）；**修复写探针从未写真库的既有 bug**（默认走桩）——现显式传真引擎（Windows 优先 `.CMD` 形式，sh shim 会 WinError 193），实时库判重收紧时优雅 SKIP。
- `RESPITE_TEST_FAST`/`RESPITE_TURN_STATE` 测试后门；README 行为表同步；`.gitignore` 增 `.store_turn`。


## 0.4.2 — 2026-11-01 · 两份 SKILL.md 英文化

- `plugins/respire/skills/respire/SKILL.md` 与 `connector/skills/respire-memory/SKILL.md` 全文英文化（dimcode 家族结构；connector 保留命令表格）；「记：」前缀与信封解析不变；触发词保留中文供路由
- 版本三方同步 0.4.2（hook VERSION / plugin manifest / marketplace 条目）

## 0.4.1 — 2026-10-31 · Stop 恢复＋提示词英文化（dimcode 同款）＋疑似凭据拦截

- **hooks.json 命令追加第三回退 `|| py -3`**：真实 WorkBuddy 宿主（Windows）以 cmd.exe spawn 钩子命令，默认 PATH 下 `python3`/`python` 均被 Microsoft Store 别名桩接管（实测 rc=49、报 "Python was not found"），原双回退链在装有 python.org Python 的 Windows 宿主上全数落空；`py` 启动器随官方安装器入 PATH，作第三回退。validate 同步要求三事件携带该回退。
- **Stop 存储检查恢复注册**（0.3.3 起默认关闭）：hooks.json 重新接线三事件；`store_nudge_every` 恢复默认 1；补齐 0.5.4 时代的两块演进——`engine_last_store()` 问引擎（agent 直接 `rsrs remember` 也算近期落库、不再误催）与 `src=hooklog/src=engine` 留痕区分；输出仍走 WorkBuddy 协议 `hookSpecificOutput.permissionDecision=deny`。
- 模型可见文本全量英文化（dimcode 0.5.6 同款）：RULES / NO_RSRS / LOGIN_NUDGE / EMPTY_NUDGE / NO_MODEL / PROBE_FAIL / STORE_NUDGE、落库回执、召回头行全部改英文；「记：」「store:」前缀兼容不变。
- 新增输入侧疑似凭据扫描（`contains_secret`）与 `$skill:` 技能指认前缀剥除（对齐 qoder 0.6.8）；命中 prompt 不召回也不落库，注入 `SECRET_SKIP` 提示。
- 安装与注册口径对齐 CLI 现状：`rsrs-cli@latest`；本机 `rsrs register` 直注、无网站步骤。
- 测试 37 → 41：断言随英文输出同步；新增疑似凭据不召回 / 不落库两条；Windows 下 stub 引擎包一层 `.cmd`（python 脚本不能被 CreateProcess 直接 exec，此前桩测试在本机全数误报失败）。

## 0.4.0 — 2026-10-29

新增**连接器形态**：插件 hooks 在桌面端实测不被加载，故把 rsrs 另做一份官方连接器（CLI+Skill），连接器页可见、技能 `respire-memory` 按需调用。

- 新增 `connector/`：`connector-meta.json`（市场条目）、`cli.json`（init / versionCheck / auth / unAuth / status + `statusMatch "User\s+PASS"`）、`icon.svg`、`skills/respire-memory/SKILL.md`
- 新增 `connector/install_local.py`：本机安装/卸载，把包按桌面端认的布局落盘六处——市场注册、插件缓存、安装条目、`enabledPlugins`、连接器市场包目录＋索引＋图标、`connector-states.json` v4 启用态（`bound/enabled` 双真）；改动前一律备份
- 命名避让：本地插件名 `respire-connector`（不能与记忆插件 `respire` 同名），技能名 `respire-memory`
- `cli.json` 相较初版补 `versionCheck`、win32 命令改 `rsrs.cmd`
- README 增「连接器形态」一节

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
