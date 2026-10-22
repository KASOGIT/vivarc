#!/usr/bin/env python3
"""Vivarc: an Arc-style sidebar, command bar and theme editor for Vivaldi (macOS).

    ./vivarc.py install        set everything up (Vivaldi must be closed)
    ./vivarc.py apply          re-inject the JS after a Vivaldi update
    ./vivarc.py status         show what is installed
    ./vivarc.py import-arc     export your Arc spaces for import into Vivaldi
    ./vivarc.py uninstall      put everything back

Standard library only. Every file it changes is backed up under ~/.vivarc/backup first.
"""
import argparse
import copy
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request

VERSION = "0.1.0"
HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.join(HOME, ".vivarc")
DEFAULT_APP = "/Applications/Vivaldi.app"
DEFAULT_DATA = os.path.join(HOME, "Library", "Application Support", "Vivaldi")
RESOURCES = "Contents/Frameworks/Vivaldi Framework.framework/Resources/vivaldi"

FLAGS = ["vivaldi-css-mods@1", "vivaldi-horizontal-pinned-tabs@1"]
BEGIN, END = "<!-- vivarc:begin -->", "<!-- vivarc:end -->"
BLOCK = f'{BEGIN}\n<script src="vivarc.js"></script>\n{END}'
FREED_KEY = "meta+t"  # the command bar listens for Cmd+T itself
COPY_URL_KEY = "shift+meta+c"
TOGGLE_SIDEBAR_KEY = "meta+s"

# Peek is community code (GPL-3.0, PaRr0tBoY/Awesome-Vivaldi). It is downloaded at install time from a
# pinned commit and verified; nothing of it is stored in this repository.
PEEK_COMMIT = "04a37c2be209d9fd4ec770ec5d703a189c2c08d6"
PEEK_BASE = f"https://raw.githubusercontent.com/PaRr0tBoY/Awesome-Vivaldi/{PEEK_COMMIT}/Vivaldi8.0Stable"
PEEK_FILES = {
    "VividPeek.js": ("Javascripts/VividPeek.js", "54c45b3ab0f3be6554a13ebb70a8b13100592502ed9e7a7582db7401b7ac818a"),
    "VividPeek.css": ("CSS/VividPeek.css", "8196dec18bac4f46bfb12c246a366456f42cbb42b6e9af77183b1ad0c95b08f7"),
}

_MISSING = object()
TOUCHED = [
    ("vivaldi", "actions"),
    ("vivaldi", "toolbars", "tabbar_before"),
    ("vivaldi", "toolbars", "tabbar_after"),
    ("vivaldi", "tabs", "bar", "position"),
    ("vivaldi", "appearance", "css_ui_mods_directory"),
]


# ---------------------------------------------------------------- pure helpers
def _get(d, path):
    for key in path:
        if not isinstance(d, dict) or key not in d:
            return _MISSING
        d = d[key]
    return d


def _set(d, path, value):
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def _delete(d, path):
    chain = [d]
    for key in path[:-1]:
        if key not in chain[-1]:
            return
        chain.append(chain[-1][key])
    chain[-1].pop(path[-1], None)
    for parent, key in zip(reversed(chain[:-1]), reversed(path[:-1])):
        if parent[key] == {}:
            del parent[key]


def _snapshot(prefs):
    snap = {}
    for path in TOUCHED:
        value = _get(prefs, path)
        snap[".".join(path)] = {"present": value is not _MISSING, "value": None if value is _MISSING else copy.deepcopy(value)}
    return snap


def _command(actions, defaults, name):
    if name not in actions:
        actions[name] = copy.deepcopy(defaults.get(name, {"shortcuts": []}))
    actions[name].setdefault("shortcuts", [])
    return actions[name]


def swap_vpn_for_downloads(items):
    out = []
    for item in items:
        item = "PanelDownloads" if item == "VPNButton" else item
        if item not in out or item in ("FlexibleSpacer", "Spacer"):
            out.append(item)
    return out


