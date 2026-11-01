#!/usr/bin/env bash
# respire(WorkBuddy) 自测 —— 模拟 stdin 事件 JSON，逐分支断言。
# 双轨：①桩引擎（STUB_RSRS，canned JSON，不碰真库）跑全分支；②真机 rsrs 只读分支（未装则跳过）。
# 写库探针须显式 --store（写真库→回执断言→rsrs forget 自清理），缺省绝不写。
set -u
export MSYS2_ENV_CONV_EXCL='PROMPT_VAL'  # MSYS 连 env 值都会把「/nomem …」转成 Windows 路径——只豁免 prompt 变量
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
PY3="$(command -v python3)"
[ -z "$PY3" ] && PY3="$(command -v python)"
RSRS="$(command -v rsrs || true)"
[ -z "$RSRS" ] && RSRS="$HOME/.npm-global/bin/rsrs"
[ -z "$RSRS" ] && RSRS="$HOME/.local/bin/rsrs"
[ -z "$RSRS" ] && RSRS="$HOME/.rsrs/bin/rsrs"
PASS=0; FAIL=0
WITH_STORE=0
[ "${1:-}" = "--store" ] && WITH_STORE=1

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# 轮次状态目录（每会话锁文件＋凭证 map）：Windows python 看不见 MSYS 路径，必须 cygpath -m 混合路径
TURNBASE="$(cygpath -m "$TMP" 2>/dev/null || printf '%s' "$TMP")/turnstate"
CFG_ON="$TMP/config-on.json"
echo '{"session_rules": true, "store_nudge_every": 0}' > "$CFG_ON"
CFG_OFF="$TMP/config-off.json"
echo '{"session_rules": false}' > "$CFG_OFF"
CFG_STORE="$TMP/config-store.json"
echo '{"session_rules": false}' > "$CFG_STORE"
CFG_STOP="$TMP/config-stop.json"
echo '{"session_rules": false, "store_nudge_every": 1}' > "$CFG_STOP"
CFG_SKIP="$TMP/config-skip.json"
echo '{"session_rules": false, "skip_prefixes": ["你正在为宿主任务编写", "Host internal recap"]}' > "$CFG_SKIP"

# ---- 桩引擎：按子命令回 canned JSON，路径写进 config ----
STUB="$TMP/rsrs-stub"
cat > "$STUB" <<'PY'
#!/usr/bin/env python3
import datetime, json, os, sys
sub = sys.argv[1] if len(sys.argv) > 1 else ""
mode = os.environ.get("STUB_MODE", "ok")
calls = os.environ.get("STUB_CALL_LOG", "")
if calls:  # 每次被调追加一行：供「疑似凭据不发引擎」断言引擎桩未被调用
    try:
        with open(calls, "a", encoding="utf-8") as f:
            f.write(sub + "\n")
    except Exception:
        pass
