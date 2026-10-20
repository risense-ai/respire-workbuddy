#!/usr/bin/env bash
# respire(WorkBuddy) 自测 —— 模拟 stdin 事件 JSON，逐分支断言。
# 双轨：①桩引擎（STUB_RSRS，canned JSON，不碰真库）跑全分支；②真机 rsrs 只读分支（未装则跳过）。
# 写库探针须显式 --store（写真库→回执断言→rsrs forget 自清理），缺省绝不写。
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# ---- 桩引擎：按子命令回 canned JSON，路径写进 config ----
STUB="$TMP/rsrs-stub"
cat > "$STUB" <<'PY'
#!/usr/bin/env python3
import json, os, sys
sub = sys.argv[1] if len(sys.argv) > 1 else ""
mode = os.environ.get("STUB_MODE", "ok")
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

# run <event> [prompt] [config] [mode] [engine] [logfile]
# config 只写非 rsrs 项（rsrs 路径由桩注入），避免覆盖被测配置；logfile 可换新文件以免「近 10 分钟已落库」跳过 Stop。
run() {
  local ev="$1" pr="${2-}" cfg="${3:-$CFG_ON}" mode="${4:-ok}" eng="${5:-$STUB}" log="${6:-$TMP/hook.log}"
  "$PY3" -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); d['rsrs']=sys.argv[2]; json.dump(d, open(sys.argv[3],'w',encoding='utf-8'))" "$cfg" "$eng" "$TMP/cfg-live.json"
  "$PY3" - "$ev" "$pr" <<'PY' | RESPITE_CONFIG="$TMP/cfg-live.json" RESPITE_LOG="$log" \
    RESPITE_NUDGE_STATE="$TMP/nudge" STUB_MODE="$mode" "$PY3" "$ROOT/hooks/respire.py" "$ev"
import json, sys
ev, pr = sys.argv[1], sys.argv[2]
d = {"hook_event_name": ev, "cwd": "/tmp", "session_id": "selftest"}
if ev == "UserPromptSubmit":
    d["prompt"] = pr
if ev == "Stop":
    d["stop_hook_active"] = False
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
check "SessionStart 注入简则" "$(run SessionStart)" "含:respire 记忆层"
check "简则点明引擎与同步" "$(run SessionStart)" "含:rsrs.rs"
check "已登录不带登录引导" "$(run SessionStart)" "不含:尚未登录"
check "未登录注入登录引导" "$(run SessionStart "" "$CFG_ON" logout)" "含:尚未登录"
check "未登录引导给出注册与代登法" "$(run SessionStart "" "$CFG_ON" logout)" "含:rsrs login --oauth --no-open"
check "session_rules=false 静默" "$(run SessionStart "" "$CFG_OFF")" "空"
check "缺模型注入装法" "$(RESPITE_FAKE_NO_MODEL=1 run SessionStart)" "含:rsrs model activate m3"
check "缺模型点明词面回退" "$(RESPITE_FAKE_NO_MODEL=1 run SessionStart)" "含:词面档"
check "有货库不带空库引导" "$(run SessionStart)" "不含:记忆库还是空的"
check "空库注入首日引导" "$(run SessionStart "" "$CFG_ON" empty)" "含:记忆库还是空的"
check "探测失败注入冷启诊断段" "$(run SessionStart "" "$CFG_ON" fail)" "含:状态探测失败"
check "召回注入标题档" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:桩召回命中条一"
check "召回带被取代标记" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:已被取代"
check "召回行带短 id" "$(run UserPromptSubmit "上次的钩子注入怎么配的")" "含:aaaaaaaa"
check "无关 prompt 零命中静默" "$(run UserPromptSubmit "无关查询桩空命中" "$CFG_ON" recall_empty)" "空"
check "记：前缀落库回执" "$(run UserPromptSubmit "记：测试条目：钩子落库回执自测。")" "含:【respire·落库】"
check "落库回执催 retitle" "$(run UserPromptSubmit "记：测试条目：钩子落库回执自测。")" "含:retitle dddddddd"
check "落库 pending 转述候选" "$(run UserPromptSubmit "记：测试条目：判重候选自测。" "$CFG_ON" pending)" "含:落库待决"
check "落库 pending 带挂靠法" "$(run UserPromptSubmit "记：测试条目：判重候选自测。" "$CFG_ON" pending)" "含:--force"
check "无记：前缀不落库" "$(run UserPromptSubmit "普通问题不做落库")" "不含:【respire·落库】"
check "Stop 存储检查拒答续跑" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop1.log")" "json:permissionDecision=deny"
check "Stop 反馈带存库指令" "$(run Stop "" "$CFG_STOP" ok "$STUB" "$TMP/stop2.log")" "含:rsrs remember"
echo "== ② 日志留痕与脱敏 =="
run SessionStart >/dev/null
run UserPromptSubmit "我的密码是 password: hunter2 这算敏感吗" >/dev/null
check "日志脱敏口令" "$(grep -q 'hunter2' "$TMP/hook.log" && echo LEAK || echo SAFE)" "含:SAFE"
check "日志脱敏留痕" "$(grep -q 'REDACTED' "$TMP/hook.log" && echo YES)" "含:YES"
check "hook.log 留痕" "$(grep -q '"ev": "session"' "$TMP/hook.log" 2>/dev/null && echo YES)" "含:YES"
echo "== ③ 包内静态物 =="
check "README 载三件事(模型可选)" "$(cat "$ROOT/README.md")" "含:不装模型完全可用"
check "README 载标准装法" "$(cat "$ROOT/README.md")" "含:codebuddy plugin install respire@risense"
check "包内无自定义安装脚本" "$(ls "$ROOT"/install.sh "$ROOT"/uninstall.sh 2>&1)" "含:No such file"

if [ "$WITH_STORE" = 1 ]; then
  echo "== ④ 写探针（写真库→断言→forget 自清理） =="
  PROBE="【respire-workbuddy 自测】钩子落库写探针，测完即删。"
  OUT="$(run UserPromptSubmit "记：$PROBE")"
  check "真库落库回执" "$OUT" "含:【respire·落库】"
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
  check "真机 SessionStart 注入简则" "$REAL_OUT" "含:respire 记忆层"
else
  echo "SKIP：未找到 rsrs 真机引擎，②′ 跳过。"
fi

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = 0 ] && { echo "TESTS: PASS"; exit 0; }
echo "TESTS: FAIL"
exit 1
