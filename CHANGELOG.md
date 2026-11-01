# Changelog

## 0.4.8 — 2026-11-01 · 第五轮：generation-scoped 锁文件（原子 claim 终案）

### Fixed

- **gen-scoped latch（R5）**：锁文件名包含 generation 哈希（`.latch_<sid>_<genhash>`）——**新 generation 天然获得新锁文件**（首个 Stop 可 claim），**旧 generation 的锁/迟到事件与新 generation 互不影响**（不同文件）；**无需删除锁来重武装**（消除删除路径的一切失败窗口——R4 的读比较+写+删锁三步非原子，迟到/并发/读取失败三个边界全部突破）。Stop 事件同样读取 `generation_id` 并传入 `latch_claim`——迟到旧 gen Stop 用旧 gen 自己的锁（不消耗新 gen 预算）；同 gen 的 Stop 共享同一锁文件（重复/并发/迟到只 claim 一次）。无 generation 的旧宿主回落单一锁文件+删除重武装（既有行为）。复审三个反例（迟到 g1 覆写、读取失败重删锁、同 gen 并发双 rearm）在 gen-scoped 文件名隔离下**结构性不可能**。

## 0.4.7 — 2026-11-01
## 0.4.7 — 2026-11-01 · 第四轮：generation 感知的一次收尾锁

### Fixed