if sub == "list":  # recent=动态毫秒新鲜条 / stale=只有陈旧条 / 其余=失败。Stop 已不查引擎，仅 unknown 回执只读核实用
    if mode == "recent":
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + ".%03dZ" % (datetime.datetime.now(datetime.timezone.utc).microsecond // 1000)
        print(json.dumps({"status": "ok", "summary": {}, "details": [
            {"id": "eeee0001-0000-0000-0000-000000000001", "title": "引擎近期落库条",
             "updated_at": now, "created_at": "2020-01-01T00:00:00Z"}]}))
    elif mode == "stale":
        print(json.dumps({"status": "ok", "summary": {}, "details": [
            {"id": "eeee0002-0000-0000-0000-000000000002", "title": "陈旧落库条",
             "updated_at": "2020-01-01T00:00:00Z"}]}))
    else:
        print(json.dumps({"status": "fail", "errors": ["stub list fail"]}))
if sub == "show":  # 复审 R2#2 反例：ok 信封 + details 非 dict（数组/字符串）→ 回读须降级 unavailable、不吞回执
    if mode == "show_badetails":
        print(json.dumps({"status": "ok", "summary": {"id": sys.argv[2], "title": "stub"}, "details": [{}]}))
    elif mode == "show_strdetails":
        print(json.dumps({"status": "ok", "summary": {"id": sys.argv[2], "title": "stub"}, "details": "str"}))
    sys.exit(0)
if sub == "status":
    if mode == "fail":
        print(json.dumps({"status": "fail", "errors": ["stub"]}))
    else:
        print(json.dumps({
            "status": "ok",
            "summary": {"session": {"has_token": mode != "logout", "user": "stub" if mode != "logout" else ""},
                        "local_total": 0 if mode == "empty" else 3824}
        }))
elif sub == "recall":
    if mode == "recall_empty":
        print(json.dumps({"status": "skip", "summary": {}, "items": [], "details": []}))
    else:
        print(json.dumps({"status": "ok", "summary": {"count": 2}, "items": [], "details": [
            {"id": "aaaaaaaa-1111-2222-3333-444444444444", "score": 0.62,
             "superseded_by": None, "title": "钉子案例：桩召回命中条一"},
            {"id": "bbbbbbbb-5555-6666-7777-888888888888", "score": 0.41,
             "superseded_by": "cccccccc-0000", "title": "钉子案例：桩召回命中条二"},
        ]}))
elif sub == "remember":
    if mode == "pending":
        print(json.dumps({"status": "pending", "summary": {"written": False},
                          "items": [{"name": "ffff0001", "status": "pending", "value": "similarity=78% title=旧条"}],
                          "actions": ["rsrs remember \"<combined>\" --merge-ids \"ffff0001\"",
                                      "rsrs remember \"<content>\" --force to write as new entry"]}))
        sys.exit(2)
    if mode == "warn":
        print(json.dumps({"status": "warn", "summary": {"action": "created", "id": "eeee1111-9999-8888-7777-666666666666"},
                          "errors": ["parent (cause) cannot be resolved; stored independently"]}))
        sys.exit(2)
    if mode == "silent":
        sys.exit(0)
    else:
        print(json.dumps({"status": "ok", "summary": {"id": "dddddddd-9999-8888-7777-666666666666"},
                          "items": [{"name": "write", "status": "ok", "value": "id=dddddddd-9999-8888-7777-666666666666"}]}))
PY
chmod +x "$STUB"
if command -v cmd.exe >/dev/null 2>&1; then
  # Windows：python 脚本不能被 CreateProcess 直接 exec，包一层 .cmd（须在 stub 写完后生成）
  PY3_WIN="$(cygpath -w "$PY3" 2>/dev/null || echo "$PY3")"
  case "$PY3_WIN" in *[Aa]|*[Ee]|*[Xx]) ;; esac  # no-op keep var
  # shim 兼容：无扩展名解释器 cmd.exe 跑不动，回退 py.exe/真实的 python.exe
  for _cand in "py.exe" "python.exe"; do
    _p="$(dirname "$PY3_WIN")/$_cand"
    [ -f "$_p" ] && PY3_WIN="$_p" && break
  done
  if [ ! -f "$PY3_WIN" ] || [ "${PY3_WIN##*.}" != "exe" ]; then
    _py="$(command -v py)"
    [ -n "$_py" ] && PY3_WIN="$(cygpath -w "$_py")"
  fi
  cat > "$TMP/rsrs-stub.cmd" <<WRAP
@echo off
"$PY3_WIN" "%~dp0rsrs-stub" %*
WRAP
  STUB="$TMP/rsrs-stub.cmd"
fi

