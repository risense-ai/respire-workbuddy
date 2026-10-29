---
name: respire-memory
description: 睿思记忆（rsrs）本地加密记忆库的操作法：recall 语义召回、remember 判重落库、show/chain 读全文与因果链、forget 墓碑删除、sync 同步、status 查态。用户提到「记忆、翻忆、查上次、记下来、存记忆、忘掉、同步、整理记忆」时使用。触发词：记忆、翻忆、recall、remember、存记忆、忘掉、同步。
---

# 睿思记忆 · 操作法

CLI 为 `rsrs`（npm 包 `@rsrsai/cli`）。记忆库在本机加密存储，可离线使用；云同步只上传密文。

## 前置

- 已连接（`rsrs status` 的 `User` 行为 `PASS`）。未连接时先请用户完成连接，不要代为输入密码。
- 一切命令加 `--json` 取结构化输出；进度写 stderr，**不要 `2>&1`**，否则 JSON 被污染。

## 命令

| 目的 | 命令 | 关键参数 |
| --- | --- | --- |
| 语义召回 | `rsrs recall "<项目名+关键词>" --limit 5 --json` | `--titles` 只要短 id＋标题；`--limit N` 条数 |
| 落库 | `rsrs remember "<内容>" --title "<事实句>" --importance important --json` | `--parent <id>` 挂到某条之下；`--merge-ids "a,b"` 合并；`--force` 跳过判重 |
| 读全文 | `rsrs show <短id> --json` | 短 id 取前 8 位 |
| 因果链 | `rsrs chain <id> --depth 3 --json` | 一次取祖先＋本条＋后代 |
| 判重候选 | `rsrs candidates "<内容>" --json` | 存前看有没有同题 |
| 清单 | `rsrs list --limit 10 --json` | `--since <日期>` 收下界 |
| 改标题 | `rsrs retitle <短id> --title "<新标题>"` | 标题须「主语＋动作＋结果」 |
| 删除 | `rsrs forget <id> --json` | 墓碑删除，随同步传播；`restore <完整id>` 可复活 |
| 同步 | `rsrs sync --json` | 平时 autosync 常开，手动才阻塞 |
| 查态 | `rsrs status --json` | 登录态、条数、索引状态 |
| 完整工作流 | `rsrs prompt` | 归档规范全文（放置、判级、三段体） |

## 常见流程

1. **答前**：`recall` 换 2–3 组词（同义词、上位词、英文词）；命中后 `show` 读全文再引用。
2. **落库**：先 `candidates` 判重 → 同题且事实已变用 `rsrs update <id> --content/--title`；同题多散条用 `remember --merge-ids`；确为新事实才 `remember --parent <挂点>`。
3. **整理**：`rsrs tree --outline --json` 看树 → `rsrs resort --spec '{\"ops\":[{\"id\":\"子\",\"parent\":\"父\"}]}' --go` 批量改挂（默认 dry-run）。

## 返回信封

所有 `--json` 命令统一返回 `{status, summary, items, details, errors}`：

- 失败是 `status:"fail"` ＋ `errors[]`，退出码可能仍为 0——**判 status 不判退出码**。
- `recall` 的命中在 `details[]`：`score`（相关度，不是可信度）、`id`（全 id）、`title`、`superseded_by`。
- `remember` 三态：`ok`＝已写入（`summary.id`）；`pending`＋`written:false`＝判为相似**未写入**，须改用 `--parent` 挂靠或 `--force` 直写；其余为失败。

## 红线

- 口令、证件号、手机号、卡号、私钥不得写入记忆正文或查询词，只记存放位置。
- 删除前确认；`forget` 传播到云端后需 `restore <完整id>` 才能恢复。
- 不要把召回分数当可信度；引述记忆前先 `show` 看原文。
