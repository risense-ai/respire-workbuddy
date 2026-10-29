#!/usr/bin/env python3
"""respire 连接器 · 本机安装/卸载（WorkBuddy 桌面端未上架时的本地装载）

为什么需要这个脚本：WorkBuddy 桌面端不加载「插件自带的 hooks」，连接器也只认
下面这五处落盘状态；`codebuddy plugin` CLI 在桌面端运行期间会卡死（epoll 等 IPC），
所以只能直接写注册表。

用法：
    python3 connector/install_local.py             # 安装/更新（幂等）
    python3 connector/install_local.py --uninstall # 卸载（保留市场注册）

落盘位置（都以 ~/.workbuddy 为根）：
    1. plugins/known_marketplaces.json                    注册 directory 型市场
    2. plugins/cache/<市场>/<插件>/<版本>/                 插件本体 + .codebuddy-directory-source.json
    3. plugins/installed_plugins.json                     安装条目 <插件>@<市场>
    4. settings.json  enabledPlugins                      启用
    5. connectors-marketplace/connectors/<插件>/          连接器市场卡片所需包目录（cli.json + skills/）
       connectors-marketplace/.codebuddy-connector/connectors.json   市场索引条目
       connectors-marketplace/icons/<插件>.svg                      卡片图标
    6. connectors/<uid>/connector-states.json             启用态 {bound:true, enabled:true}
       （v4 为准，connector-states.v3.json 只是降级镜像，一并同步）

改完必须完全退出并重开 WorkBuddy，钩子/连接器都在启动时装载。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

SRC = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(SRC, "connector-meta.json"), encoding="utf-8"))
NAME = "respire-connector"          # 本地插件名：不能叫 respire，会与记忆插件撞名
MARKET = "risense-respire-connector"
VER = META.get("version", "1.0.0")
PID = f"{NAME}@{MARKET}"
SKILL_DIR = "respire-memory"        # 与 SKILL.md 的 frontmatter name 一致

WB = os.path.join(os.path.expanduser("~"), ".workbuddy")


def say(msg: str) -> None:
    print(f"[respire-connector] {msg}")


def die(msg: str) -> None:
    print(f"[respire-connector] 失败：{msg}", file=sys.stderr)
    sys.exit(1)


def read_json(path: str, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def find_state_dir() -> str | None:
    """connectors/<uid>/ 里放着状态与密钥。"""
    root = os.path.join(WB, "connectors")
    if not os.path.isdir(root):
        return None
    for name in os.listdir(root):
        if os.path.isfile(os.path.join(root, name, "connector-states.json")):
            return os.path.join(root, name)
    return None


def plugin_manifest() -> dict:
    """由 connector-meta.json 派生插件清单（WorkBuddy 消费的是这套布局）。"""
    display = {
        "name": META["name"],
        "name_en": META.get("name_en", META["name"]),
        "description_zh": META.get("description_zh", META.get("description", "")),
        "description_en": META.get("description_en", META.get("description", "")),
        "examples_zh": META.get("examples_zh", []),
        "examples_en": META.get("examples_en", []),
    }
    return {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": NAME,
        "version": VER,
        "description": META.get("description_zh") or META.get("description", ""),
        "keywords": ["skills", "cli"],
        "extensions": {"ai.workbuddy": {"schemaVersion": "1.0.0", "display": display}},
    }


def build_package(dest: str) -> None:
    """装出 WorkBuddy 认的包布局（与官方市场里的 CLI 连接器同形）。"""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "ai.workbuddy", "assets"))
    os.makedirs(os.path.join(dest, "skills", SKILL_DIR))
    write_json(os.path.join(dest, ".codebuddy-plugin", "plugin.json"), plugin_manifest())
    shutil.copy2(os.path.join(SRC, "cli.json"), os.path.join(dest, "ai.workbuddy", "cli.json"))
    shutil.copy2(os.path.join(SRC, "icon.svg"), os.path.join(dest, "ai.workbuddy", "assets", "icon.svg"))
    shutil.copy2(os.path.join(SRC, "skills", SKILL_DIR, "SKILL.md"),
                 os.path.join(dest, "skills", SKILL_DIR, "SKILL.md"))


def backup(paths: list[str]) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(WB, ".bak-install", "connector-" + stamp)
    os.makedirs(bak, exist_ok=True)
    for p in paths:
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(bak, p.replace(os.sep, "__")))
    return bak


def install() -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    kp = os.path.join(WB, "plugins", "known_marketplaces.json")
    ip = os.path.join(WB, "plugins", "installed_plugins.json")
    sp = os.path.join(WB, "settings.json")
    idx = os.path.join(WB, "connectors-marketplace", ".codebuddy-connector", "connectors.json")
    offmp = os.path.join(WB, "plugins", "marketplaces", "workbuddy-connector-plugins-official",
                         ".codebuddy-plugin", "marketplace.json")
    st_dir = find_state_dir()
    bak = backup([kp, ip, sp, idx, offmp] + ([os.path.join(st_dir, "connector-states.json"),
                                              os.path.join(st_dir, "connector-states.v3.json")] if st_dir else []))
    say(f"备份 → {bak}")

    # 1 市场注册（directory 型，源指本仓 connector/local 的生成目录外的稳定位置：插件目录本身）
    d = read_json(kp)
    d[MARKET] = {
        "manifestName": MARKET, "type": "directory",
        "source": {"source": "directory", "path": SRC},
        "installLocation": SRC,
        "description": f"Marketplace from {SRC}",
        "lastUpdated": now, "autoUpdate": False,
    }
    write_json(kp, d)
    say(f"1 市场注册 {MARKET}")

    # 2 插件缓存
    cache = os.path.join(WB, "plugins", "cache", MARKET, NAME, VER)
    build_package(cache)
    write_json(os.path.join(cache, ".codebuddy-directory-source.json"),
               {"format": 1, "sourceRoot": SRC})
    say(f"2 插件缓存 {cache}")

    # 3 安装条目
    d = read_json(ip, {"version": 2, "plugins": {}})
    d.setdefault("plugins", {})
    prev = (d["plugins"].get(PID) or [{}])[0]
    d["plugins"][PID] = [{"scope": "user", "installPath": cache, "version": VER,
                          "installedAt": prev.get("installedAt", now), "lastUpdated": now}]
    write_json(ip, d)
    say(f"3 安装条目 {PID} → {VER}")

    # 4 启用插件
    d = read_json(sp)
    d.setdefault("enabledPlugins", {})[PID] = True
    write_json(sp, d)
    say("4 插件已启用")

    # 5 连接器市场包目录 + 索引 + 图标
    cm = os.path.join(WB, "connectors-marketplace")
    cat_pkg = os.path.join(cm, "connectors", NAME)
    if os.path.isdir(cat_pkg):
        shutil.rmtree(cat_pkg)
    os.makedirs(os.path.join(cat_pkg, "skills", SKILL_DIR))
    shutil.copy2(os.path.join(SRC, "cli.json"), os.path.join(cat_pkg, "cli.json"))
    shutil.copy2(os.path.join(SRC, "skills", SKILL_DIR, "SKILL.md"),
                 os.path.join(cat_pkg, "skills", SKILL_DIR, "SKILL.md"))
    entry = {
        "id": NAME, "name": META["name"], "name_en": META.get("name_en", NAME),
        "description": META.get("description", ""),
        "description_zh": META.get("description_zh", ""),
        "description_en": META.get("description_en", ""),
        "source": NAME, "type": META.get("type", "cli"),
        "examples_zh": META.get("examples_zh", []), "examples_en": META.get("examples_en", []),
    }
    d = read_json(idx, {"connectors": []})
    d["connectors"] = [x for x in d.get("connectors", []) if x.get("id") != NAME] + [entry]
    write_json(idx, d)
    icon = os.path.join(cm, "icons", NAME + ".svg")
    os.makedirs(os.path.dirname(icon), exist_ok=True)
    shutil.copy2(os.path.join(SRC, "icon.svg"), icon)
    say(f"5 市场包目录 + 索引条目 + 图标（索引共 {len(d['connectors'])} 条）")

    # 5b 官方本地市场镜像（连接器页「安装」按钮回落用；官方刷新会覆盖，可重跑本脚本）
    off_pkg = os.path.join(WB, "plugins", "marketplaces", "workbuddy-connector-plugins-official",
                           "connectors", NAME)
    if os.path.isdir(off_pkg):
        shutil.rmtree(off_pkg)
    shutil.copytree(cache, off_pkg)
    try:
        os.remove(os.path.join(off_pkg, ".codebuddy-directory-source.json"))
    except FileNotFoundError:
        pass
    if os.path.isfile(offmp):
        d = read_json(offmp)
        plugs = [p for p in d.get("plugins", []) if p.get("name") != NAME]
        plugs.append({"name": NAME, "description": META.get("description_zh", ""),
                      "source": f"./connectors/{NAME}", "version": VER})
        d["plugins"] = plugs
        write_json(offmp, d)
        say(f"5b 官方本地市场镜像（插件数 {len(plugs)}）")

    # 6 启用态：v4 为准（connectors[id]={bound,enabled}），v3 仅镜像
    st_dir = find_state_dir()
    if not st_dir:
        say("6 跳过启用态：找不到 connectors/<uid>/（多半还没登录过 WorkBuddy）")
    else:
        p4 = os.path.join(st_dir, "connector-states.json")
        d = read_json(p4, {"version": 4, "connectors": {}})
        d.setdefault("connectors", {})[NAME] = {"bound": True, "enabled": True}
        write_json(p4, d)
        os.chmod(p4, 0o600)
        p3 = os.path.join(st_dir, "connector-states.v3.json")
        if os.path.isfile(p3):
            d3 = read_json(p3)
            for k in ("enabled", "everConnected"):
                arr = d3.get(k) or []
                if NAME not in arr:
                    arr.append(NAME)
                d3[k] = arr
            write_json(p3, d3)
            os.chmod(p3, 0o600)
        say("6 启用态已写（bound=true, enabled=true）")

    verify()


def verify() -> None:
    cli = read_json(os.path.join(SRC, "cli.json"))
    plat = "win32" if sys.platform.startswith("win") else ("darwin" if sys.platform == "darwin" else "linux")
    say("— 探活 —")
    vc = cli.get("versionCheck") or {}
    if vc.get("command"):
        try:
            out = subprocess.run(vc["command"][plat], shell=True, capture_output=True, text=True).stdout.strip()
            m = re.search(vc.get("versionPattern", r"(\d+\.\d+\.\d+)"), out)
            say(f"版本：{out!r} → {m.group(1) if m else '未识别'}（minVersion {vc.get('minVersion', '-')}）")
        except Exception as e:  # noqa: BLE001
            say(f"版本检查跳过：{e}")
    try:
        out = subprocess.run(cli["status"][plat], shell=True, capture_output=True, text=True).stdout
    except Exception as e:  # noqa: BLE001
        die(f"status 命令跑不起来：{e}")
    ok = bool(re.search(cli.get("statusMatch", ""), out))
    say(f"登录态：{'已连接' if ok else '未连接（请先 rsrs login）'}")
    say("完事——完全退出并重开 WorkBuddy 才生效。")


def uninstall() -> None:
    kp = os.path.join(WB, "plugins", "known_marketplaces.json")
    ip = os.path.join(WB, "plugins", "installed_plugins.json")
    sp = os.path.join(WB, "settings.json")
    idx = os.path.join(WB, "connectors-marketplace", ".codebuddy-connector", "connectors.json")
    offmp = os.path.join(WB, "plugins", "marketplaces", "workbuddy-connector-plugins-official",
                         ".codebuddy-plugin", "marketplace.json")
    say(f"备份 → {backup([kp, ip, sp, idx, offmp])}")

    shutil.rmtree(os.path.join(WB, "plugins", "cache", MARKET, NAME), ignore_errors=True)
    shutil.rmtree(os.path.join(WB, "connectors-marketplace", "connectors", NAME), ignore_errors=True)
    shutil.rmtree(os.path.join(WB, "plugins", "marketplaces", "workbuddy-connector-plugins-official",
                               "connectors", NAME), ignore_errors=True)
    for p, fn in ((kp, lambda d: d.pop(MARKET, None)),
                  (ip, lambda d: d.get("plugins", {}).pop(PID, None)),
                  (sp, lambda d: d.get("enabledPlugins", {}).pop(PID, None)),
                  (idx, lambda d: d.__setitem__("connectors",
                                                [x for x in d.get("connectors", []) if x.get("id") != NAME])),
                  (offmp, lambda d: d.__setitem__("plugins",
                                                  [x for x in d.get("plugins", []) if x.get("name") != NAME]))):
        if os.path.isfile(p):
            d = read_json(p)
            fn(d)
            write_json(p, d)
    st_dir = find_state_dir()
    if st_dir:
        p4 = os.path.join(st_dir, "connector-states.json")
        if os.path.isfile(p4):
            d = read_json(p4)
            d.get("connectors", {}).pop(NAME, None)
            write_json(p4, d)
            os.chmod(p4, 0o600)
    say("已卸载——重启 WorkBuddy 生效。市场注册保留，重装直接再跑本脚本。")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
