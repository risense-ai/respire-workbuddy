# Changelog

## 0.1.0 — 2026-10-20

首版：respire 由 Dim 插件移植为 WorkBuddy 标准插件。

- 形态：`.codebuddy-plugin/plugin.json`（WorkBuddy 清单）＋ `.codebuddy-plugin/marketplace.json`（本仓自为市场，source `./`），按 WorkBuddy 插件市场标准安装，无自定义 install.sh。
- 钩子三事件（与 Dim 版同源，协议按 WorkBuddy 改写）：
  - `SessionStart`（matcher `startup|resume|clear|compact`）：注入记忆层简则；未装引擎则注入安装引导（`npm i -g @rsrsai/cli@latest`，agent 代装）；已装则一次探测三态（未登录/空库/缺模型）按需附引导，常态零打扰。
  - `UserPromptSubmit`：每轮 `rsrs recall --titles` 标题档注入（分数＋8 位短 id＋标题，`superseded_by` 标「已被取代」）；prompt 以「记：/存：/remember:」开头直接落库并回执，判后即存判相似时转述候选待模型决断；`/nomem` 关本轮。
  - `Stop`：存储检查续跑一轮（`hookSpecificOutput.permissionDecision`，不用已弃用的 `decision:"block"`）；`stop_hook_active=true` 防循环；`store_nudge_every` 节流；近 10 分钟已落库不催。
- 协议适配：事件名/字段走 WorkBuddy 信封（`hook_event_name`/`prompt`/`stop_hook_active`/`source`），占位符用 `${CODEBUDDY_PLUGIN_ROOT}`（兼容 `python3 || python` 回退链，无 `commandWindows`——WorkBuddy schema 不含该字段，改由 `shell` 字段与回退链兜底）。
- 文案：`rules`/`empty`/`login` 引导改指 `~/.workbuddy/`（SOUL.md、USER.md）而非 Dim 的 `~/.dimcode/`。
- 落库协议：`rsrs remember --importance important`（引擎判后即存：`status:"pending"` + `written:false` 时不写入，转述候选）；回执催 `retitle` 替换暂拟题。
- 引擎探测链扩展：`~/.npm-global/bin/rsrs`、`/usr/local/bin/rsrs` 入列（本机 npm 前缀安装与系统安装并存）。
- 模型体积口径：BGE-M3 量化版 onnx 件约 570 MB（tokenizer 约 17 MB），激活时同目录生成 cpu-v1.ort 再占约 543 MiB，目录总占用约 1.1 GB；非 fp16 的 1.1G 单件。
- 测试：桩引擎全分支 25 断言（不碰真库）＋真机只读分支，`--store` 显式写探针（写→断言→forget 自清理）；`scripts/validate_plugin.py` 结构/清单/hooks 形状/fail-open/敏感扫描自检。
