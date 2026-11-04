#!/usr/bin/env python3
"""respire 连接器 · 提交前自检

按 connector-meta.json 的 type 分两条路查（官方口径：一个连接器只能选一种方案）：
    type=mcp → 包里必须是 mcp.json，探活走 MCP 握手（initialize + tools/list）
    type=cli → 包里必须是 cli.json，探活走 status 命令 + statusMatch 正则

四层，任一层不过就是审核会被打回的地方：
    1. 包结构     —— meta / 配置 / icon / skills 齐，技能名与目录名一致
    2. 市场条目   —— connector-meta.json 必填字段（中英名/描述/示例/source）
    3. 接入契约   —— 配置合法 + 真机探活命中
    4. 打包       —— zip 顶层必须是 connector-meta.json（不能多一层目录）

用法：
    python3 connector/validate_connector.py            # 全检（会真跑探活）
    python3 connector/validate_connector.py --offline  # 不跑外部命令，只查静态
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

SRC = os.path.dirname(os.path.abspath(__file__))
PLATFORMS = ("darwin", "linux", "win32")
TIMEOUT = 90
ok_n = 0
fail: list[str] = []


def ok(msg: str) -> None:
    global ok_n
    ok_n += 1
    print(f"  ✓ {msg}")


def bad(msg: str) -> None:
    fail.append(msg)
    print(f"  ✗ {msg}")


def load(name: str):
    p = os.path.join(SRC, name)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        bad(f"{name} 不是合法 JSON：{e}")
        return None


def check_layout(ctype: str) -> None:
    print("[1/4] 包结构")
    need = ["connector-meta.json", "icon.svg", "mcp.json" if ctype == "mcp" else "cli.json"]
    for rel in need:
        if os.path.isfile(os.path.join(SRC, rel)):
            ok(rel)
        else:
            bad(f"缺 {rel}（type={ctype}）")
    extra = "cli.json" if ctype == "mcp" else "mcp.json"
    if os.path.isfile(os.path.join(SRC, extra)):
        bad(f"type={ctype} 却同时带了 {extra}——官方要求一个连接器只选一种方案")

    skills_dir = os.path.join(SRC, "skills")
    if not os.path.isdir(skills_dir):
        if ctype == "mcp":
            ok("无 skills/（MCP 方案 Skill 可选）")
            return
        bad("缺 skills/ 目录（CLI 方案强烈推荐 Skill）")
        return
    names = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))]
    if not names:
        bad("skills/ 下没有技能目录")
        return
    for d in names:
        md = os.path.join(skills_dir, d, "SKILL.md")
        if not os.path.isfile(md):
            bad(f"skills/{d} 缺 SKILL.md")
            continue
        head = open(md, encoding="utf-8").read(800)
        m = re.search(r"^---\s*\n(.*?)\n---", head, re.S)
        if not m:
            bad(f"skills/{d}/SKILL.md 缺 frontmatter")
            continue
        fm = m.group(1)
        nm = re.search(r"^name:\s*(\S+)", fm, re.M)
        desc = re.search(r"^description:\s*(.+)", fm, re.M)
        if not nm:
            bad(f"skills/{d} frontmatter 缺 name")
        elif nm.group(1) != d:
            bad(f"skills/{d} 目录名与 frontmatter.name({nm.group(1)}) 不一致")
        else:
            ok(f"技能 {d}（name 与目录一致）")
        if not desc or len(desc.group(1).strip()) < 20:
            bad(f"skills/{d} 的 description 太短，模型选不中它")
        else:
            ok(f"技能 {d} description {len(desc.group(1))} 字")


def check_meta(meta) -> str:
    print("[2/4] 市场条目 connector-meta.json")
    if not meta:
        return "cli"
    required = ("name", "name_en", "description", "description_zh", "description_en",
                "source", "version", "examples_zh", "examples_en")
    for k in required:
        if not meta.get(k):
            bad(f"缺字段 {k}")
        else:
            ok(k)
    src = str(meta.get("source", ""))
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", src):
        bad(f"source={src!r} 不是 kebab-case（小写字母/数字/连字符）")
    else:
        ok(f"source={src} kebab-case")
    if len(meta.get("name", "")) > 20:
        bad("name 超过 20 字符")
    for k in ("description_zh", "description_en"):
        n = len(str(meta.get(k, "")))
        if not (20 <= n <= 120):
            bad(f"{k} 长度 {n}，官方建议 20–100 字")
        else:
            ok(f"{k} {n} 字")
    for k in ("examples_zh", "examples_en"):
        v = meta.get(k) or []
        if not (2 <= len(v) <= 5):
            bad(f"{k} 条数 {len(v)}，官方口径 2–5 条")
        else:
            ok(f"{k} {len(v)} 条")

    ctype = meta.get("type") or "mcp"
    if ctype not in ("cli", "mcp"):
        bad(f"type={ctype!r} 不是 cli/mcp")
        ctype = "mcp"
    else:
        ok(f"type={ctype}")
    am = meta.get("auth_mode")
    if am not in (None, "", "server-side", "token"):
        bad(f"auth_mode={am!r} 只允许省略 / server-side / token")
    elif am:
        ok(f"auth_mode={am}")
        if am == "server-side" and not meta.get("server_auth"):
            bad("auth_mode=server-side 必须同时给 server_auth")
        if am == "token":
            if str(meta.get("minWorkbuddyVersion", "0")) < "4.23.0":
                bad("auth_mode=token 要求 minWorkbuddyVersion ≥ 4.23.0")
            if not os.path.isfile(os.path.join(SRC, "token-schema.json")):
                bad("auth_mode=token 缺 token-schema.json")
    else:
        ok("auth_mode 省略（无需认证）")
    return ctype


def probe_mcp(cfg, offline: bool) -> None:
    print("[3/4] 接入契约 mcp.json")
    if not cfg:
        return
    servers = cfg.get("mcpServers") or {}
    if len(servers) != 1:
        bad(f"mcpServers 有 {len(servers)} 个，官方只读第一个——一个连接器对应一个 Server")
        return
    name, s = next(iter(servers.items()))
    ok(f"唯一 Server：{name}")
    stype = s.get("type") or ("stdio" if s.get("command") else None)
    if stype not in ("stdio", "sse", "streamableHttp"):
        bad(f"type={stype!r} 只允许 stdio / sse / streamableHttp")
        return
    ok(f"传输类型 {stype}")
    if stype == "stdio":
        if not s.get("command"):
            bad("stdio 缺 command")
            return
        ok(f"command = {s['command']} {' '.join(s.get('args') or [])[:60]}")
        if not isinstance(s.get("args", []), list):
            bad("args 必须是数组")
        rt = s.get("runtime")
        if rt:
            if rt.get("type") != "node":
                bad(f"runtime.type={rt.get('type')!r} 只允许 node")
            else:
                ok(f"runtime node {rt.get('version', '')}".strip())
    else:
        url = str(s.get("url", ""))
        if not url.startswith("https://"):
            bad(f"url 必须是 HTTPS：{url}")
        else:
            ok(f"url {url[:50]}")
    if cfg.get("preAuth") not in (None, "", "cli"):
        bad(f"preAuth={cfg.get('preAuth')!r} 只支持 cli")
    if offline:
        print("  - 离线模式：跳过 MCP 握手")
        return

    cmd = s.get("command")
    exe = cmd.split()[0] if cmd else ""
    if exe and not shutil.which(exe):
        bad(f"本机找不到 {exe}，无法探活（用户侧同样会连不上）")
        return
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "validate-connector", "version": "0"}}}
    ready = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    listq = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    payload = "\n".join(json.dumps(x) for x in (init, ready, listq)) + "\n"
    try:
        p = subprocess.run([cmd] + (s.get("args") or []), input=payload, capture_output=True,
                           text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        bad(f"MCP 握手 {TIMEOUT}s 超时：{cmd}")
        return
    server_info, tools = None, []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") == 1:
            server_info = (d.get("result") or {}).get("serverInfo") or {}
        elif d.get("id") == 2:
            tools = (d.get("result") or {}).get("tools") or []
    if not server_info:
        bad(f"initialize 无响应（stderr 尾：{p.stderr.strip()[-160:]}）")
        return
    ok(f"握手成功：serverInfo={server_info.get('name')} v{server_info.get('version')}")
    if not tools:
        bad("tools/list 返回 0 个工具——AI 拿不到任何能力")
        return
    ok(f"tools/list {len(tools)} 个工具")
    skill = os.path.join(SRC, "skills")
    if os.path.isdir(skill):
        body = ""
        for root, _d, files in os.walk(skill):
            for f in files:
                if f == "SKILL.md":
                    body += open(os.path.join(root, f), encoding="utf-8").read()
        hit = sum(1 for t in tools if t.get("name", "") in body)
        if hit < len(tools) / 2:
            bad(f"Skill 只覆盖 {hit}/{len(tools)} 个工具，模型不知道怎么用剩下的")
        else:
            ok(f"Skill 覆盖 {hit}/{len(tools)} 个工具")


def probe_cli(cli, offline: bool) -> None:
    print("[3/4] 接入契约 cli.json")
    if not cli:
        return
    for cmd in ("init", "auth", "unAuth", "status"):
        block = cli.get(cmd) or {}
        miss = [p for p in PLATFORMS if not block.get(p)]
        if miss:
            bad(f"{cmd} 缺平台 {miss}")
        else:
            ok(f"{cmd} 三平台齐")
    sm = cli.get("statusMatch")
    try:
        re.compile(sm or "")
        ok(f"statusMatch 是合法正则：{sm!r}")
    except re.error as e:
        bad(f"statusMatch 不是合法正则：{e}")
        return
    plat = "win32" if sys.platform.startswith("win") else ("darwin" if sys.platform == "darwin" else "linux")
    if offline:
        print("  - 离线模式：跳过真实探活")
        return
    status_cmd = (cli.get("status") or {}).get(plat)
    if not status_cmd:
        bad(f"status 无 {plat} 命令")
        return
    if not shutil.which(status_cmd.split()[0]):
        bad(f"{plat} 上找不到命令 {status_cmd.split()[0]}")
        return
    try:
        out = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT).stdout
    except subprocess.TimeoutExpired:
        bad(f"status 命令 {TIMEOUT}s 无响应")
        return
    if re.search(sm, out):
        ok(f"探活命中：`{status_cmd}` 匹配 {sm!r} → 已连接")
    else:
        bad(f"探活未命中：`{status_cmd}` 输出里没有 {sm!r}")
    vc = cli.get("versionCheck") or {}
    if vc.get("command"):
        vcmd = vc["command"].get(plat)
        try:
            vout = subprocess.run(vcmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT).stdout
        except subprocess.TimeoutExpired:
            bad(f"versionCheck 超时：{vcmd}")
            return
        m = re.search(vc.get("versionPattern", r"(\d+\.\d+\.\d+)"), vout)
        got = m.group(1) if m else None
        want = vc.get("minVersion", "0.0.0")
        if not got:
            bad(f"versionCheck 抓不到版本号：{vout.strip()!r}")
        elif tuple(map(int, got.split("."))) >= tuple(map(int, want.split("."))):
            ok(f"版本 {got} ≥ minVersion {want}")
        else:
            bad(f"版本 {got} < minVersion {want}")


def check_zip(ctype: str) -> None:
    print("[4/4] 打包口径")
    files = ["connector-meta.json", "icon.svg", "mcp.json" if ctype == "mcp" else "cli.json"]
    tmp = "/tmp/respire-connector-selfcheck.zip"
    if os.path.isfile(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(SRC, rel), rel)
        base = os.path.join(SRC, "skills")
        if os.path.isdir(base):
            for root, _d, fs in os.walk(base):
                for f in fs:
                    full = os.path.join(root, f)
                    z.write(full, os.path.relpath(full, SRC))
    with zipfile.ZipFile(tmp) as z:
        roots = sorted({n.split("/")[0] for n in z.namelist()})
    if "connector-meta.json" in roots:
        ok(f"zip 顶层正确：{roots}")
    else:
        bad(f"zip 顶层不对（多包了一层？）：{roots}")
    print(f"  · 试打：{tmp}（{os.path.getsize(tmp)} B）")


def main() -> int:
    offline = "--offline" in sys.argv
    print(f"自检目录：{SRC}\n")
    meta = load("connector-meta.json")
    ctype = check_meta(meta)
    check_layout(ctype)
    if ctype == "mcp":
        probe_mcp(load("mcp.json"), offline)
    else:
        probe_cli(load("cli.json"), offline)
    check_zip(ctype)
    print()
    if fail:
        print(f"RESULT: FAIL（{len(fail)} 项不过，{ok_n} 项通过）")
        for f in fail:
            print(f"  - {f}")
        return 1
    print(f"RESULT: PASS（{ok_n} 项通过）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
