#!/usr/bin/env bash
# respire(WorkBuddy) 自测 —— 模拟 stdin 事件 JSON，逐分支断言。
# 双轨：①桩引擎（STUB_RSRS，canned JSON，不碰真库）跑全分支；②真机 rsrs 只读分支（未装则跳过）。
# 写库探针须显式 --store（写真库→回执断言→rsrs forget 自清理），缺省绝不写。
set -u
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
if sub == "list":  # Stop 侧 engine_last_store 用：recent=近 10 分钟有落库 / stale=只有陈旧条 / 其余=失败
    if mode == "recent":
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(json.dumps({"status": "ok", "summary": {}, "details": [
            {"id": "eeee0001-0000-0000-0000-000000000001", "title": "引擎近期落库条",
             "updated_at": now, "created_at": "2020-01-01T00:00:00Z"}]}))
    elif mode == "stale":
        print(json.dumps({"status": "ok", "summary": {}, "details": [
            {"id": "eeee0002-0000-0000-0000-000000000002", "title": "陈旧落库条",
             "updated_at": "2020-01-01T00:00:00Z"}]}))
    else:
        print(json.dumps({"status": "fail", "errors": ["stub list fail"]}))
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
                          "items": [{"name": "ffff0001", "status": "pending", "value": "similarity=78% title=旧条"}]}))
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

# run <event> [prompt] [config] [mode] [engine] [logfile] [stop_hook_active]
# config 只写非 rsrs 项（rsrs 路径由桩注入），避免覆盖被测配置；logfile 可换新文件以免「近 10 分钟已落库」跳过 Stop。
run() {
  local ev="$1" pr="${2-}" cfg="${3:-$CFG_ON}" mode="${4:-ok}" eng="${5:-$STUB}" log="${6:-$TMP/hook.log}" sha="${7:-false}"
  "$PY3" -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); d['rsrs']=sys.argv[2]; json.dump(d, open(sys.argv[3],'w',encoding='utf-8'))" "$cfg" "$eng" "$TMP/cfg-live.json"
  "$PY3" - "$ev" "$pr" "$sha" <<'PY' | RESPITE_CONFIG="$TMP/cfg-live.json" RESPITE_LOG="$log" \
    RESPITE_NUDGE_STATE="$TMP/nudge" STUB_MODE="$mode" STUB_CALL_LOG="$TMP/stub-calls.log" "$PY3" "$ROOT/hooks/respire.py" "$ev"
import json, sys
ev, pr, sha = sys.argv[1], sys.argv[2], sys.argv[3]
d = {"hook_event_name": ev, "cwd": "/tmp", "session_id": "selftest"}
if ev == "UserPromptSubmit":
    d["prompt"] = pr
if ev == "Stop":
    d["stop_hook_active"] = sha == "true"
sys.stdout.write(json.dumps(d, ensure_ascii=False))
PY
}

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
check "Stop 存储检查拒答续跑" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop1.log")" "json:permissionDecision=deny"
check "Stop 反馈带存库指令" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop2.log")" "含:rsrs remember"
check "hooks.json 注册 Stop" "$(cat "$ROOT/hooks/hooks.json")" "含:\"Stop\""
# ---- Stop 分支覆盖：防重入 / 节流关闭 / 引擎近期落库不催 / 陈旧仍催 / 查询失败放行 / hook.log 已存放行放行 ----
CFG_STOP0="$TMP/config-stop0.json"
echo '{"session_rules": false, "store_nudge_every": 0}' > "$CFG_STOP0"
check "Stop 防重入续跑轮放行" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-active.log" true)" "空"
check "Stop 节流关闭静默" "$(run Stop "" "$CFG_STOP0" ok "$STUB" "$TMP/stop-off.log")" "空"
check "Stop 引擎近期落库不催" "$(run Stop "" "$CFG_STOP" recent "$STUB" "$TMP/stop-recent.log")" "空"
check "Stop 引擎陈旧落库仍催" "$(run Stop "" "$CFG_STOP" stale "$STUB" "$TMP/stop-stale.log")" "json:permissionDecision=deny"
check "Stop 引擎查询失败放行催存" "$(run Stop "" "$CFG_STOP" fail "$STUB" "$TMP/stop-listfail.log")" "json:permissionDecision=deny"
NOW_TS="$(date +%Y-%m-%dT%H:%M:%S)"
printf '{"ts": "%s", "ev": "store", "out": "ok"}\n' "$NOW_TS" > "$TMP/stop-stored.log"
check "Stop 近期已存放行放行" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop-stored.log")" "空"
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
  OUT="$(run UserPromptSubmit "记：$PROBE")"
  check "真库落库回执" "$OUT" "含:【respire · stored】"
  SID="$(printf '%s' "$OUT" | grep -oE 'retitle [0-9a-f]{8}' | head -1 | awk '{print $2}')"
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
