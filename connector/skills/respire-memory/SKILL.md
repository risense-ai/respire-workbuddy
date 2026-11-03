---
name: respire-memory
version: 1.0.0
description: respire (rsrs) local encrypted memory, exposed as MCP tools. ALWAYS recall first — run memory_recall at the start of every turn before answering, then memory_remember at the end if anything new happened. Also memory_show/chain/tree to read bodies and causal chains, memory_diary* for date-anchored fragments. Triggers: every turn, memory, recall, remember, what happened last time, save this, 记忆, 翻忆, 查上次, 记下来, 存记忆, 整理记忆.
---

# respire memory · MCP playbook

Memory lives encrypted on this device and works offline; cloud sync uploads ciphertext only. **These are MCP tools provided by the respire connector — call the tools directly. Do not shell out to `rsrs`.**

## Trigger (hard — this is why the connector exists)

1. **On every user turn, before giving any substantive answer**, call `memory_recall` once with `query` set to 2–3 keywords from this turn (nouns + intent, plus an English synonym if the Chinese term is ambiguous) and `limit=5`.
2. Hits → `memory_show` the full body, then cite it as memory (not as a current fact). No hits → answer directly; **do not retry with the same query**.
3. Skip only for bare social turns with no referent (`你好`, `谢谢`, `好的`).
4. **At the end of the turn**, if a new fact / decision / agreement / lesson / pitfall appeared, `memory_remember` it (rules below). If nothing new happened, store nothing.

Without step 1 the memory store is dead weight — the tools sit unused. Do not wait for the user to say "recall".

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

1. **Before answering**: `memory_recall` with 2–3 different wordings (synonyms, hypernyms, English); on hits, `memory_show` the full body before citing it.
2. **Storing**: recall same-topic candidates → `memory_show` them → apply update > merge > attach > new → after writing, `memory_show` the id to verify.
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
