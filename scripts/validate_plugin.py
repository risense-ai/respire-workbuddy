#!/usr/bin/env python3
"""respire 插件自检 —— 结构与规范校验（对齐 WorkBuddy 插件包要求），零第三方依赖。

用法: python3 scripts/validate_plugin.py   （退出码 0=通过；任一 FAIL=1）
"""
import json
import os
import py_compile
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
failed = False


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def fail(msg: str) -> None:
    global failed
    failed = True
    print(f"FAIL: {msg}", file=sys.stderr)


def read_text(rel: str) -> str:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        fail(f"missing {rel}")
        return ""
    with open(p, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        fail(f"empty {rel}")
    else:
        ok(rel)
    return text


def parse_json(rel: str):
    text = read_text(rel)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception as e:
        fail(f"invalid JSON {rel}: {e}")
        return None


REQUIRED = [
    ".codebuddy-plugin/plugin.json",
    ".codebuddy-plugin/marketplace.json",
    "hooks/hooks.json",
    "hooks/respire.py",
    "hooks/respire.config.example.json",
    "skills/respire/SKILL.md",
    "tests/test_hooks.sh",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
]
for rel in REQUIRED:
    read_text(rel)

# ---- 插件清单 ----
manifest = parse_json(".codebuddy-plugin/plugin.json")
if manifest:
    if manifest.get("name") != "respire":
        fail("manifest name must be respire")
    else:
        ok("manifest name")
    ver = str(manifest.get("version") or "")
    if not re.match(r"^\d+\.\d+\.\d+$", ver):
        fail(f"manifest version must be plain SemVer: {ver!r}")
    else:
        ok(f"manifest version {ver}")
    if manifest.get("hooks") != "./hooks/hooks.json":
        fail('manifest hooks must be "./hooks/hooks.json"')
    else:
        ok("manifest hooks pointer")
    if manifest.get("skills") != "./skills":
        fail('manifest skills must be "./skills"')
    else:
        ok("manifest skills pointer")

# ---- 市场清单：本仓自为市场，source 指向仓根 ----
mp = parse_json(".codebuddy-plugin/marketplace.json")
if mp:
    plugs = mp.get("plugins") or []
    respire = next((p for p in plugs if p.get("name") == "respire"), None)
    if not respire:
        fail("marketplace must list plugin respire")
    else:
        src = str(respire.get("source") or "")
        if "respite" in src or src.startswith(".."):
            fail(f"marketplace source must stay inside repo: {src!r}")
        else:
            ok(f"marketplace source {src!r}")

# ---- hooks 规范：事件合法、command 走 ${CODEBUDDY_PLUGIN_ROOT}、含回退链、timeout 正 ----
hooks_cfg = parse_json("hooks/hooks.json")
if hooks_cfg:
    events = hooks_cfg.get("hooks") or {}
    allowed = {"SessionStart", "UserPromptSubmit", "Stop"}
    if set(events) - allowed:
        fail(f"unexpected events: {sorted(set(events) - allowed)}")
    else:
        ok("hook events subset")
    for ev in allowed:
        if ev not in events:
            fail(f"missing required event {ev}")
    for ev, groups in events.items():
        if not isinstance(groups, list) or not groups:
            fail(f"hooks.{ev} must be a non-empty array")
            continue
        for g in groups:
            for h in (g.get("hooks") or []):
                if h.get("type") != "command":
                    fail(f"{ev}: handler type must be command")
                cmd = h.get("command") or ""
                if "${CODEBUDDY_PLUGIN_ROOT}" not in cmd:
                    fail(f"{ev}: command must use ${{CODEBUDDY_PLUGIN_ROOT}}")
                if "python3 " not in cmd or " || python " not in cmd:
                    fail(f"{ev}: command should carry python3||python fallback chain")
                if not h.get("statusMessage"):
                    fail(f"{ev}: statusMessage missing")
                t = h.get("timeout")
                if not isinstance(t, (int, float)) or t <= 0:
                    fail(f"{ev}: timeout must be positive")
    ok("hooks.json shape")

# ---- 主脚本可编译 + fail-open 恒 exit 0 ----
try:
    py_compile.compile(os.path.join(ROOT, "hooks/respire.py"), doraise=True)
    ok("respire.py compiles")
except Exception as e:
    fail(f"respire.py compile: {e}")
src = read_text("hooks/respire.py")
if src and "sys.exit(0)" not in src:
    fail("respire.py must keep fail-open exit 0")
elif src:
    ok("fail-open exit present")

# ---- SKILL.md 前栏须 name=respire 且带 description ----
skill = read_text("skills/respire/SKILL.md")
if skill:
    fm = skill.split("---", 2)
    if len(fm) < 3 or not re.search(r"^name:\s*respire\s*$", fm[1], re.M):
        fail("SKILL.md frontmatter name must be respire")
    elif not re.search(r"^description:\s*\S", fm[1], re.M):
        fail("SKILL.md frontmatter description missing")
    else:
        ok("SKILL.md frontmatter")

# ---- 敏感模式扫描（分发前自检） ----
SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY")
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "node_modules"}]
    for fn in filenames:
        if fn.endswith((".pyc", ".webp", ".png", ".jpg")):
            continue
        p = os.path.join(dirpath, fn)
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                if SECRET.search(f.read()):
                    fail(f"secret-like pattern in {os.path.relpath(p, ROOT)}")
        except Exception:
            pass
ok("secret scan done")

print("----")
if failed:
    print("VALIDATE: FAIL")
    sys.exit(1)
print("VALIDATE: PASS")
sys.exit(0)
