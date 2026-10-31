# respire

> 吸即存，呼即取——给 WorkBuddy agent 装上本地加密记忆。

`respire` 是 WorkBuddy 标准内容插件：以命令钩子把 [respire（CLI 名 rsrs）](https://www.npmjs.com/package/rsrs-cli) 记忆引擎挂进 agent 循环——每轮标题档自动召回、「记：」一前缀即落库。本地优先、端侧加密、云端 LWW 同步；**不带自定义安装脚本，按 WorkBuddy 插件市场标准安装**。

## 数据存储安全

1. **可离线使用**：记忆库是本机本地库，新配置即离线模式——不联网、不注册、不登录，召回与落库照常；离线期间的写入留在本地队列不丢，联网登录后随 autosync 自动补同步。
2. **同步到云端的是密文**：记录在本地加密后才上传，服务端只存加密记录；解密、索引、检索全在设备端完成，服务端不需要模型、也拿不到账户解密密钥——云端与运维方可见的只有密文。
3. **企业可自建同步服务器**：服务端 `respire-server` 支持私有化部署（Docker Compose + Postgres），可整套架在企业内网离线运行，把同步端点指向自建服务即可，数据不出企业网络（部署步骤见 respire-docs《自托管》）。

## 不装模型完全可用（降级是一等公民）

- **注册、登录、同步、召回全不依赖端侧模型**——装完插件即可用，未装模型时引擎自动走词面档（等同 memlite 未配嵌入的效果）。
- BGE-M3（量化版，下载约 570 MB：onnx 件约 543 MiB ＋ tokenizer 约 17 MB）是**纯可选增强**：想要更好的语义召回再 `rsrs model install && rsrs model activate m3`，插件检测到未装会在会话内提示一句，装与不装都不报错、不拦路。

## 安装（一条脚本，走官方装载链路）

一行装（无需克隆，GitHub 远端市场直达）：

```bash
curl -fsSL https://raw.githubusercontent.com/risense-ai/respire-workbuddy/main/install.sh | bash
```

或克隆后跑安装脚本——自动定位 WorkBuddy 桌面端自带的 `codebuddy` CLI（非常规安装位可设 `CODEBUDDY_BIN=/path/to/codebuddy`），注册市场、安装插件并验证注册表与缓存落地：

```bash
git clone https://github.com/risense-ai/respire-workbuddy.git && cd respire-workbuddy
bash install.sh                # 安装；已装则升级到最新
bash install.sh --github       # 强制走 GitHub 远端市场（忽略本地仓）
bash install.sh --uninstall    # 卸载（保留市场注册，便于重装）
```

升级：重跑任一安装命令即可——git 型市场先 `marketplace update` 拉 origin 再 `plugin update`。

**装完须完全退出并重启 WorkBuddy，新会话起生效。** WorkBuddy 正在运行时写入可能被其内存态覆盖——若重启后没生效，退出 WorkBuddy 再跑一次脚本即可。

手动兜底（脚本失效时）：

```bash
codebuddy plugin marketplace add <本仓绝对路径> --name risense-workbuddy
codebuddy plugin install respire@risense-workbuddy
```

GUI 未证实存在插件安装入口；若你的版本有（插件页 → 市场 → 添加本地市场），走 GUI 亦可。

仓结构＝标准两层：仓根 `.codebuddy-plugin/marketplace.json` 是市场清单，插件本体在 `plugins/respire/`（其内 `.codebuddy-plugin/plugin.json` 为插件清单）。

引擎（rsrs CLI）缺失时插件会在会话内注入装法（`npm i -g rsrs-cli@latest`），可让 agent 代装。**新会话起生效。**

安装位置：`~/.workbuddy/plugins/cache/risense-workbuddy/respire/<版本>/`（WorkBuddy 标准缓存，随市场自动更新）。

验证：

```bash
ls ~/.workbuddy/plugins/cache/risense-workbuddy/respire/*/    # .codebuddy-plugin、hooks、skills 齐
echo '{"prompt":"respire 测试"}' | python3 ~/.workbuddy/plugins/cache/risense-workbuddy/respire/*/hooks/respire.py UserPromptSubmit
```

## 连接器形态（hooks 之外的第二种装法）

实测桌面端**不加载插件自带的 hooks**，只有 `settings.json` 用户级钩子会跑；想要「连接器页可见、按需调用」这条路，用仓库里的 `connector/`：

```bash
python3 connector/install_local.py              # 装 / 升级（幂等）
python3 connector/install_local.py --uninstall  # 卸（保留市场注册）
```

1. `connector/` 是官方开放平台（open.workbuddy.cn）的提交源：`connector-meta.json` ＋ `cli.json` ＋ `icon.svg` ＋ `skills/respire-memory/`
2. `install_local.py` 把包按桌面端认的布局装到 `~/.workbuddy`（六处落盘，全程备份），装完**完全退出并重开**才生效
3. 两种形态可共存：插件名分别是 `respire`（钩子自动召回）与 `respire-connector`（技能 `respire-memory` 按需调用 `rsrs`）
4. 细节与上架步骤见 [`connector/README.md`](connector/README.md)

## 定位：安装器 ＋ 管理器 ＋ 正常钩子

插件只做三件，装完自走一条生命周期：

1. **引擎未装时＝安装器**：SessionStart 把安装命令直接注给 agent 代跑（`npm i -g rsrs-cli@latest`＋权限兜底＋`rsrs --version` 验证），并顺手交代配置下一步（rsrs.rs 注册／`rsrs register`／模型可选）——无需用户手动操作；
2. **检测就绪＝自动切正常钩子**：每轮实时探测，引擎装完**同会话内**即恢复简则、召回与「记：」落库；
3. **管理器三档开关**（见下「启用与关闭」）。

## 启用与关闭

| 档 | 怎么关 | 范围 |
| --- | --- | --- |
| 单轮 | prompt 前缀 `/nomem` | 只关本轮召回 |
| 总开关 | `hooks/respire.config.json` 设 `"enabled": false` | 记忆层全线静默（简则/召回/落库），hook.log 留 `disabled` 痕 |
| 只关存催 | `hooks/respire.config.json` 设 `"store_nudge_every": 0` | Stop 钩子保留注册但检查静默，召回与落库不受影响 |
| 组件级 | WorkBuddy 插件页对 respire 的 **hook 组件**逐项开关（`skill`/`hook`/`mcp` 原生支持） | WorkBuddy 侧直接卸力 |

## 装上后发生什么

| 时机 | 行为 |
| --- | --- |
| `SessionStart` | 注入记忆层简则（何时翻忆、如何落库、红线），对整会话生效；**一次探测三态**——未登录附注册引导（rsrs.rs 注册、`rsrs register` 首设备、`rsrs login --oauth --no-open` 代开授权链接）、库空（<10 条）附首日存料与导入引导、缺语义模型附**可选**装法；常态零打扰 |
| `UserPromptSubmit` | 自动 `rsrs recall --titles`：**标题档注入**——只给分数＋8 位短 id＋标题，正文由 agent `rsrs show <id>` 按需取（附因果链）；默认**直出不过滤**，噪音边界＝rsrs skip 门＋limit 5＋标题档 |
| `prompt` 以「记：」「存：」「remember:」开头 | 直接 `rsrs remember … --importance important` 落库并回执；判后即存判为相似时**不写入**、回执转述候选（`--parent` 挂靠或 `--force` 直写），由模型决断；回执硬约束 AI 抽「主语＋动作＋结果」事实句 `retitle` 替换暂拟题 |
| `Stop`（AI 干完活） | **默认注册**（0.4.1 恢复），存储检查续跑一轮催存；`store_nudge_every` 节流——默认 1=每轮检查，设 0 关闭、设 N 每 N 轮一次。防误催三道：`stop_hook_active=true` 放行；近 10 分钟本层已落库不催；近 10 分钟引擎侧有落库（agent 直接 `rsrs remember` 也算）同样不催 |
| `prompt` 以 `/nomem` 开头 | 本轮跳过召回 |
| `skills/respire` | 按需加载的操作法（recall/remember/show/forget/sync 与信封解析要点）；**注意技能只是说明书，动作全由钩子驱动** |

## 首次使用 · 三件事

1. **注册登录**（开箱即用，不依赖模型）：[rsrs.rs](https://rsrs.rs) 注册 → 本机 `rsrs register`；日常 `rsrs login` 浏览器授权；autosync 常开，`rsrs sync` 手动同步，`rsrs status` 查态。
2. **导入既有记忆与规则（一次成库，LLM 代抽）**：开个 WorkBuddy 新会话粘贴下面整段——

   > 请把本机 WorkBuddy 的既有规则与记忆导入 respire：逐个读取——`~/.workbuddy/SOUL.md`、`~/.workbuddy/USER.md`、常用项目根下的 `AGENTS.md`/`CODEBUDDY.md` 与 `.workbuddy/skills/*/SKILL.md`；抽出可复用的事实、约定、教训与红线（口令、证件号、卡号、私钥一律排除、只记位置），去重后用 `rsrs remember` 分条存入（`--importance important`、标题按事实句；判重给候选先决断挂靠或合并），存完给我一份清单。

   空库首日 SessionStart 会注入同一线索。
3. **端侧模型（可选增强）**：`rsrs model install && rsrs model activate m3`——不装完全可用，想要更好语义召回再装。

## 调优（可选）

`~/.workbuddy/plugins/cache/risense-workbuddy/respire/<版本>/hooks/respire.config.json`（缺失即全默认，改完新会话生效；**不涉及登录与账号**）：

| 字段 | 默认 | 含义 |
| --- | --- | --- |
| `rsrs` | `""` | 引擎路径；空 = 自动探测（PATH → `~/.npm-global/bin` → `~/.local/bin` → `~/.rsrs/bin` → `/usr/local/bin` → `/usr/bin`） |
| `recall_threshold` | `0.0` | 召回下限；**0=默认关（rsrs 直出）**，设正数才启用过滤 |
| `recall_limit` | `5` | 取前 N 条 |
| `min_prompt_chars` | `2` | 1 字才跳，2 字起即查 |
| `session_rules` | `true` | 是否注入 SessionStart 简则 |
| `budget_chars` | `1500` | 单轮注入总预算（标题行远短于此） |
| `enabled` | `true` | **总开关**：false=全线静默 |
| `store_nudge_every` | `1` | Stop 存储检查节流：1=默认每轮检查、N=每 N 轮一次、**0=关闭**（Stop 钩子仍注册，仅检查静默） |
| `log` | `true` | `hooks/hook.log` 留痕（超 256KB 清轮，口令/token/长数字自动打码） |
| `skip_prefixes` | `[]` | 宿主内部提示白名单：prompt 以列表中任一前缀开头（大小写不敏感）则本轮不召回也不落库——宿主给自动化任务写 Recap 之类时按需加 |

过滤策略：**默认不设阈值**——三层已框住噪音：rsrs skip 门、limit 5、标题档。历史教训：阈值 0.56→0.31 每降一次都是真相关被拦的补救，漏召代价远大于多看两行标题。

## 卸载

首选 `bash install.sh --uninstall`（走官方 CLI，注册表干净）。CLI 失效时搬移式兜底，**目标必须在 plugins 根之外**（根内带 manifest 的残留目录会被当插件继续加载、钩子双跑）：

```bash
mv ~/.workbuddy/plugins/cache/risense-workbuddy/respire ~/.workbuddy/plugins-backup/respire.removed-$(date +%s)
codebuddy plugin uninstall respire@risense-workbuddy
```

## 设计要点

- **fail-open**：hook 任何异常 → 空 stdout + `exit 0`，永不拦会话；失败必留痕于 hook.log
- **纯文本输出**：stdout 即 additionalContext，没有误拦面；Stop 走 `hookSpecificOutput.permissionDecision`（WorkBuddy 现协议），不用已弃用的 `decision:"block"`
- **标题档注入**：`recall --titles` 只回 id/score/title，正文交 `show` 按需拉取；`superseded_by` 标「已被取代」
- **判后即存尊重设计**：落库不带 `--force`，`pending` 候选原样转述给模型决断
- **`${CODEBUDDY_PLUGIN_ROOT}` 占位符**：WorkBuddy 运行时替换为插件安装根，跨机器自洽；command 带 `python3 || python || py -3` 回退链（Windows 宿主以 cmd.exe spawn 钩子，`python3`/`python` 可能被 Microsoft Store 别名桩接管，`py` 启动器随官方安装器入 PATH 作第三回退）
- **包内自检**：`python3 plugins/respire/scripts/validate_plugin.py`（结构/清单/hooks 形状/可编译/fail-open/敏感扫描），分发前必跑

## 已知边界

- **召回质量是引擎上限**：用词鸿沟下 BGE-M3 可能漏召真条——简则已约束模型「命中不贴题换词补查」（同义词/上位词/英文词分路）
- **冷启动窗**：runtime 冷启＋模型加载实测 7s+，故 hook timeout 20s、recall 14s、probe 10s；探测失败时 SessionStart 注入诊断段
- **PostCompact 不可重注**（协议该事件仅副作用）：长会话压缩后简则如丢失，开新会话即复
- **留痕**：`hooks/hook.log` 每事件一行（ts/ev/out/ms/d 含 query 摘要），按行复盘「灵不灵」

## 测试

```bash
python3 plugins/respire/scripts/validate_plugin.py   # 包结构自检
bash plugins/respire/tests/test_hooks.sh             # 行为断言（桩引擎全分支＋真机只读，不碰真库）
bash plugins/respire/tests/test_hooks.sh --store     # 加写探针（写真库→回执→rsrs forget 自清理）
```

rsrs 无 data-dir 隔离（runtime 单例＋全局 client.json），故写测试仅在显式开启时进行，即写即忘。

## License

MIT
