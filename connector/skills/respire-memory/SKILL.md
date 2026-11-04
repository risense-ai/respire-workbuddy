---
name: respire-memory
version: 1.0.0
description: respire (rsrs) local encrypted memory, exposed as MCP tools. EXPLICIT ONLY — call memory_recall when the user asks (记忆, 翻忆, 查上次, recall, 我们之前定的…), never proactively each turn. Store with memory_remember only when the user asks to save. Also memory_show/chain/tree to read bodies and causal chains, memory_diary* for date-anchored fragments. Triggers: 记忆, 翻忆, 查上次, 记下来, 存记忆, recall, what did we decide before, 整理记忆.
---

# respire memory · MCP playbook

Memory lives encrypted on this device and works offline; cloud sync uploads ciphertext only. **These are MCP tools provided by the respire connector — call the tools directly. Do not shell out to `rsrs`.**

## Recall trigger (explicit only — hard)

1. **Call `memory_recall` only when the user explicitly asks**: 记忆 / 翻忆 / 查上次 / 之前那个 / 我们怎么定的 / recall / save this / 整理记忆 — or when the turn plainly continues a thread that opened with one of those.
2. **Do NOT recall proactively.** No `memory_recall` at the start of an unrelated turn, no "just in case" lookups. If the user did not ask for memory, do not touch memory this turn.
3. On an explicit recall, run `memory_recall` with `query` = 2–3 keywords from what they actually asked, `limit=5`. Hits → `memory_show` the full body, then cite it as memory (not as a current fact). No hits → say so and move on; do not retry the same query.
4. **Store only when the user asks to save** (`记：`, 记下来, 存一下, save this, or an explicit "把这条记进去"). Never write a memory as a side effect of answering something else.

This is deliberate: automatic per-turn recall and auto-store are noise the user has explicitly rejected. Be silent unless asked.

## Prerequisites

- The respire connector must be connected (its MCP server responds). If it is not, ask the user to connect it in Connector Management; never enter their password.
- Cloud sync is optional: the store works without login. Login (`rsrs login`, run by the user) is only needed to sync across devices.

## Store placement rules (hard)

1. **Judge before store.** `memory_remember` without `force` runs an internal recall first — high similarity means merge (`merge_ids`), medium means attach (`parent`). Never bypass with `force`.
2. **Read before you write.** Before any memory write, read the same-topic candidates in full with `memory_show`. Apply **update > merge > attach > new** in that order.
3. **A new `important` record MUST have a real, reasonable parent whose full body you have read.** Only after that review may you call `memory_remember` with `importance=important` and `parent=<id>`. If no such parent exists, leave it pending.
4. **DO NOT** guess a parent, pass `force=true`, or downgrade importance to bypass rule 3. **DO NOT** write in read-only/off mode or change that mode to enable a write.
5. **Title must be a complete fact sentence**: subject + action + result. Not "discussion about connectors".
6. **After a real write, verify** with `memory_show` on the returned id — check id, title, and full body. If the outcome is unknown, **do not retry automatically and do not claim success**; verify read-only.

## Tools

| Tool | Parameters (*required) | Purpose |
| --- | --- | --- |
| `memory_recall` | query*, limit, related | Semantic recall (local BGE + keyword fusion, no network) |
| `memory_remember` | content*, title, parent, merge_ids, force, importance, type, see_also, supersedes | Store a memory (judge-then-store) |
| `memory_show` | id* | Full body, including causal context (never truncated) |
| `memory_chain` | id*, depth | Ancestors + this entry + descendants in one call |
| `memory_tree` | outline, from, depth | Causal forest / subtree / full-depth outline |
| `memory_attach` | id*, parent* | Explicit reparent (no judging, direct) |
| `memory_update` | id*, content, title, importance, kind, tags | Edit an existing record |
| `memory_list` | limit | Recent records |
| `memory_status` | — | Store status (data dir, session, counts) |
| `memory_taxonomy` | — | The 23 built-in catalog roots |
| `memory_history` | id, limit | Change audit (create/update/delete/restore) |
| `memory_diary` | date, from, to, contains, limit | Diary time chain (trivial zone included) |
| `memory_diary_search` | query*, limit, mode, max_chars | Cross-date diary fragments; scores are relevance, not credibility |
| `memory_diary_fragment` | fragment_id*, source_id*, max_chars, neighbors | Bounded fragment read; rejects changed/missing locators |
| `memory_extract` | confirm, dry_run, since, limit, parent, importance | Batch-import local coding-agent sessions — **always `dry_run=true` first** |
| `memory_query_log_mark` | ids*, good, bad | Self-grade recall candidates (chosen / rejected) |

## Common flows

1. **Explicit recall**: user asks → `memory_recall` with 2–3 different wordings of *what they asked* (synonyms, hypernyms, English) → on hits, `memory_show` the full body before citing it. Not asked → skip entirely.
2. **Storing** (only when asked to save): recall same-topic candidates → `memory_show` them → apply update > merge > attach > new → after writing, `memory_show` the id to verify.
3. **Organizing**: `memory_tree` with `outline=true` to see the tree → `memory_attach` to re-attach in bulk → `memory_history` to review.

## Envelope and boundaries

- Recall hits carry a `score`: **relevance, not confidence**. Never treat it as evidence; `memory_show` the original before citing.
- A single memory is not a current fact — it can be stale. Re-verify anything time-sensitive against live sources.
- `memory_extract` writes in bulk: `dry_run=true` first, then `confirm=true`.
- `memory_diary_search` scores are relevance, not credibility.

## Red lines

- Never put passwords, ID numbers, phone numbers, card numbers, or private keys into memory bodies or query terms; record only where they are stored.
- Confirm before deleting. Once a tombstone propagates to the cloud, reviving needs the full id — **when unsure, do not delete**.
- Never present a memory as an established current fact without checking it.