- **官方 generation_id 契约（R4）**：[CodeBuddy Code v2.144.0+](https://www.workbuddy.ai/docs/cli/release-notes/v2.144.0) 的 UserPromptSubmit 携带 `generation_id`（同对话回合稳定、可与 Stop 关联）——`mark_prompt(session, generation)` 现按 **session+generation** 关联判定：**同 generation 重投/迟到/并发事件不重新武装 latch**（先比较 `st_<sid>.gen` 再决定删锁；同 gen 直接跳过 rearm）；**旧 generation 迟到不撤销新 generation 的保护**（gen 不同→忽略，不 rearm 不覆写 gen 文件）；**不同 generation 同文本正常新一轮**（正常 rearm）。无 generation_id 的旧宿主保持既有行为（每次 rearm），README 注明版本边界。gen 文件读不到时保守 rearm（兼容方向）；写入失败不影响 rearm（latch 是硬保证）。状态读取/持久化失败均保守放行，不依赖失败后继续 deny。

### Changed

- 测试：CI 39/39（+3：同 gen 重投不 rearm、旧 gen 迟到不撤销新保护、无字段兼容行为）。

## 0.4.6 — 2026-11-01
## 0.4.6 — 2026-11-01 · 第三轮复审整改（PR #5 复审三项 P2，移植 zcode/dimcode 已合并终案）

### Changed

- **R3#1 取消磁盘凭证免催（终案，同 zcode 0.1.9 / dimcode 0.5.14 复核⑥）**：同会话 `_state_update`（load→patch→rename）无锁 RMW 可被两进程屏障交错恢复旧请求凭证（复审已复现：新 prompt_ts 被旧快照回滚、旧代 store_req_ts 重新生效、turn_stored=True 误免催）——跨事件（UserPromptSubmit→Stop 是两个独立 hook 进程）不存在可靠的「当前请求」磁盘身份，失败-恢复窗口无法闭合。按终案**取消免催优化**：`turn_stored` 恒 `False`，`on_stop` 删除该调用分支（latch 落锁即催）——防重唯一依据回归 latch 语义（nudge 时 `O_EXCL` 创建、下一次真实 prompt 删除）。「记：」写回执仍诚实输出给模型（告知已存）；`st_<sid>.json` 状态文件保留为诊断轨迹，不再影响 Stop 决策。
- **R3#2 畸形 ID／回读类型严格化**：写回执 id 必须**原生字符串**（JSON 数字 12345678 不做 `str()` 强转）且匹配**标准 UUID 或 16+ 位连续 hex** 白名单（`a-------` 这类宽松 hex-连字符不算）——否则按不可确认归 unknown（不 Saved、不引导重发）。`show` 回读改**三方 id 一致**：summary.id 与 entry.id 均须原生字符串且 === 写入 id（entry.id 错/缺失 → mismatch，不再只核 summary.id）；title/content 须 `isinstance(str)` 后再比对（数字 42 ≠ "42"，不做强转）——类型异常归 mismatch，已写的 Saved 回执保留、绝不冒充 verified。
- **R3#3 重放边界（README 注明）**：WorkBuddy 事件流不带宿主请求/事件标识，无法区分同事件重投与用户再次发送同文本——保守按新请求处理（重新武装收尾锁），由「每请求至多催一次」的一次收尾锁兜底；不以内容哈希吞掉正常的重复提问。README Stop 行同步（免催不依赖磁盘凭证＋重放边界说明），UserPromptSubmit 行同步 id 白名单与三方 id 回读口径。
- 测试：CI 35 → 36（+畸形 ID 反例：数字 id／`a-------` → unknown 不 Saved；回读反例：entry.id 错（复审点名的 DIFFERENT 路径）／缺失／数字 content → mismatch 且 Saved 保留；store 后 Stop 仍催、同请求二次 Stop 由 latch 放行；TurnStateFiles 全组翻转为恒 False 并补诊断轨迹存在性断言；Stop 期望 argv 序列改空——launcher 放宽空序列断言，Stop 期间任何 subprocess 即拒绝）；bash 87/0 保持（「记：成功后免催」翻转为仍催 deny，A/B 会话段同步 latch 语义命名，屏障与独立文件断言保留）；版本三方同步 0.4.6。

## 0.4.5 — 2026-11-01 · 复审第二轮整改（PR #5 复审三项 P2）

### Fixed

- **R2#1 内部提示不得重新武装收尾锁**：`on_prompt` 辨别顺序改为 空检查 → `/nomem`（真实请求：mark 后只跳召回）→ `skip_prefixes` 内部白名单（**命中即返回，不 mark、不删锁、不记请求代**）→ `mark_prompt` → 凭据/快存/召回。修复序列：真实请求→Stop deny→同会话内部 Recap（配置 `skip_prefixes`）→Stop——旧顺序里 Recap 先 `mark_prompt` 删掉收尾锁，宿主未带 `stop_hook_active` 时第二个 Stop 会再次 deny；现在必放行。重复投递同一 UserPromptSubmit 文本无请求身份可去重：保守按新真实请求处理（重武装不额外伤害——锁本就只在无新真实请求时保持）。
- **R2#2 readback 坏 details 不再吞回执**：`show` 回 `status=ok` 但 `details` 非 dict（数组/字符串）时，旧代码 `(doc.get("details") or {}).get("entry")` 抛 AttributeError，异常冒到主入口被 fail-open 兜成**空输出**——已成功的 Saved 回执凭空消失。现在 `details` 加 `isinstance(dict)` 防护：非 dict 一律局部降级 **unavailable**，保留 Saved 回执与禁止重发约束。
- **R2#3 会话独立状态文件（删除共享 turn_map.json）**：prompt_ts/store_ts/请求代从共享 `turn_map.json`（读-改-写无锁，temp+rename 原子替换挡不住丢失更新——确定性交错「B 读全 map→A 新请求更新 prompt_ts→B 写回旧快照」会把 A 恢复成旧 `store_ts>=prompt_ts`，本轮没写也误免催）迁至**每会话独立 `st_<sid>.json`**（temp+rename 原子替换，各会话各写各的文件，交错无法构成；超 64 个按 mtime 收敛）。**写回执绑定请求代**：`mark_prompt` 返回本请求代 ts，`mark_store` 记 `store_req_ts`，`turn_stored` 要求 `store_req_ts==prompt_ts`——旧请求延迟到新 prompt 之后完成的写回执不免催新轮。

### Changed

- 测试：CI 29 → 35（+复审点名序列「真实请求→deny→内部 Recap→Stop 放行＋零引擎调用＋重放语义」、坏 details 数组/字符串反例、状态文件单测组×4：确定性交错屏障 B 不回滚 A、多会话并发更新不丢失、旧代写回执跨新 prompt 不免催、每会话一文件无共享 map）；bash 72/0 → 87/0（+R2#1 序列四断言、坏 details 两反例、A/B 会话独立状态文件屏障＋快照不变＋turn_map.json 移除断言、A 新请求后旧回执应催；本机含真机只读分支）；版本三方同步 0.4.5。

## 0.4.4 — 2026-11-01 · 维护者复审整改（fix/audit-result-contract-stop-failopen 复审 5 项，WB-07~WB-11）

### Fixed

- **WB-07 一次收尾锁重构（复审#1）**：`.store_turn` 单会话状态改为**每会话独立锁文件**（`O_CREAT|O_EXCL` 原子独占——并发 Stop 只有一个能落锁；锁无 TTL，25 小时后仍占用，只有新真实 prompt 删除重新武装；A→B→A 会话交错不丢锁、不互耗）；无法落锁（状态目录不可写等）一律放行——绝不无锁 deny。prompt_ts/store_ts 移入尽力维护的 per-session map（temp+rename 原子替换、仅按数量收敛），map 失败只损失免催优化，不影响一次上限保证。
- **WB-08 畸形回执归 unknown（复审#2）**：`ok`/`warn` 缺有效 id（hex/uuid 白名单校验，垃圾 id 不当有效）、非 dict summary（类型防护不再外抛）、未知 status 一律 **unknown**（不当失败、不当成功、禁重发）；`skip` = 引擎按模式拒绝（未写非失败）；仅 `fail` 断言「未接受」。
- **WB-09 共享 hook 预算（复审#3）**：remember/回读/只读核实共用一个截止时间（`RESPITE_HOOK_BUDGET_S`，默认 20s、预留 2.5s 输出余量）；慢坏回执（接近 STORE_T 才回垃圾）剩余预算不足直接 unknown，不再追加 list——unknown 回执不再可能在输出前被宿主杀掉。
- **WB-10 回读全量核验（复审#4）**：`show` 回读须 **返回 id＝写入 id ＋ 标题相等＋完整正文相等** 才称 verified；相同前缀不同结论尾部、错误 id 均 mismatch 如实标注；畸形 show 返回 unavailable 并保留已写回执。
- **WB-11 免催只认可归属凭证（复审#5）**：移除「全库最新写入时间晚于本轮 prompt 即免催」（引擎时间戳无法归属会话，B 会话写入会误免催 A）；**Stop 完全不再查询引擎**（也因此不存在查库失败强迫续跑的路径）；`/nomem` 仍算新请求（mark 提前到跳召回判断之前），重新武装收尾锁、只跳召回。

### Changed

- 测试：CI 24 → 29（+A→B→A 交错、无 TTL 老锁、状态不可写放行、Stop 零引擎查询、缺 id/垃圾 id/坏 summary 回执、错 id/尾部篡改回读、慢坏回执+紧预算零追加调用）；bash 67/0 → 72/0（轮次状态目录改 `cygpath -m` 混合路径、`PROMPT_VAL` 豁免 MSYS 环境转换、+25 小时锁仍占用、/nomem 重武装、不可写目录放行、Stop 零引擎调用断言）；版本三方同步 0.4.4。

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