def patch_preferences(prefs, default_actions, css_dir):
    """Return (patched copy, snapshot of the original values of everything touched)."""
    new = copy.deepcopy(prefs)
    snap = _snapshot(prefs)
    existing = _get(new, ("vivaldi", "actions"))
    actions_list = copy.deepcopy(default_actions) if existing is _MISSING else existing
    actions = actions_list[0]
    defaults = default_actions[0]
    for name in ("COMMAND_NEW_TAB", "COMMAND_SHOW_QUICK_COMMANDS"):
        cmd = _command(actions, defaults, name)
        cmd["shortcuts"] = [s for s in cmd["shortcuts"] if s != FREED_KEY]
    copy_url = _command(actions, defaults, "COMMAND_PAGE_COPY_URL")
    if COPY_URL_KEY not in copy_url["shortcuts"]:
        copy_url["shortcuts"].append(COPY_URL_KEY)
    for name, cmd in defaults.items():
        if TOGGLE_SIDEBAR_KEY in cmd.get("shortcuts", []):
            _command(actions, defaults, name)
    for cmd in actions.values():
        if isinstance(cmd, dict):
            cmd["shortcuts"] = [s for s in cmd.get("shortcuts", []) if s != TOGGLE_SIDEBAR_KEY]
    _command(actions, defaults, "COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR")["shortcuts"] = [TOGGLE_SIDEBAR_KEY]
    _set(new, ("vivaldi", "actions"), actions_list)

    bar = _get(new, ("vivaldi", "toolbars", "tabbar_before"))
    if bar is not _MISSING:
        _set(new, ("vivaldi", "toolbars", "tabbar_before"), [x for x in bar if x not in ("Spacer", "WorkspaceButton")])
    after = _get(new, ("vivaldi", "toolbars", "tabbar_after"))
    if after is not _MISSING:
        _set(new, ("vivaldi", "toolbars", "tabbar_after"), swap_vpn_for_downloads(after))
    _set(new, ("vivaldi", "tabs", "bar", "position"), 1)
    _set(new, ("vivaldi", "appearance", "css_ui_mods_directory"), css_dir)
    return new, snap


def restore_preferences(prefs, snap):
    new = copy.deepcopy(prefs)
    for dotted, saved in snap.items():
        path = tuple(dotted.split("."))
        if saved["present"]:
            _set(new, path, copy.deepcopy(saved["value"]))
        else:
            _delete(new, path)
    return new


def patch_local_state(ls):
    """Return (patched copy, flags that were added)."""
    new = copy.deepcopy(ls)
    flags = new.setdefault("browser", {}).setdefault("enabled_labs_experiments", [])
    added = [f for f in FLAGS if f not in flags]
    flags.extend(added)
    return new, added


def restore_local_state(ls, added):
    new = copy.deepcopy(ls)
    flags = _get(new, ("browser", "enabled_labs_experiments"))
    if flags is not _MISSING:
        new["browser"]["enabled_labs_experiments"] = [f for f in flags if f not in added]
    return new


def inject_window_html(html):
    if BEGIN in html:
        html = remove_window_html(html)
    return html.replace("</body>", BLOCK + "\n</body>", 1)


def remove_window_html(html):
    return re.sub(r"\n?" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "\n", html, flags=re.S)


def find_profiles(local_state):
    cache = _get(local_state, ("profile", "info_cache"))
    if cache is _MISSING or not cache:
        return [("Default", "Default")]
    return [(key, cache[key].get("name", key)) for key in sorted(cache)]