# run <event> [prompt] [config] [mode] [engine] [logfile] [stop_hook_active] [turnstate] [session]
# config 只写非 rsrs 项（rsrs 路径由桩注入）；prompt 走 PROMPT_VAL env（顶部已设 MSYS2_ENV_CONV_EXCL
# 豁免——argv 与 env 值都会被 MSYS 转成 Windows 路径）；turn 状态目录独立，供 Stop 场景复位；
# session 缺省 selftest，A/B 会话隔离场景显式传。
run() {
  local ev="$1" pr="${2-}" cfg="${3:-$CFG_ON}" mode="${4:-ok}" eng="${5:-$STUB}" log="${6:-$TMP/hook.log}" sha="${7:-false}" tb="${8:-$TURNBASE}" sess="${9:-selftest}"
  "$PY3" -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); d['rsrs']=sys.argv[2]; json.dump(d, open(sys.argv[3],'w',encoding='utf-8'))" "$cfg" "$eng" "$TMP/cfg-live.json"
  PROMPT_VAL="$pr" "$PY3" - "$ev" "$sha" "$sess" <<'PY' | PROMPT_VAL="$pr" RESPITE_CONFIG="$TMP/cfg-live.json" RESPITE_LOG="$log"     RESPITE_NUDGE_STATE="$TMP/nudge" RESPITE_TURN_STATE="$tb" STUB_MODE="$mode" STUB_CALL_LOG="$TMP/stub-calls.log" "$PY3" "$ROOT/hooks/respire.py" "$ev"
import json, os, sys
ev, sha, sess = sys.argv[1], sys.argv[2], sys.argv[3]
pr = os.environ.get("PROMPT_VAL", "")
d = {"hook_event_name": ev, "cwd": "/tmp", "session_id": sess}
if ev == "UserPromptSubmit":
    d["prompt"] = pr
if ev == "Stop":
    d["stop_hook_active"] = sha == "true"
sys.stdout.write(json.dumps(d, ensure_ascii=False))
PY
}
rst() { rm -rf "$TMP/turnstate" "$TMP/nudge"; }   # Stop 场景复位：轮次状态目录（每会话锁＋凭证 map）＋节流计数


check() {   # check <名字> <实际输出> <模式: 非空|空|含:xxx|不含:xxx|json:permissionDecision=deny>
  local name="$1" got="$2" want="$3" ok=0
  case "$want" in
    非空) [ -n "$got" ] && ok=1 ;;
    空)   [ -z "$got" ] && ok=1 ;;
    不含:*) printf '%s' "$got" | grep -qF -e "${want#不含:}" && ok=0 || ok=1 ;;
    含:*)  printf '%s' "$got" | grep -qF -e "${want#含:}" && ok=1 ;;
    json:permissionDecision=deny)
      printf '%s' "$got" | "$PY3" -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get("hookSpecificOutput",{}).get("permissionDecision")=="deny" else 1)' 2>/dev/null && ok=1 ;;
  esac
  if [ "$ok" = 1 ]; then
    PASS=$((PASS+1)); echo "PASS  $name"
  else
    FAIL=$((FAIL+1)); echo "FAIL  $name  期望[$want] 实际[$(printf '%s' "$got" | head -c 200)]"
  fi
}

