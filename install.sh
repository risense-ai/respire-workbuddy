#!/usr/bin/env bash
# respire × WorkBuddy 插件安装/卸载脚本
# 用法: bash install.sh              安装（幂等：已装则提示升级）
#       bash install.sh --uninstall  卸载插件（保留市场注册，便于重装）
# 原理: 调 WorkBuddy 桌面端自带的 codebuddy CLI 走官方装载链路
#       （marketplace add → plugin install），不手改 ~/.workbuddy 注册表。
# 生效: 装完须完全退出并重启 WorkBuddy，新会话起钩子生效。
set -u

MARKET_NAME="risense-workbuddy"
PLUGIN_ID="respire@risense-workbuddy"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOW="$(date -Iseconds 2>/dev/null || date)"

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "→ $*"; }

# ---- 1. 找 codebuddy CLI：显式环境变量 → PATH → Linux 桌面端捆绑位 ----
find_cli() {
  if [ -n "${CODEBUDDY_BIN:-}" ] && [ -x "${CODEBUDDY_BIN:-}" ]; then
    echo "$CODEBUDDY_BIN"; return 0
  fi
  local p
  p="$(command -v codebuddy 2>/dev/null)" && [ -x "$p" ] && { echo "$p"; return 0; }
  for p in \
    /var/opt/apps/workbuddy/resources/app.asar.unpacked/cli/bin/codebuddy \
    /opt/apps/workbuddy/resources/app.asar.unpacked/cli/bin/codebuddy; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}

CB="$(find_cli)" || die "未找到 codebuddy CLI。请确认已装 WorkBuddy 桌面端；非常规安装路径可设 CODEBUDDY_BIN=/path/to/codebuddy 后重跑。"
say "codebuddy CLI: $CB"

# ---- 2. WorkBuddy 运行中提示（安装会写 ~/.workbuddy，运行中可能被内存态覆盖） ----
if pgrep -i workbuddy >/dev/null 2>&1; then
  say "检测到 WorkBuddy 正在运行。本次安装仍会执行；若重启后未生效，退出 WorkBuddy 再跑一次本脚本。"
fi

# ---- 3. 已装检测（读 installed_plugins.json，不猜 CLI 输出格式） ----
is_installed() {
  python3 - "$PLUGIN_ID" <<'PY' 2>/dev/null
import json, os, sys
p = os.path.expanduser("~/.workbuddy/plugins/installed_plugins.json")
try:
    d = json.load(open(p, encoding="utf-8"))
except Exception:
    sys.exit(1)
sys.exit(0 if (d.get("plugins") or {}).get(sys.argv[1]) else 1)
PY
}

if [ "${1:-}" = "--uninstall" ]; then
  is_installed || { say "未安装 $PLUGIN_ID，无需卸载。"; exit 0; }
  "$CB" plugin uninstall "$PLUGIN_ID" || die "卸载失败（CLI 报错见上）。"
  say "已卸载 $PLUGIN_ID。市场 $MARKET_NAME 注册保留（重装直接重跑本脚本）；要一并移除：codebuddy plugin marketplace remove $MARKET_NAME"
  say "重启 WorkBuddy 后生效。"
  exit 0
fi

# ---- 4. 安装：市场注册（已注册则刷新）→ 装插件（已装则升级） ----
if "$CB" plugin marketplace add "$REPO_ROOT" --name "$MARKET_NAME" >/dev/null 2>&1; then
  say "市场 $MARKET_NAME 已注册（源：$REPO_ROOT）"
else
  say "市场已存在，刷新之"
  "$CB" plugin marketplace update "$MARKET_NAME" >/dev/null 2>&1 \
    || say "刷新失败（通常无碍，继续装插件）"
fi

if is_installed; then
  say "已安装，升级到仓内版本"
  "$CB" plugin update "$PLUGIN_ID" || die "升级失败。可先 bash install.sh --uninstall 再重装。"
else
  "$CB" plugin install "$PLUGIN_ID" || die "安装失败（CLI 报错见上）。"
fi

# ---- 5. 验证落地：注册表 + 缓存目录 ----
is_installed || die "安装后注册表未见 $PLUGIN_ID——若 WorkBuddy 在运行，退出重启后重跑本脚本验证。"
CACHE_DIR="$(python3 - "$PLUGIN_ID" <<'PY' 2>/dev/null
import json, os, sys
d = json.load(open(os.path.expanduser("~/.workbuddy/plugins/installed_plugins.json"), encoding="utf-8"))
for e in (d.get("plugins") or {}).get(sys.argv[1]) or []:
    print(e.get("installPath", "")); break
PY
)"
[ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ] || die "注册表有记录但缓存目录缺失：$CACHE_DIR"
[ -f "$CACHE_DIR/hooks/respire.py" ] || die "缓存目录缺钩子文件：$CACHE_DIR/hooks/respire.py"

echo "✓ 安装完成（$NOW）"
echo "  插件: $PLUGIN_ID → $CACHE_DIR"
echo "  生效: 完全退出并重启 WorkBuddy，新会话起自动召回/落库即挂上"
echo "  自检: 新会话里问一句记忆相关的话，或看 $CACHE_DIR/hooks/hook.log 有无留痕"
