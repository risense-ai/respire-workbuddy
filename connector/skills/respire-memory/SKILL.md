---
name: respire-memory
description: respire (rsrs) local encrypted memory playbook: recall for semantic search, remember to store after dedup, show/chain to read full bodies and causal chains, forget to tombstone-delete, sync to synchronize, status to check state. Use when the user mentions memory, recall, what happened last time, save this, forget, sync, or organize memory. Triggers: memory, recall, remember, store memory, forget, sync, 记忆, 翻忆, 查上次, 记下来, 存记忆, 忘掉, 同步, 整理记忆.
---

# respire memory · playbook

The CLI is `rsrs` (npm package `rsrs-cli`; `@rsrsai/cli` is the same CLI). The memory store is encrypted locally and works offline; cloud sync uploads ciphertext only.

## Prerequisites

- Connected (the `User` line of `rsrs status` reads `PASS`). If not connected, ask the user to connect first; never enter their password.
- Every command takes `--json` for structured output; progress goes to stderr — **never `2>&1`**, or the JSON gets polluted.

## Commands

| Purpose | Command | Key parameters |
| --- | --- | --- |
| Semantic recall | `rsrs recall "<project name + keywords>" --limit 5 --json` | `--titles` for short id + title only; `--limit N` for count |
| Store | `rsrs remember "<content>" --title "<fact sentence>" --importance important --parent <reviewed-parent-id> --json` | `--parent <id>` attaches under a record; `--merge-ids "a,b"` merges; new important records require a reviewed reasonable parent; no force bypass |
| Read full body | `rsrs show <short-id> --json` | short id = first 8 chars |
| Causal chain | `rsrs chain <id> --depth 3 --json` | ancestors + record + descendants in one call |
| Dedup candidates | `rsrs candidates "<content>" --json` | check same-subject records before storing |
| List | `rsrs list --limit 10 --json` | `--since <date>` lower bound |
| Retitle | `rsrs retitle <short-id> --title "<new title>"` | title must be "subject + action + result" |
| Delete | `rsrs forget <id> --json` | tombstone delete, propagated by sync; `restore <full-id>` revives |
| Sync | `rsrs sync --json` | autosync runs normally; manual sync blocks |
| Status | `rsrs status --json` | login state, record counts, index state |
| Full workflow | `rsrs prompt` | the complete archiving policy (placement, grading, three-section body), on demand |

## Common flows

1. **Before answering**: `recall` with 2–3 different wordings (synonyms, hypernyms, English); on hits, `show` the full body before citing it.
2. **Storing**: Before any memory write, you MUST read rsrs prompt, recall same-topic candidates, and use rsrs show <id> to read their full bodies. Apply update > merge > attach > new in that order; use the existing CLI for updates/merges. A new important record MUST have a real, reasonable parent whose full body you have read. ONLY AFTER that review may you use rsrs remember with --importance important --parent <id>; if no such parent is available, remain pending. DO NOT guess a parent, use --force, or downgrade importance to bypass this requirement. DO NOT write in read-only/off mode or change that mode to enable a write. Use literal body markers required by engine policy; DO NOT translate them. The title MUST be a complete subject + action + result fact sentence. After an actual write, you MUST use rsrs show to verify the id, title, and full body. If the actual write outcome is unknown, DO NOT retry automatically or claim success. Verify read-only; DO NOT resend the write.
3. **Organizing**: `rsrs tree --outline --json` to view the tree → `rsrs resort --spec '{\"ops\":[{\"id\":\"child\",\"parent\":\"parent\"}]}' --go` to re-attach in bulk (dry-run by default).

## Return envelope

All `--json` commands return `{status, summary, items, details, errors}`:

- Failures are `status:"fail"` plus `errors[]`, and the exit code may still be 0 — **judge by status, not the exit code**.
- recall hits live in `details[]`: `score` (relevance, not confidence), `id` (full id), `title`, `superseded_by`.
- ok/warn with a valid id means written; DO NOT resend. Pending means nothing was written. If an actual write outcome is unknown, DO NOT resend or claim success; verify read-only.

## Red lines

- Never put passwords, ID numbers, phone numbers, card numbers, or private keys into memory bodies or query terms; record only where they are stored.
- Confirm before deleting; once `forget` propagates to the cloud, `restore <full-id>` is required to revive it.
- Never treat recall scores as confidence; `show` the original text before citing any memory.