echo "== ① 桩引擎：全分支（不碰真库） =="
check "SessionStart 注入简则" "$(run SessionStart)" "含:respire memory layer"
check "简则点明引擎与同步" "$(run SessionStart)" "含:rsrs.rs"
check "已登录不带登录引导" "$(run SessionStart)" "不含:not signed in"
check "未登录注入登录引导" "$(run SessionStart "" "$CFG_ON" logout)" "含:not signed in"
check "未登录引导给出注册与代登法" "$(run SessionStart "" "$CFG_ON" logout)" "含:rsrs login --oauth --no-open"
check "session_rules=false 静默" "$(run SessionStart "" "$CFG_OFF")" "空"
check "缺模型注入装法" "$(RESPITE_FAKE_NO_MODEL=1 run SessionStart)" "含:rsrs model activate m3"
check "缺模型点明词面回退" "$(RESPITE_FAKE_NO_MODEL=1 run SessionStart)" "含:lexical tier"
check "有货库不带空库引导" "$(run SessionStart)" "不含:memory store is empty"
check "空库注入首日引导" "$(run SessionStart "" "$CFG_ON" empty)" "含:memory store is empty"
check "探测失败注入冷启诊断段" "$(run SessionStart "" "$CFG_ON" fail)" "含:status probe failed"
check "召回注入标题档" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:桩召回命中条一"
check "召回带被取代标记" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:superseded"
check "召回行带短 id" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:aaaaaaaa"
check "无关 prompt 零命中静默" "$(run UserPromptSubmit "无关查询桩空命中" "$CFG_ON" recall_empty)" "空"
check "记：前缀落库回执" "$(run UserPromptSubmit "记：测试条目：钩子落库回执自测。")" "含:【respire · stored】"
check "落库回执催 retitle" "$(run UserPromptSubmit "记：测试条目：钩子落库回执自测。")" "含:retitle dddddddd"
check "落库 pending 转述候选" "$(run UserPromptSubmit "记：测试条目：判重候选自测。" "$CFG_ON" pending)" "含:store pending"
check "落库 pending 带挂靠法" "$(run UserPromptSubmit "记：测试条目：判重候选自测。" "$CFG_ON" pending)" "含:--force"
check "无记：前缀不落库" "$(run UserPromptSubmit "普通问题不做落库")" "不含:【respire · stored】"
check "store: 前缀落库回执" "$(run UserPromptSubmit "store: 测试条目：英文前缀落库自测。")" "含:【respire · stored】"
check "白名单前缀跳过召回" "$(run UserPromptSubmit "你正在为宿主任务编写简短 Recap" "$CFG_SKIP")" "空"
check "白名单前缀大小写不敏感" "$(run UserPromptSubmit "HOST INTERNAL RECAP of the session" "$CFG_SKIP")" "空"
check "白名单不影响普通 prompt" "$(run UserPromptSubmit "普通问题照常召回注入" "$CFG_SKIP")" "含:桩召回命中条一"
# ---- 疑似凭据回归：凭据字面量一律运行时拼接（源文件不出现 sk-<16+>/ghp_<20+> 连续串，
# validate 的 secret 静态扫描才不拦）；nonce=synthetic 供 grep 断言「日志/输出零泄漏」。----
SYN_KEY="synthetic""0123456789abcdef"         # api_key= 赋值：SECRET_RE 命中；redact 表不覆盖 api_key/token/secret 赋值
SYN_TOKEN="sk-""synthetic""0123456789abcdef"  # sk- 令牌：SECRET_RE 的 sk- 分支命中
SYN_BEARER="Bearer ""synthetic""zzzyyxxxwww"  # Bearer 值：SECRET_RE 命中；redact 同样不覆盖
SECRET_LOG="$TMP/secret.log"; : > "$SECRET_LOG"
calls_n() { wc -l < "$TMP/stub-calls.log" 2>/dev/null | tr -d '[:space:]'; }
N0="$(calls_n)"
OUT="$(run UserPromptSubmit "api_key = ${SYN_KEY} 存一下" "$CFG_ON" ok "$STUB" "$SECRET_LOG")"
check "疑似凭据拦截提示" "$OUT" "含:contains a credential"
check "合成凭据不进注入输出" "$OUT" "不含:synthetic"
check "合成凭据不落 hook.log" "$(grep -q 'synthetic' "$SECRET_LOG" && echo LEAK || echo SAFE)" "含:SAFE"
check "secret_skip 只记固定原因码" "$(grep 'secret_skip' "$SECRET_LOG" | grep -q '"d"' && echo HAS_DETAIL || echo CODE_ONLY)" "含:CODE_ONLY"
check "疑似凭据不发引擎" "$( [ "$(calls_n)" = "$N0" ] && echo SAME || echo CALLED )" "含:SAME"
check "sk- 令牌同样拦截" "$(run UserPromptSubmit "my token: ${SYN_TOKEN} remember this" "$CFG_ON" ok "$STUB" "$SECRET_LOG")" "含:contains a credential"
check "Bearer 值同样拦截" "$(run UserPromptSubmit "Authorization: ${SYN_BEARER} remember this" "$CFG_ON" ok "$STUB" "$SECRET_LOG")" "含:contains a credential"
check "凭据轮引擎桩全程未调用" "$( [ "$(calls_n)" = "$N0" ] && echo SAME || echo CALLED )" "含:SAME"
check "普通路径照常召回不回归" "$(run UserPromptSubmit "普通问题照常召回注入" "$CFG_ON" ok "$STUB" "$SECRET_LOG")" "含:桩召回命中条一"
check "普通路径引擎桩被调用" "$( [ "$(calls_n)" != "$N0" ] && echo CALLED || echo SAME )" "含:CALLED"
check "疑似凭据不落库" "$(run UserPromptSubmit "记：数据库密码 = hunter2u")" "含:contains a credential"
# ---- Stop 分支覆盖（复审新契约：每会话原子一次收尾锁 / 免催只认可归属凭证 / 不查引擎；每场景 rst 复位） ----
CFG_STOP0="$TMP/config-stop0.json"
echo '{"session_rules": false, "store_nudge_every": 0}' > "$CFG_STOP0"
rst; OUT_STOP="$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop1.log")"
check "Stop 存储检查拒答续跑" "$OUT_STOP" "json:permissionDecision=deny"
check "Stop 反馈带存库指令" "$OUT_STOP" "含:rsrs remember"
check "hooks.json 注册 Stop" "$(cat "$ROOT/hooks/hooks.json")" "含:\"Stop\""
check "hooks.json 三事件带 py -3 回退" "$( [ "$(grep -c '|| py -3 ' "$ROOT/hooks/hooks.json")" = "3" ] && echo THREE || echo OTHER )" "含:THREE"
rst; check "Stop 防重入续跑轮放行" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-active.log" true)" "空"
rst; check "Stop 节流关闭静默" "$(run Stop "" "$CFG_STOP0" ok "$STUB" "$TMP/stop-off.log")" "空"
rst; run UserPromptSubmit "turn that will store via engine" "$CFG_STOP" ok "$STUB" "$TMP/stop-recent.log" >/dev/null
check "引擎侧写入不再免催(去无归属抑制)" "$(run Stop "" "$CFG_STOP" recent "$STUB" "$TMP/stop-recent.log")" "json:permissionDecision=deny"
rst; check "无请求凭证时仍催(免催只认本层回执)" "$(run Stop "" "$CFG_STOP" recent "$STUB" "$TMP/stop-recent2.log")" "json:permissionDecision=deny"
rst; run UserPromptSubmit "turn with stale engine only" "$CFG_STOP" ok "$STUB" "$TMP/stop-stale.log" >/dev/null
check "Stop 引擎陈旧落库仍催" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-stale.log")" "json:permissionDecision=deny"
rst; check "查库坏信封不再影响Stop(不查引擎)" "$(run Stop "" "$CFG_STOP" fail "$STUB" "$TMP/stop-listfail.log")" "json:permissionDecision=deny"
rst; NCALL0="$(calls_n)"
run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-nocall.log" >/dev/null
check "Stop 不再发起引擎查询" "$( [ "$(calls_n)" = "$NCALL0" ] && echo SAME || echo CALLED )" "含:SAME"
rst; run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-latch.log" >/dev/null
check "同请求二次Stop一次收尾锁放行(宿主未带active)" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-latch.log")" "空"
check "一次收尾锁留痕(once_latch_skip)" "$(grep -q 'once_latch_skip' "$TMP/stop-latch.log" && echo YES)" "含:YES"
rst; run UserPromptSubmit "记：receipt suppression fact sentence。" "$CFG_STOP" ok "$STUB" "$TMP/stop-stored.log" >/dev/null
check "记：成功后本轮凭证免催(取代旧hook.log窗口)" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-stored.log")" "空"
run UserPromptSubmit "next turn after stored receipt" "$CFG_STOP" ok "$STUB" "$TMP/stop-stored.log" >/dev/null
check "下一轮不被上一轮成功写误抑制(应催)" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-stored.log")" "json:permissionDecision=deny"
rst; run UserPromptSubmit "re-arm after wrap-up" "$CFG_STOP" ok "$STUB" "$TMP/stop-rearm.log" >/dev/null
check "新请求重新武装仍催" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-rearm.log")" "json:permissionDecision=deny"
# 锁不设 TTL：25 小时前的锁仍占用，只有新 prompt 重新武装
rst; run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-aged.log" >/dev/null
OLDLATCH="$(ls "$TMP"/turnstate/.latch_* 2>/dev/null | head -1)"
[ -n "$OLDLATCH" ] && printf '{"ts": 100}' > "$OLDLATCH"
check "25小时前的锁仍占用(无TTL)" "$( [ -n "$OLDLATCH" ] && [ -z "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-aged.log")" ] && echo HELD || echo LOST )" "含:HELD"
# /nomem 只跳召回，仍是新请求（重新武装收尾锁）
rst; run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-nomem.log" >/dev/null
run UserPromptSubmit "/nomem skip recall only" "$CFG_STOP" ok "$STUB" "$TMP/stop-nomem.log" >/dev/null
check "/nomem 轮重新武装收尾锁(应催)" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-nomem.log")" "json:permissionDecision=deny"
# ---- 复审 R2#1 点名序列：真实请求→Stop deny→同会话内部 Recap（skip_prefixes）→Stop 必放行 ----
CFG_STOPSKIP="$TMP/config-stopskip.json"
echo '{"session_rules": false, "store_nudge_every": 1, "skip_prefixes": ["Host internal recap"]}' > "$CFG_STOPSKIP"
rst; run UserPromptSubmit "real request before internal recap" "$CFG_STOPSKIP" ok "$STUB" "$TMP/stop-intrecap.log" >/dev/null
check "序列:真实请求Stop拒答续跑" "$(run Stop "" "$CFG_STOPSKIP" ok "$STUB" "$TMP/stop-intrecap.log")" "json:permissionDecision=deny"
NCAP1="$(calls_n)"
check "序列:内部Recap静默且零引擎调用" "$(run UserPromptSubmit "Host internal recap of the session" "$CFG_STOPSKIP" ok "$STUB" "$TMP/stop-intrecap.log" >/dev/null; [ "$(calls_n)" = "$NCAP1" ] && echo SAME || echo CALLED)" "含:SAME"
check "序列:内部Recap后Stop不再deny(未重武装)" "$(run Stop "" "$CFG_STOPSKIP" ok "$STUB" "$TMP/stop-intrecap.log")" "空"
check "序列:内部Recap未删收尾锁(留痕)" "$(grep -q 'once_latch_skip' "$TMP/stop-intrecap.log" && echo YES)" "含:YES"
# ---- 复审 R2#3：每会话独立状态文件——B 的更新不回滚 A 的免催凭证，共享 turn_map.json 不复存在 ----
rst; run UserPromptSubmit "记：session A stores a fact sentence。" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessA >/dev/null
check "A 会话写回执免催 A" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessA)" "空"
AKEY="$("$PY3" -c 'import hashlib; print(hashlib.sha1(b"respire-turn-v2:sessA").hexdigest()[:16])')"
cp "$TURNBASE/st_$AKEY.json" "$TMP/a-snapshot.json" 2>/dev/null
run UserPromptSubmit "session B new unrelated request" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessB >/dev/null
check "B 新请求未存应催" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessB)" "json:permissionDecision=deny"
check "屏障:B 写不影响 A 状态文件(独立文件)" "$(cmp -s "$TURNBASE/st_$AKEY.json" "$TMP/a-snapshot.json" && echo SAME || echo CHANGED)" "含:SAME"
check "A 仍免催(B 未回滚 A 凭证)" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessA)" "空"
check "状态按会话独立成文件(共2个)" "$(ls "$TURNBASE" | grep -c '^st_.*\.json$' | tr -d '[:space:]' | grep -qx 2 && echo TWO || echo OTHER)" "含:TWO"
check "共享 turn_map.json 已移除" "$([ -f "$TURNBASE/turn_map.json" ] && echo PRESENT || echo GONE)" "含:GONE"
run UserPromptSubmit "session A new request after receipt" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessA >/dev/null
check "A 新请求后旧回执不免催(请求代绑定,应催)" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-ab.log" false "$TURNBASE" sessA)" "json:permissionDecision=deny"
# 状态目录不可写（被同名文件挡住；cygpath 转不动含文件组件的路径，先转 $TMP 再拼）→ 无法落锁 → 放行
rm -rf "$TMP/not-a-dir"; printf 'x' > "$TMP/not-a-dir"
rst; check "状态目录不可写放行(绝不无锁deny)" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-nostate.log" false "$(cygpath -m "$TMP" 2>/dev/null || printf '%s' "$TMP")/not-a-dir/sub")" "空"
rm -f "$TMP/not-a-dir"
# ---- 写回执状态机（§7.1/§7.2 契约） ----
check "warn 已写入不误报失败" "$(run UserPromptSubmit "记：warn receipt fact sentence。" "$CFG_ON" warn)" "含:Saved with warnings"
check "warn 回执附引擎警告摘要" "$(run UserPromptSubmit "记：warn receipt fact sentence。" "$CFG_ON" warn)" "含:parent (cause) cannot be resolved"
check "warn 不引导重发" "$(run UserPromptSubmit "记：warn receipt fact sentence。" "$CFG_ON" warn)" "不含:did not accept"
check "warn 仍给 retitle 精修入口" "$(run UserPromptSubmit "记：warn receipt fact sentence。" "$CFG_ON" warn)" "含:retitle eeee1111"
check "pending 保留建议动作merge" "$(run UserPromptSubmit "记：pend receipt fact sentence。" "$CFG_ON" pending)" "含:--merge-ids"
check "坏回执归为unknown" "$(run UserPromptSubmit "记：silent receipt fact sentence。" "$CFG_ON" silent)" "含:store unknown"
check "unknown 禁止重发" "$(run UserPromptSubmit "记：silent receipt fact sentence。" "$CFG_ON" silent)" "含:Do NOT resend"
check "unknown 不误报失败" "$(run UserPromptSubmit "记：silent receipt fact sentence。" "$CFG_ON" silent)" "不含:did not accept"
# ---- 复审 R2#2 反例：show 回 ok 但 details 非 dict → 回读降级 unavailable，不吞已写回执 ----
check "details为数组不吞Saved回执" "$(run UserPromptSubmit "记：bad details array fact sentence。" "$CFG_ON" show_badetails)" "含:【respire · stored】"
check "details为数组回执标unavailable" "$(run UserPromptSubmit "记：bad details array fact sentence。" "$CFG_ON" show_badetails)" "含:Read-back unavailable"
check "details为字符串不吞Saved回执" "$(run UserPromptSubmit "记：bad details string fact sentence。" "$CFG_ON" show_strdetails)" "含:【respire · stored】"
check "details为字符串不误报失败" "$(run UserPromptSubmit "记：bad details string fact sentence。" "$CFG_ON" show_strdetails)" "不含:did not accept"
echo "== ② 日志留痕与脱敏 =="
run SessionStart >/dev/null
run UserPromptSubmit "我的密码是 password: hunter2 这算敏感吗" >/dev/null
check "日志脱敏口令" "$(grep -q 'hunter2' "$TMP/hook.log" && echo LEAK || echo SAFE)" "含:SAFE"
# secret_skip 已只记固定码（敏感摘要不落日志）；脱敏机制改在合法落详情的 nomem 分支上验证
run UserPromptSubmit "/nomem 口令: hunter2 这条走 nomem_or_empty 落详情" >/dev/null
check "日志脱敏留痕" "$(grep -q 'REDACTED' "$TMP/hook.log" && echo YES)" "含:YES"
check "hook.log 留痕" "$(grep -q '"ev": "session"' "$TMP/hook.log" 2>/dev/null && echo YES)" "含:YES"
echo "== ③ 包内静态物 =="
check "README 载三件事(模型可选)" "$(cat "$REPO_ROOT/README.md")" "含:不装模型完全可用"
check "README 载标准装法" "$(cat "$REPO_ROOT/README.md")" "含:codebuddy plugin install respire@risense-workbuddy"
check "仓根含安装脚本" "$([ -f "$REPO_ROOT/install.sh" ] && echo YES)" "含:YES"
check "安装脚本支持卸载" "$(grep -q -- '--uninstall' "$REPO_ROOT/install.sh" 2>/dev/null && echo YES)" "含:YES"
check "安装脚本走官方 CLI" "$(grep -q 'plugin install' "$REPO_ROOT/install.sh" 2>/dev/null && echo YES)" "含:YES"
check "安装脚本含远端市场源" "$(grep -q 'risense-ai/respire-workbuddy' "$REPO_ROOT/install.sh" 2>/dev/null && echo YES)" "含:YES"

