#!/usr/bin/env python3
"""respire 连接器 · 提交前自检

查四层，任一层不过就是审核会被打回的地方：
    1. 包结构     —— connector-meta.json / cli.json / icon / skills 齐，且技能名与目录名一致
    2. 市场条目   —— connector-meta.json 必填字段（官方要求：中英名/描述/示例/type）
    3. 命令契约   —— cli.json 三平台齐、statusMatch 是合法正则且能命中真实输出、versionCheck 版本够
    4. 打包       —— 打成 zip 后顶层必须是 connector-meta.json（不能多一层目录）

用法：
    python3 connector/validate_connector.py            # 全检（会真跑 status 探活）
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
        bad(f"缺文件 {name}")
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        bad(f"{name} 不是合法 JSON：{e}")
        return None


def check_layout() -> None:
    print("[1/4] 包结构")
    for rel in ("connector-meta.json", "cli.json", "icon.svg"):
        if os.path.isfile(os.path.join(SRC, rel)):
            ok(rel)
        else:
            bad(f"缺 {rel}")

    skills_dir = os.path.join(SRC, "skills")
    if not os.path.isdir(skills_dir):
        bad("缺 skills/ 目录")
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


def check_meta(meta) -> None:
    print("[2/4] 市场条目 connector-meta.json")
    if not meta:
        return
    required = ("name", "name_en", "description", "description_zh", "description_en",
                "source", "type", "version", "examples_zh", "examples_en")
    for k in required:
        if not meta.get(k):
            bad(f"缺字段 {k}")
        else:
            ok(k)
    if meta.get("type") not in ("cli", "mcp"):
        bad(f"type={meta.get('type')} 不是 cli/mcp")
    else:
        ok(f"type={meta['type']}")
    for k in ("examples_zh", "examples_en"):
        v = meta.get(k) or []
        if not (2 <= len(v) <= 5):
            bad(f"{k} 条数 {len(v)}，官方口径 2–5 条")
        elif any(len(str(x)) < 4 for x in v):
            bad(f"{k} 有过短示例")
        else:
            ok(f"{k} {len(v)} 条")


def check_cli(cli, offline: bool) -> None:
    print("[3/4] 命令契约 cli.json")
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
        bad(f"status 无 {plat} 命令，无法探活")
        return
    exe = status_cmd.split()[0]
    if not shutil.which(exe):
        bad(f"{plat} 上找不到命令 {exe} —— 用户装了也用不了，init 会先跑，但 status 会一直失败")
        return
    try:
        out = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=60).stdout
    except subprocess.TimeoutExpired:
        bad(f"status 命令 60 秒无响应：{status_cmd}")
        return
    if re.search(sm, out):
        ok(f"探活命中：`{status_cmd}` 匹配 {sm!r} → 已连接")
    else:
        bad(f"探活未命中：`{status_cmd}` 输出里没有 {sm!r}（用户会觉得「连上了但显示未连接」）")

    vc = cli.get("versionCheck") or {}
    if vc.get("command"):
        vcmd = vc["command"].get(plat)
        if not vcmd:
            bad(f"versionCheck 缺 {plat}")
            return
        try:
            vout = subprocess.run(vcmd, shell=True, capture_output=True, text=True, timeout=60).stdout
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
            bad(f"版本 {got} < minVersion {want}，用户会被判定 needsUpgrade 直接跳过")


def check_zip() -> None:
    print("[4/4] 打包口径")
    out = os.path.join(os.path.dirname(SRC), "respire-connector-" + "1.0.0" + ".zip")
    tmp = os.path.join("/tmp", "respire-connector-selfcheck.zip")
    if os.path.isfile(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in ("connector-meta.json", "cli.json", "icon.svg"):
            z.write(os.path.join(SRC, rel), rel)
        base = os.path.join(SRC, "skills")
        for root, _dirs, files in os.walk(base):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, SRC))
    with zipfile.ZipFile(tmp) as z:
        roots = sorted({n.split("/")[0] for n in z.namelist()})
    if "connector-meta.json" in roots and len(roots) <= 4:
        ok(f"zip 顶层正确：{roots}")
    else:
        bad(f"zip 顶层不对（多包了一层？）：{roots}")
    print(f"  · 试打：{tmp}（{os.path.getsize(tmp)} B）")
    if out and os.path.isfile(out):
        print(f"  · 仓内已有：{os.path.basename(out)}")


def main() -> int:
    offline = "--offline" in sys.argv
    print(f"自检目录：{SRC}\n")
    meta = load("connector-meta.json")
    cli = load("cli.json")
    check_layout()
    check_meta(meta)
    check_cli(cli, offline)
    check_zip()
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