def build_bundle(js_dir, config, extras=(), pre=()):
    """Config first, then `pre` scripts (globals the modules read at load), the modules, then `extras`."""
    parts = ["window.__vmConfig = " + json.dumps(config) + ";\n"]
    for name, source in pre:
        parts.append(f"\n// ---- {name}\n{source}")
    for name in sorted(os.listdir(js_dir)):
        if name.endswith(".js"):
            parts.append(f"\n// ---- {name}\n" + read_text(os.path.join(js_dir, name)))
    for name, source in extras:
        parts.append(f"\n// ---- {name}\n{source}")
    return "".join(parts)


# ---------------------------------------------------------------- io helpers
def read_text(path):
    with open(path, encoding="utf8") as f:
        return f.read()


def read_json(path):
    with open(path, encoding="utf8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)


def vivaldi_running():
    return subprocess.run(["pgrep", "-x", "Vivaldi"], capture_output=True).returncode == 0


def app_version(app):
    out = subprocess.run(["defaults", "read", os.path.join(app, "Contents/Info"), "CFBundleShortVersionString"],
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def die(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def say(message):
    print(message)


def load_state():
    path = os.path.join(HOME_DIR, "state.json")
    return read_json(path) if os.path.exists(path) else {"profiles": {}, "flags_added": [], "version": VERSION}


def save_state(state):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(os.path.join(HOME_DIR, "state.json"), "w", encoding="utf8") as f:
        json.dump(state, f, indent=1)


def load_config():
    path = os.path.join(HOME_DIR, "config.json")
    return read_json(path) if os.path.exists(path) else {}


def backup_dir():
    path = os.path.join(HOME_DIR, "backup", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(path, exist_ok=True)
    return path


def fetch_peek():
    out_dir = os.path.join(HOME_DIR, "peek")
    os.makedirs(out_dir, exist_ok=True)
    for name, (path, sha) in PEEK_FILES.items():
        with urllib.request.urlopen(f"{PEEK_BASE}/{path}", timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"{name} does not match the pinned checksum")
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(data)
    return out_dir


def default_actions(resources):
    defs = read_json(os.path.join(resources, "prefs_definitions.json"))["vivaldi"]["actions"]
    key = {"Darwin": "default_mac", "Linux": "default_linux"}.get(platform.system(), "default")
    return defs[key]


def sync_css():
    """Copy the stylesheet (and Peek's, if downloaded) to the folder Vivaldi loads CSS mods from, and the guide page."""
    css_dir = os.path.join(HOME_DIR, "css")
    os.makedirs(css_dir, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "src/css/vivarc.css"), css_dir)
    peek_css = os.path.join(HOME_DIR, "peek", "VividPeek.css")
    if os.path.exists(peek_css):
        shutil.copy2(peek_css, css_dir)
    start_dir = os.path.join(HOME_DIR, "start")
    os.makedirs(start_dir, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "src/start/index.html"), start_dir)
    return css_dir


def write_bundle(resources, with_peek):
    extras, pre = [], []
    icons = os.path.join(HOME_DIR, "icons.js")
    if os.path.exists(icons):
        pre.append(("icons.js", read_text(icons)))
    peek_dir = os.path.join(HOME_DIR, "peek")
    if with_peek and os.path.exists(os.path.join(peek_dir, "VividPeek.js")):
        extras.append(("peek-stubs.js", read_text(os.path.join(HERE, "src/optional/peek-stubs.js"))))
        extras.append(("VividPeek.js", read_text(os.path.join(peek_dir, "VividPeek.js"))))
    start_page = pathlib.Path(HOME_DIR, "start", "index.html").as_uri()
    config = {**load_config(), "cssDir": os.path.join(HOME_DIR, "css"), "startUrl": start_page}
    bundle = build_bundle(os.path.join(HERE, "src/js"), config, extras, pre)
    with open(os.path.join(resources, "vivarc.js"), "w", encoding="utf8") as f:
        f.write(bundle)


def apply_js(app, resources, with_peek):
    html_path = os.path.join(resources, "window.html")
    html = read_text(html_path)
    saved = os.path.join(HOME_DIR, "backup", f"window.html.{app_version(app)}.orig")
    os.makedirs(os.path.dirname(saved), exist_ok=True)
    if BEGIN not in html and not os.path.exists(saved):
        shutil.copy2(html_path, saved)
    write_bundle(resources, with_peek)
    with open(html_path, "w", encoding="utf8") as f:
        f.write(inject_window_html(html))


def permission_hint(error):
    die(f"{error}\nmacOS blocked writing into Vivaldi.app. Open System Settings > Privacy & Security > "
        "App Management, allow your terminal app, then run the command again.")


# ---------------------------------------------------------------- commands
def cmd_install(args):
    app, data = args.app, args.data_dir
    resources = os.path.join(app, RESOURCES)
    if not os.path.isdir(resources):
        die(f"Vivaldi not found at {app} (use --app)")
    if vivaldi_running() and not args.dry_run:
        die("Quit Vivaldi (Cmd+Q) first, then run this again.")
    local_state_path = os.path.join(data, "Local State")
    local_state = read_json(local_state_path)
    profiles = find_profiles(local_state)
    if args.profiles:
        wanted = set(args.profiles.split(","))
        profiles = [p for p in profiles if p[0] in wanted or p[1] in wanted]
    say(f"Vivaldi {app_version(app)}; profiles: {', '.join(f'{n} ({d})' for d, n in profiles)}")
    if args.dry_run:
        say("dry run: nothing written")
        return

    state = load_state()
    backup = backup_dir()
    css_dir = sync_css()
    config_path = os.path.join(HOME_DIR, "config.json")
    if not os.path.exists(config_path):
        write_json(config_path, {})

    if not args.no_peek:
        try:
            fetch_peek()
            sync_css()
            say("Peek (community mod, GPL-3.0) downloaded and verified")
        except Exception as error:  # network or checksum problem: Peek is optional
            say(f"Peek skipped: {error}")

    actions = default_actions(resources)
    for directory, name in profiles:
        prefs_path = os.path.join(data, directory, "Preferences")
        if not os.path.exists(prefs_path):
            continue
        os.makedirs(os.path.join(backup, directory), exist_ok=True)
        shutil.copy2(prefs_path, os.path.join(backup, directory, "Preferences"))
        prefs = read_json(prefs_path)
        old_css = _get(prefs, ("vivaldi", "appearance", "css_ui_mods_directory"))
        if old_css not in (_MISSING, "", css_dir) and not args.force:
            say(f"  {name}: already uses CSS mods in {old_css}; skipped (use --force to replace)")
            continue
        new, snap = patch_preferences(prefs, actions, css_dir)
        state["profiles"].setdefault(directory, snap)
        write_json(prefs_path, new)
        say(f"  {name}: configured")

    shutil.copy2(local_state_path, os.path.join(backup, "Local State"))
    new_ls, added = patch_local_state(local_state)
    write_json(local_state_path, new_ls)
    state["flags_added"] = sorted(set(state["flags_added"]) | set(added))
    state["version"] = VERSION
    save_state(state)

    try:
        apply_js(app, resources, not args.no_peek)
    except PermissionError as error:
        permission_hint(error)
    say("Done. Open Vivaldi. After a Vivaldi update, run: ./vivarc.py apply")


def cmd_apply(args):
    resources = os.path.join(args.app, RESOURCES)
    if vivaldi_running():
        die("Quit Vivaldi (Cmd+Q) first, then run this again.")
    sync_css()
    try:
        apply_js(args.app, resources, os.path.exists(os.path.join(HOME_DIR, "peek", "VividPeek.js")))
    except PermissionError as error:
        permission_hint(error)
    say(f"Re-applied to Vivaldi {app_version(args.app)}")


def cmd_uninstall(args):
    resources = os.path.join(args.app, RESOURCES)
    if vivaldi_running():
        die("Quit Vivaldi (Cmd+Q) first, then run this again.")
    state = load_state()
    for directory, snap in state["profiles"].items():
        prefs_path = os.path.join(args.data_dir, directory, "Preferences")
        if os.path.exists(prefs_path):
            write_json(prefs_path, restore_preferences(read_json(prefs_path), snap))
            say(f"  {directory}: restored")
    ls_path = os.path.join(args.data_dir, "Local State")
    if os.path.exists(ls_path):
        ours = os.path.join(HOME_DIR, "css")
        blank = {".".join(path): {"present": False, "value": None} for path in TOUCHED}
        for directory, _name in find_profiles(read_json(ls_path)):
            prefs_path = os.path.join(args.data_dir, directory, "Preferences")
            if directory in state["profiles"] or not os.path.exists(prefs_path):
                continue
            prefs = read_json(prefs_path)
            if _get(prefs, ("vivaldi", "appearance", "css_ui_mods_directory")) == ours:
                write_json(prefs_path, restore_preferences(prefs, blank))  # created after install: defaults were the original
                say(f"  {directory}: reset to Vivaldi defaults (configured by Vivarc at runtime)")
        write_json(ls_path, restore_local_state(read_json(ls_path), state["flags_added"]))
    html_path = os.path.join(resources, "window.html")
    try:
        if os.path.exists(html_path):
            html = read_text(html_path)
            with open(html_path, "w", encoding="utf8") as f:
                f.write(remove_window_html(html))
        bundle = os.path.join(resources, "vivarc.js")
        if os.path.exists(bundle):
            os.remove(bundle)
    except PermissionError as error:
        permission_hint(error)
    if args.purge:
        shutil.rmtree(HOME_DIR, ignore_errors=True)
    say("Vivarc removed. Your bookmarks (including the Vivarc folder) were left alone.")


def cmd_status(args):
    resources = os.path.join(args.app, RESOURCES)
    html_path = os.path.join(resources, "window.html")
    injected = os.path.exists(html_path) and BEGIN in read_text(html_path)
    say(f"Vivarc {VERSION}; Vivaldi {app_version(args.app)} (running: {vivaldi_running()})")
    say(f"JS injected: {injected}" + ("" if injected else "  -> run ./vivarc.py apply"))
    state = load_state()
    for directory, name in find_profiles(read_json(os.path.join(args.data_dir, "Local State"))):
        path = os.path.join(args.data_dir, directory, "Preferences")
        css = _get(read_json(path), ("vivaldi", "appearance", "css_ui_mods_directory")) if os.path.exists(path) else _MISSING
        say(f"  {name} ({directory}): {'configured' if directory in state['profiles'] else 'not configured'}"
            f", css dir {'ok' if css == os.path.join(HOME_DIR, 'css') else 'other/unset'}")


def cmd_import_arc(args):
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import arc_import
    arc_import.run(args.arc_dir, os.path.join(HOME_DIR, "import"), HOME_DIR)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vivarc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=DEFAULT_APP)
    parser.add_argument("--data-dir", default=DEFAULT_DATA)
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--profiles", help="comma-separated profile folders or names (default: all)")
    install.add_argument("--no-peek", action="store_true")
    install.add_argument("--force", action="store_true", help="replace an existing CSS mods folder")
    install.add_argument("--dry-run", action="store_true")
    sub.add_parser("apply")
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--purge", action="store_true", help="also delete ~/.vivarc")
    sub.add_parser("status")
    imp = sub.add_parser("import-arc")
    imp.add_argument("--arc-dir", default=os.path.join(HOME, "Library", "Application Support", "Arc"))
    args = parser.parse_args(argv)
    if platform.system() != "Darwin":
        die("Vivarc currently supports macOS only")
    {"install": cmd_install, "apply": cmd_apply, "uninstall": cmd_uninstall,
     "status": cmd_status, "import-arc": cmd_import_arc}[args.command](args)


if __name__ == "__main__":
    main()