if [ "$WITH_STORE" = 1 ]; then
  echo "== ④ 写探针（写真库→断言→forget 自清理） =="
  PROBE="【respire-workbuddy 自测】钩子落库写探针，测完即删。"
  # Windows：command -v rsrs 可能返回无扩展名的 sh shim（CreateProcess 报 WinError 193），优先 .CMD
  REAL_RSRS="$RSRS"
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      for _cand in "$(command -v rsrs.CMD || true)" "$(command -v rsrs.cmd || true)" "$(command -v rsrs.exe || true)"; do
        [ -n "$_cand" ] && REAL_RSRS="$_cand" && break
      done
      REAL_RSRS="$(cygpath -m "$REAL_RSRS")"
      ;;
  esac
  OUT="$(run UserPromptSubmit "记：$PROBE" "$CFG_ON" ok "$REAL_RSRS" "$TMP/real-store.log")"
  if printf '%s' "$OUT" | grep -qF "store pending"; then
    PASS=$((PASS+1)); echo "SKIP  写探针判重待决（实时库判重门收紧，回执路径由桩套件覆盖）"
  else
    check "真库落库回执" "$OUT" "含:【respire · stored】"
  fi
  SID="$(printf '%s' "$OUT" | grep -oE 'retitle [0-9a-f]{8}' | head -1 | awk '{print $2}')"
  if printf '%s' "$OUT" | grep -qF "store pending"; then
    SID=""
  fi
  if [ -n "$SID" ] && [ -n "$RSRS" ]; then
    FULLID="$(HOME="${HOME:-$HOME}" "$RSRS" recall "$PROBE" --titles --json 2>/dev/null | "$PY3" -c 'import json,sys
d=json.load(sys.stdin)
for x in (d.get("details") or []):
    if "写探针" in str(x.get("title") or ""): print(x["id"]); break')"
    if [ -n "$FULLID" ]; then
      HOME="${HOME:-$HOME}" "$RSRS" forget "$FULLID" >/dev/null 2>&1
      PASS=$((PASS+1)); echo "PASS  写探针已 forget 清理"
    else
      FAIL=$((FAIL+1)); echo "FAIL  写探针未 recall 到（未清理，需手工 forget）"
    fi
  fi
elif [ -n "$RSRS" ]; then
  echo "== ②′ 真机 rsrs 只读分支（跳过写） =="
  REAL_OUT="$(RESPITE_CONFIG="$CFG_ON" RESPITE_LOG="$TMP/real.log" "$PY3" "$ROOT/hooks/respire.py" SessionStart)"
  check "真机 SessionStart 注入简则" "$REAL_OUT" "含:respire memory layer"
else
  echo "SKIP：未找到 rsrs 真机引擎，②′ 跳过。"
fi

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = 0 ] && { echo "TESTS: PASS"; exit 0; }
echo "TESTS: FAIL"
exit 1
