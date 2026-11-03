#!/usr/bin/env python3
"""respire 连接器（MCP 形态）· 本机安装 / 卸载

未上架前把连接器按 WorkBuddy 认的布局装到本机，让 **MCP 工具与 Skill 一起生效**。

为什么不能只写 `~/.workbuddy/mcp.json`：
    那样只注册一个「自定义 MCP」——16 个工具能用，但连接器随包带的 `SKILL.md` **不会加载**，
    模型看不到操作法（什么时候召回、怎么落库），等于没人触发记忆。
    要工具和技能同时在，必须按连接器包布局装。

用法：
    python3 connector/install_local.py             # 装 / 升级（幂等）
    python3 connector/install_local.py --uninstall # 卸（备份保留）

装完**完全退出并重开 WorkBuddy**。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

SRC = os.path.dirname(os.path.abspath(__file__))
WB = os.path.join(os.path.expanduser("~"), ".workbuddy")

NAME = "respire"                        # 连接器 source（市场清单 / 索引用）
PLUGIN = "respire-connector"            # 插件名：不能叫 respire，会与 plugins/respire 撞名
MARKET = "workbuddy-connector-plugins-official"
PID = f"{PLUGIN}@{MARKET}"
SKILL = "respire-memory"


def say(m: str) -> None:
    print(f"[respire-connector] {m}")


def die(m: str) -> None:
    print(f"[respire-connector] 失败：{m}", file=sys.stderr)
    sys.exit(1)


def read(path: str, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def find_state_dir() -> str | None:
    root = os.path.join(WB, "connectors")
    if not os.path.isdir(root):
        return None
    for n in os.listdir(root):
        if os.path.isfile(os.path.join(root, n, "connector-states.json")):
            return os.path.join(root, n)
    return None


def backup(paths: list[str]) -> str:
    bak = os.path.join(WB, ".bak-install", "connector-mcp-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bak, exist_ok=True)
    for p in paths:
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(bak, p.replace(os.sep, "__")))
    return bak


def build_plugin(dest: str, meta: dict, mcp: dict) -> None:
    """按官方市场里 MCP 连接器的布局造包。"""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, ".codebuddy-plugin"))
    os.makedirs(os.path.join(dest, "ai.workbuddy", "assets"))
    os.makedirs(os.path.join(dest, "skills", SKILL))
    shutil.copy2(os.path.join(SRC, "mcp.json"), os.path.join(dest, "mcp.json"))
    shutil.copy2(os.path.join(SRC, "icon.svg"), os.path.join(dest, "ai.workbuddy", "assets", "icon.svg"))
    shutil.copy2(os.path.join(SRC, "skills", SKILL, "SKILL.md"),
                 os.path.join(dest, "skills", SKILL, "SKILL.md"))

    server = next(iter((mcp.get("mcpServers") or {}).values()), {})
    plugin = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": PLUGIN,
        "version": meta.get("version", "1.0.0"),
        "description": meta.get("description_zh") or meta.get("description", ""),
        "keywords": ["skills", "mcp"],
        "extensions": {
            "ai.workbuddy": {
                "schemaVersion": "1.0.0",
                "display": {
                    "name": meta.get("name", "睿思记忆"),
                    "name_en": meta.get("name_en", "Respire Memory"),
                    "description_zh": meta.get("description_zh", ""),
                    "description_en": meta.get("description_en", ""),
                    "examples_zh": meta.get("examples_zh", []),
                    "examples_en": meta.get("examples_en", []),
                },
                "policy": {"mcpServers": {NAME: {"timeout": server.get("timeout", 60000)}}},
            }
        },
    }
    write(os.path.join(dest, ".codebuddy-plugin", "plugin.json"), plugin)


def install() -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    meta = read(os.path.join(SRC, "connector-meta.json"))
    mcp = read(os.path.join(SRC, "mcp.json"))
    if not (meta and mcp):
        die("connector-meta.json 或 mcp.json 读不到")
    ver = meta.get("version", "1.0.0")

    kp = os.path.join(WB, "plugins", "known_marketplaces.json")
    ip = os.path.join(WB, "plugins", "installed_plugins.json")
    sp = os.path.join(WB, "settings.json")
    idx = os.path.join(WB, "connectors-marketplace", ".codebuddy-connector", "connectors.json")
    mp = os.path.join(WB, "plugins", "marketplaces", MARKET, ".codebuddy-plugin", "marketplace.json")
    user_mcp = os.path.join(WB, "mcp.json")
    say(f"备份 → {backup([kp, ip, sp, idx, mp, user_mcp])}")

    market_dir = os.path.join(WB, "plugins", "marketplaces", MARKET)
    if not os.path.isdir(market_dir):
        die(f"官方连接器市场目录不在：{market_dir}（先让应用拉一次连接器市场）")

    # 1 市场清单
    if os.path.isfile(mp):
        d = read(mp)
        plugs = [p for p in d.get("plugins", []) if p.get("name") != PLUGIN]
        plugs.append({"name": PLUGIN, "description": meta.get("description_zh", ""),
                      "source": f"./connectors/{PLUGIN}", "version": ver})
        d["plugins"] = plugs
        write(mp, d)
        say(f"1 市场清单已登记（插件 {len(plugs)} 个）")

    # 2 市场里的连接器包
    pkg = os.path.join(market_dir, "connectors", PLUGIN)
    build_plugin(pkg, meta, mcp)
    say(f"2 连接器包 {pkg}")

    # 3 插件缓存
    cache = os.path.join(WB, "plugins", "cache", MARKET, PLUGIN, ver)
    build_plugin(cache, meta, mcp)
    write(os.path.join(cache, ".codebuddy-directory-source.json"),
          {"format": 1, "sourceRoot": pkg})
    say(f"3 插件缓存 {cache}")

    # 4 安装条目 + 启用
    d = read(ip, {"version": 2, "plugins": {}})
    d.setdefault("plugins", {})
    prev = (d["plugins"].get(PID) or [{}])[0]
    d["plugins"][PID] = [{"scope": "user", "installPath": cache, "version": ver,
                          "installedAt": prev.get("installedAt", now), "lastUpdated": now}]
    write(ip, d)
    d = read(sp)
    d.setdefault("enabledPlugins", {})[PID] = True
    write(sp, d)
    say(f"4 安装条目 {PID} → {ver}（已启用）")

    # 5 连接器索引 + 卡片包目录 + 图标
    cm = os.path.join(WB, "connectors-marketplace")
    card = os.path.join(cm, "connectors", NAME)
    if os.path.isdir(card):
        shutil.rmtree(card)
    os.makedirs(os.path.join(card, "skills", SKILL))
    shutil.copy2(os.path.join(SRC, "mcp.json"), os.path.join(card, "mcp.json"))
    shutil.copy2(os.path.join(SRC, "skills", SKILL, "SKILL.md"),
                 os.path.join(card, "skills", SKILL, "SKILL.md"))
    entry = {"id": NAME, "name": meta.get("name"), "name_en": meta.get("name_en"),
             "description": meta.get("description", ""),
             "description_zh": meta.get("description_zh", ""),
             "description_en": meta.get("description_en", ""),
             "source": NAME, "type": "mcp",
             "examples_zh": meta.get("examples_zh", []), "examples_en": meta.get("examples_en", []),
             "minWorkbuddyVersion": meta.get("minWorkbuddyVersion", "5.0.0")}
    d = read(idx, {"connectors": []})
    d["connectors"] = [x for x in d.get("connectors", []) if x.get("id") != NAME] + [entry]
    write(idx, d)
    ic = os.path.join(cm, "icons", NAME + ".svg")
    os.makedirs(os.path.dirname(ic), exist_ok=True)
    shutil.copy2(os.path.join(SRC, "icon.svg"), ic)
    say(f"5 连接器索引（共 {len(d['connectors'])} 条）+ 卡片包 + 图标")

    # 6 启用态（v4 为准，v3 镜像）
    sd = find_state_dir()
    if sd:
        p4 = os.path.join(sd, "connector-states.json")
        d = read(p4, {"version": 4, "connectors": {}})
        d.setdefault("connectors", {})[NAME] = {"bound": True, "enabled": True}
        write(p4, d)
        os.chmod(p4, 0o600)
        p3 = os.path.join(sd, "connector-states.v3.json")
        if os.path.isfile(p3):
            d3 = read(p3)
            for k in ("enabled", "everConnected"):
                arr = d3.get(k) or []
                if NAME not in arr:
                    arr.append(NAME)
                d3[k] = arr
            write(p3, d3)
            os.chmod(p3, 0o600)
        say("6 启用态 {bound:true, enabled:true}")
    else:
        say("6 跳过启用态：找不到 connectors/<uid>/")

    # 7 摘掉「自定义 MCP」那条，避免同一个 Server 注册两遍
    if os.path.isfile(user_mcp):
        d = read(user_mcp)
        srv = d.get("mcpServers", {})
        if NAME in srv:
            srv.pop(NAME)
            d["mcpServers"] = srv
            write(user_mcp, d)
            say("7 已从 ~/.workbuddy/mcp.json 摘掉重复的 respire（改由连接器声明）")
        else:
            say("7 ~/.workbuddy/mcp.json 无重复条目")

    say("完事——完全退出并重开 WorkBuddy。")


def uninstall() -> None:
    kp = os.path.join(WB, "plugins", "known_marketplaces.json")
    ip = os.path.join(WB, "plugins", "installed_plugins.json")
    sp = os.path.join(WB, "settings.json")
    idx = os.path.join(WB, "connectors-marketplace", ".codebuddy-connector", "connectors.json")
    mp = os.path.join(WB, "plugins", "marketplaces", MARKET, ".codebuddy-plugin", "marketplace.json")
    say(f"备份 → {backup([kp, ip, sp, idx, mp])}")

    for p in (os.path.join(WB, "plugins", "marketplaces", MARKET, "connectors", PLUGIN),
              os.path.join(WB, "plugins", "cache", MARKET, PLUGIN),
              os.path.join(WB, "connectors-marketplace", "connectors", NAME)):
        if os.path.isdir(p):
            shutil.rmtree(p)
            say(f"移除 {p}")

    for path, fn in (
        (ip, lambda d: d.get("plugins", {}).pop(PID, None)),
        (sp, lambda d: d.get("enabledPlugins", {}).pop(PID, None)),
        (mp, lambda d: d.__setitem__("plugins", [x for x in d.get("plugins", []) if x.get("name") != PLUGIN])),
        (idx, lambda d: d.__setitem__("connectors", [x for x in d.get("connectors", []) if x.get("id") != NAME])),
    ):
        if os.path.isfile(path):
            d = read(path)
            fn(d)
            write(path, d)

    sd = find_state_dir()
    if sd:
        p4 = os.path.join(sd, "connector-states.json")
        if os.path.isfile(p4):
            d = read(p4)
            d.get("connectors", {}).pop(NAME, None)
            write(p4, d)
            os.chmod(p4, 0o600)
    say("已卸载——重启生效。备份在 .bak-install/connector-mcp-*。")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
