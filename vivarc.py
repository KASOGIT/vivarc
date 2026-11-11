#!/usr/bin/env python3
"""Vivarc: an Arc-style sidebar, command bar and theme editor for Vivaldi (macOS and Windows).

    ./vivarc.py install        set everything up (Vivaldi must be closed)
    ./vivarc.py update         fetch the latest Vivarc and re-apply it (also after a Vivaldi update)
    ./vivarc.py apply          re-inject the JS only
    ./vivarc.py status         show what is installed
    ./vivarc.py import-arc     export your Arc spaces for import into Vivaldi
    ./vivarc.py uninstall      put everything back

Standard library only. Every file it changes is backed up under ~/.vivarc/backup first.
"""
import argparse
import copy
import glob
import hashlib
import json
import os
import pathlib
import platform
import plistlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import urllib.request

VERSION = "0.1.30"
IS_WIN = os.name == "nt"
HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.join(HOME, ".vivarc")
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.join(HOME, "AppData", "Local"))


def _default_win_app():
    """Vivaldi installs per user by default; a machine-wide install lives under Program Files."""
    per_user = os.path.join(LOCALAPPDATA, "Vivaldi", "Application")
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        machine = os.path.join(base, "Vivaldi", "Application") if base else None
        if machine and not os.path.isdir(per_user) and os.path.isdir(machine):
            return machine
    return per_user


if IS_WIN:
    DEFAULT_APP = os.environ.get("VIVARC_APP") or _default_win_app()
    DEFAULT_DATA = os.environ.get("VIVARC_DATA_DIR") or os.path.join(LOCALAPPDATA, "Vivaldi", "User Data")
    START_MENU = os.path.join(os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming")),
                              "Microsoft", "Windows", "Start Menu", "Programs", "Vivarc")
    UPDATE_COMMAND = os.path.join(HOME_DIR, "Update Vivarc.cmd")
    UPDATE_APP = os.path.join(START_MENU, "Update Vivarc.lnk")
    UNINSTALL_COMMAND = os.path.join(HOME_DIR, "Uninstall Vivarc.cmd")
    UNINSTALL_APP = os.path.join(START_MENU, "Uninstall Vivarc.lnk")
    LEGACY_UPDATE_COMMAND = os.path.join(HOME_DIR, "Update Vivarc.command")  # never written on Windows
else:
    DEFAULT_APP = os.environ.get("VIVARC_APP", "/Applications/Vivaldi.app")
    DEFAULT_DATA = os.environ.get("VIVARC_DATA_DIR", os.path.join(HOME, "Library", "Application Support", "Vivaldi"))
    UPDATE_COMMAND = os.path.join(HOME_DIR, "Update Vivarc.command")
    UPDATE_APP = os.path.join(HOME, "Applications", "Update Vivarc.app")
    LEGACY_UPDATE_COMMAND = os.path.join(HOME, "Applications", "Update Vivarc.command")
    UNINSTALL_COMMAND = os.path.join(HOME_DIR, "Uninstall Vivarc.command")
    UNINSTALL_APP = os.path.join(HOME, "Applications", "Uninstall Vivarc.app")
UPDATE_MARK = "# Created by Vivarc"
LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
UPDATE_SCHEME = "vivarc"  # the sidebar button opens vivarc://update, which the Update Vivarc app answers
RELEASES_LATEST = "https://github.com/KASOGIT/vivarc/releases/latest"
INSTALL_PS1 = "https://raw.githubusercontent.com/KASOGIT/vivarc/main/install.ps1"
REMINDER_LABEL = "com.vivarc.reminder"
REMINDER_PLIST = os.path.join(HOME, "Library", "LaunchAgents", f"{REMINDER_LABEL}.plist")
REMINDER_TASK = "\\Vivarc\\Reapply"
REMIND_EVERY = 12 * 3600
RESOURCES = "Contents/Frameworks/Vivaldi Framework.framework/Resources/vivaldi"
WIN_VERSION_DIR = re.compile(r"^\d+(\.\d+){3}$")

BEGIN, END = "<!-- vivarc:begin -->", "<!-- vivarc:end -->"
BLOCK = f'{BEGIN}\n<script src="vivarc.js"></script>\n{END}'

# One table per platform; the JS gets the same table through the bundle config. On Windows the Win key is
# mostly taken by the OS (Win+S, Win+T, Win+Ctrl+arrows), so Ctrl stands in for Cmd like in Arc for Windows.
KEYS = {
    "mac": {
        "commandBar": "meta+t",  # freed from New Tab: the command bar listens for it itself
        "copyUrl": "shift+meta+c",
        "toggleSidebar": "meta+s",
        "profilePrev": "ctrl+meta+left", "profileNext": "ctrl+meta+right",  # handled by the JS profile switcher
        "profileMods": "ctrl+meta",  # + 1..9 opens the nth profile chip
        "spacePrev": "alt+meta+left", "spaceNext": "alt+meta+right",
        "spaceNew": "ctrl+meta+n",  # opens Vivaldi's own Create Workspace dialog
        "tabNext": "ctrl+tab", "tabPrev": "ctrl+shift+tab",  # freed from Vivaldi's tab cycling: the tab switcher handles them
    },
    "win": {
        "commandBar": "ctrl+t",
        "copyUrl": "ctrl+shift+c",  # taken from Copy to Note
        "toggleSidebar": "ctrl+s",  # taken from Save Page
        "profilePrev": "ctrl+alt+shift+left", "profileNext": "ctrl+alt+shift+right", "profileMods": "ctrl+alt+shift",
        "spacePrev": "ctrl+alt+left", "spaceNext": "ctrl+alt+right",
        "spaceNew": "ctrl+alt+n",
        "tabNext": "ctrl+tab", "tabPrev": "ctrl+shift+tab",
    },
}
KEY_LABELS = {"mac": {"meta": "Cmd", "alt": "Option", "ctrl": "Ctrl", "shift": "Shift"},
              "win": {"meta": "Win", "alt": "Alt", "ctrl": "Ctrl", "shift": "Shift"}}
PLATFORM = "win" if IS_WIN else "mac"


def use_keys(name):
    """Point the module-level key constants at one platform's table (tests call this to switch)."""
    global FREED_KEY, COPY_URL_KEY, PROFILE_KEYS, SPACE_KEYS, TAB_KEYS, TOGGLE_SIDEBAR_KEY
    k = KEYS[name]
    FREED_KEY = k["commandBar"]
    COPY_URL_KEY = k["copyUrl"]
    PROFILE_KEYS = (k["profilePrev"], k["profileNext"])
    TAB_KEYS = (k["tabNext"], k["tabPrev"])
    SPACE_KEYS = {"COMMAND_WORKSPACE_SWITCH_BACK_ORDER": k["spacePrev"], "COMMAND_WORKSPACE_SWITCH_FORWARD_ORDER": k["spaceNext"],
                  "COMMAND_WORKSPACE_CREATE_NEW": k["spaceNew"]}
    TOGGLE_SIDEBAR_KEY = k["toggleSidebar"]


use_keys(PLATFORM)
SIDEBAR_WIDTH = 323
SIDEBAR_BOTTOM = ["NewTab", "FlexibleSpacer", "AccountButton", "FlexibleSpacer", "PanelDownloads", "UpdateButton"]
SIDEBAR_TOOLBAR = ["TabButton", "Extensions", "FlexibleSpacer", "Back", "Reload", "Forward", "AddressField"]

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
    ("vivaldi", "address_bar", "visible"),
    ("vivaldi", "panels", "position"),
    ("vivaldi", "auto_hide", "enabled"),
    ("vivaldi", "auto_hide", "panel"),
    ("vivaldi", "auto_hide", "tab_bar"),
    ("vivaldi", "auto_hide", "address_bar"),
    ("vivaldi", "auto_hide", "status_bar"),
    ("vivaldi", "auto_hide", "bookmarks_bar"),
    ("vivaldi", "auto_hide", "show_introduction"),
    ("vivaldi", "status_bar", "display"),
    ("vivaldi", "tabs", "bar", "width"),
    ("vivaldi", "tabs", "bar", "position"),
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


def patch_preferences(prefs, default_actions, reapply=False):
    """Return (patched copy, snapshot of the original values of everything touched).
    On a re-apply (an update) the auto-hide choices the user made since are kept."""
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
    taken = PROFILE_KEYS + TAB_KEYS + tuple(SPACE_KEYS.values())
    for name, cmd in defaults.items():
        if any(key in cmd.get("shortcuts", []) for key in taken + (COPY_URL_KEY,)):
            _command(actions, defaults, name)
    for name, cmd in actions.items():
        if isinstance(cmd, dict):
            cmd["shortcuts"] = [s for s in cmd.get("shortcuts", []) if s != TOGGLE_SIDEBAR_KEY and s not in taken
                                and (s != COPY_URL_KEY or name == "COMMAND_PAGE_COPY_URL")]
    for name, key in SPACE_KEYS.items():
        _command(actions, defaults, name)["shortcuts"].append(key)
    _command(actions, defaults, "COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR")["shortcuts"] = [TOGGLE_SIDEBAR_KEY]
    _set(new, ("vivaldi", "actions"), actions_list)

    bar = _get(new, ("vivaldi", "toolbars", "tabbar_before"))
    bar = ["WorkspaceButton"] if bar is _MISSING else bar
    bar = [x for x in bar if x not in ("Spacer", "WorkspaceButton")]
    _set(new, ("vivaldi", "toolbars", "tabbar_before"), bar if "AddressField" in bar else list(SIDEBAR_TOOLBAR))
    _set(new, ("vivaldi", "address_bar", "visible"), False)
    after = _get(new, ("vivaldi", "toolbars", "tabbar_after"))
    after = swap_vpn_for_downloads([] if after is _MISSING else after)
    _set(new, ("vivaldi", "toolbars", "tabbar_after"), after if "AccountButton" in after else list(SIDEBAR_BOTTOM))
    _set(new, ("vivaldi", "panels", "position"), 1)
    _set(new, ("vivaldi", "auto_hide", "enabled"), True)
    for key, value in (("panel", True), ("tab_bar", False), ("address_bar", False), ("status_bar", False),
                       ("bookmarks_bar", False), ("show_introduction", False)):
        if not (reapply and _get(new, ("vivaldi", "auto_hide", key)) is not _MISSING):
            _set(new, ("vivaldi", "auto_hide", key), value)
    _set(new, ("vivaldi", "status_bar", "display"), 2)  # overlay: only appears on hover
    if _get(new, ("vivaldi", "tabs", "bar", "width")) is _MISSING:
        _set(new, ("vivaldi", "tabs", "bar", "width"), SIDEBAR_WIDTH)
    _set(new, ("vivaldi", "tabs", "bar", "position"), 1)
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


def looks_configured(prefs):
    """True when a profile carries Vivarc's keys (set at install, or at runtime by the JS for a newer profile)."""
    actions = _get(prefs, ("vivaldi", "actions"))
    if actions is _MISSING or not actions:
        return False
    table = actions[0]
    toggle = table.get("COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR", {}).get("shortcuts", [])
    copy_url = table.get("COMMAND_PAGE_COPY_URL", {}).get("shortcuts", [])
    new_tab = table.get("COMMAND_NEW_TAB", {}).get("shortcuts", [])
    return toggle == [TOGGLE_SIDEBAR_KEY] and COPY_URL_KEY in copy_url and FREED_KEY not in new_tab


def style_script(element_id, css):
    return ("(() => {\n"
            f"  const style = document.createElement(\"style\");\n  style.id = {json.dumps(element_id)};\n"
            f"  style.textContent = {json.dumps(css)};\n"
            "  (document.head || document.documentElement).append(style);\n})();\n")


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
    with open(path, "w", encoding="utf8", newline="\n") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)


def _version_key(name):
    return tuple(int(n) for n in name.split("."))


def win_version_dir(app):
    """Vivaldi for Windows keeps each version in its own folder (Application/8.3.4191.26/...), and an update leaves
    the old one next to the new one for a while: the newest folder that holds the UI is the one in use."""
    try:
        names = [n for n in os.listdir(app) if WIN_VERSION_DIR.match(n)
                 and os.path.exists(os.path.join(app, n, "resources", "vivaldi", "window.html"))]
    except OSError:
        return None
    return max(names, key=_version_key) if names else None


def win_app_dir(path):
    """--app and VIVARC_APP take the Application folder or the vivaldi.exe inside it."""
    return os.path.dirname(path) if path.lower().endswith(".exe") else path


def resources_dir(app):
    if IS_WIN:
        version = win_version_dir(app)
        if version:
            return os.path.join(app, version, "resources", "vivaldi")
        flat = os.path.join(app, "resources", "vivaldi")  # a standalone copy without version folders
        if os.path.exists(os.path.join(flat, "window.html")):
            return flat
        return os.path.join(app, "unknown", "resources", "vivaldi")
    return os.path.join(app, RESOURCES)


def vivaldi_exe(app):
    return os.path.join(app, "vivaldi.exe")


def _tasklist_has_vivaldi(output):
    return any(line.strip().lower().startswith("vivaldi.exe") for line in output.splitlines())


def vivaldi_running():
    if IS_WIN:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq vivaldi.exe", "/NH"], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return _tasklist_has_vivaldi(out.stdout)
    return subprocess.run(["pgrep", "-x", "Vivaldi"], capture_output=True).returncode == 0


def app_version(app):
    if IS_WIN:
        return win_version_dir(app) or "unknown"
    out = subprocess.run(["defaults", "read", os.path.join(app, "Contents/Info"), "CFBundleShortVersionString"],
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def die(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def say(message):
    print(message)


SETTINGS_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_AppBundles"


QUIT_KEYS = "Alt+F4" if IS_WIN else "Cmd+Q"


def ask(prompt):
    """Read an answer from the terminal even when stdin is a pipe; None when there is no terminal."""
    out_name, in_name = ("CONOUT$", "CONIN$") if IS_WIN else ("/dev/tty", "/dev/tty")
    try:
        with open(out_name, "w") as out, open(in_name) as tty:
            out.write(prompt)
            out.flush()
            return tty.readline().strip()
    except OSError:
        return None


def open_settings():
    if not IS_WIN:
        subprocess.run(["open", SETTINGS_PANE], check=False)


def quit_vivaldi():
    if IS_WIN:
        # Without /F taskkill asks the windows to close, so Vivaldi saves its session like a normal exit.
        subprocess.run(["taskkill", "/IM", "vivaldi.exe"], capture_output=True, check=False)
    else:
        subprocess.run(["osascript", "-e", 'tell application "Vivaldi" to quit'], check=False)
    for _ in range(40):
        if not vivaldi_running():
            return
        time.sleep(0.5)


def can_write(directory):
    try:
        probe = os.path.join(directory, f".vivarc-write-test-{os.getpid()}")
        with open(probe, "w"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def check_not_root():
    if IS_WIN:
        return
    if os.geteuid() == 0:
        die("Do not run Vivarc with sudo. It does not help (macOS asks for a separate permission, see below) "
            "and it leaves files in your home folder that only root can change.\n"
            "Run the same command without sudo. If macOS blocks it, allow your terminal under "
            "System Settings > Privacy & Security > App Management.")


def check_owner(path):
    if IS_WIN:
        return
    if os.path.exists(path) and os.stat(path).st_uid != os.getuid():
        die(f"{path} belongs to another user, probably from an earlier run with sudo. Fix it with:\n"
            f"  sudo chown -R \"$(whoami)\" \"{path}\"\nthen run the command again (without sudo).")


def ensure_vivaldi_closed(ask=None, quit_app=None):
    # Looked up at call time (not as default arguments) so a replaced ask/quit_vivaldi is honoured.
    ask, quit_app = ask or globals()["ask"], quit_app or quit_vivaldi
    if not vivaldi_running():
        return
    answer = ask("Vivaldi is open and must be closed first. Quit it now? [Y/n] ")
    if answer is None:
        die(f"Quit Vivaldi ({QUIT_KEYS}) first, then run this again. Nothing was changed.")
    if answer.lower() in ("", "y", "yes"):
        quit_app()
        if not vivaldi_running():
            return
        die(f"Vivaldi did not close. Quit it yourself ({QUIT_KEYS}), then run this again. Nothing was changed.")
    die("Vivaldi has to be closed first. Nothing was changed.")


def preflight(resources, ask=None, open_settings=None):
    """macOS only lets an app with the 'App Management' permission edit Vivaldi.app. Check before changing anything."""
    ask, open_settings = ask or globals()["ask"], open_settings or globals()["open_settings"]
    if IS_WIN:
        if not os.path.isdir(resources) or can_write(resources):
            return
        die(f"Cannot write into {resources}. Nothing was changed.\n"
            "Vivaldi is installed for all users (under Program Files), so changing it needs administrator rights: "
            "run this again from a terminal opened with 'Run as administrator', or reinstall Vivaldi for your user only.")
    opened = False
    for _ in range(5):
        if can_write(resources):
            return
        if not opened:
            say("macOS is not letting this terminal modify Vivaldi. This is a one-time permission:")
            say("  1. System Settings is opening on Privacy & Security > App Management")
            say("  2. Switch on the app you are typing this in (Terminal, iTerm...). Add it with + if it is missing.")
            say("  3. Come back here. If macOS asks to quit and reopen the terminal, do it and run the command again.")
            open_settings()
            opened = True
        answer = ask("Press Enter once it is switched on (or type q to stop): ")
        if answer is None:
            die("Cannot ask for the permission here. Nothing was changed. Allow your terminal under "
                "System Settings > Privacy & Security > App Management, then run the command again.")
        if answer.lower() == "q":
            die("Stopped. Nothing was changed.")
    die("Still no permission to modify Vivaldi. Nothing was changed. See the README troubleshooting section.")


def write_atomic(path, text):
    """Write next to the target and swap it in, so a reader never sees half a file and a stale owner cannot block us."""
    temp = f"{path}.vivarc-tmp"
    with open(temp, "w", encoding="utf8", newline="\n") as f:
        f.write(text)
    if IS_WIN and os.path.exists(path) and not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)  # Windows refuses to replace a read-only file
    os.replace(temp, path)


def load_state():
    path = os.path.join(HOME_DIR, "state.json")
    return read_json(path) if os.path.exists(path) else {"profiles": {}, "version": VERSION}


def save_state(state):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(os.path.join(HOME_DIR, "state.json"), "w", encoding="utf8", newline="\n") as f:
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


def sync_guide():
    start_dir = os.path.join(HOME_DIR, "start")
    os.makedirs(start_dir, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "src/start/index.html"), start_dir)


def write_bundle(resources, with_peek):
    extras, pre = [], [("vivarc.css", style_script("vivarc-css", read_text(os.path.join(HERE, "src/css/vivarc.css"))))]
    icons = os.path.join(HOME_DIR, "icons.js")
    if os.path.exists(icons):
        pre.append(("icons.js", read_text(icons)))
    peek_dir = os.path.join(HOME_DIR, "peek")
    peek_installed = with_peek and os.path.exists(os.path.join(peek_dir, "VividPeek.js"))
    if peek_installed:
        extras.append(("peek-stubs.js", read_text(os.path.join(HERE, "src/optional/peek-stubs.js"))))
        extras.append(("VividPeek.js", read_text(os.path.join(peek_dir, "VividPeek.js"))))
        extras.append(("VividPeek.css", style_script("vivarc-peek-css", read_text(os.path.join(peek_dir, "VividPeek.css")))))
    start_page = pathlib.Path(HOME_DIR, "start", "index.html").as_uri()
    config = {**load_config(), "startUrl": start_page, "platform": PLATFORM,
              "keys": KEYS[PLATFORM], "keyLabels": KEY_LABELS[PLATFORM], "version": VERSION,
              "peekInstalled": peek_installed}
    bundle = build_bundle(os.path.join(HERE, "src/js"), config, extras, pre)
    write_atomic(os.path.join(resources, "vivarc.js"), bundle)


def apply_js(app, resources, with_peek):
    html_path = os.path.join(resources, "window.html")
    html = read_text(html_path)
    saved = os.path.join(HOME_DIR, "backup", f"window.html.{app_version(app)}.orig")
    os.makedirs(os.path.dirname(saved), exist_ok=True)
    if BEGIN not in html and not os.path.exists(saved):
        shutil.copy2(html_path, saved)
    write_bundle(resources, with_peek)
    write_atomic(html_path, inject_window_html(html))


def is_newer(tag, current):
    try:
        return tuple(int(n) for n in tag.lstrip("v").split(".")) > tuple(int(n) for n in current.split("."))
    except (AttributeError, ValueError):
        return False


def latest_release_tag():
    try:
        with urllib.request.urlopen(RELEASES_LATEST, timeout=10) as response:
            return response.geturl().rsplit("/", 1)[-1]
    except OSError:
        return None


def console_python():
    """The python.exe next to the running interpreter: the scheduled task runs pythonw.exe, which has no console."""
    folder, name = os.path.split(sys.executable)
    if name.lower() == "pythonw.exe" and os.path.exists(os.path.join(folder, "python.exe")):
        return os.path.join(folder, "python.exe")
    return sys.executable


def windowless_python():
    folder = os.path.dirname(sys.executable)
    candidate = os.path.join(folder, "pythonw.exe")
    return candidate if os.path.exists(candidate) else sys.executable


def _cmd_quote(path):
    return '"' + path.replace("%", "%%") + '"'


def command_script(purpose, subcommand, app=None, python=None, data=None):
    if IS_WIN:
        app, data = app or DEFAULT_APP, data or DEFAULT_DATA
        return "\r\n".join([
            "@echo off",
            "chcp 65001 >nul",  # the file is UTF-8: read paths with a non-ASCII user name correctly
            f"rem {UPDATE_MARK}: {purpose}.",
            f"{_cmd_quote(python or console_python())} {_cmd_quote(os.path.join(HERE, 'vivarc.py'))} "
            f"--app {_cmd_quote(app)} --data-dir {_cmd_quote(data)} {subcommand}",
            "set status=%ERRORLEVEL%",
            f"if exist {_cmd_quote(vivaldi_exe(app))} start \"\" {_cmd_quote(vivaldi_exe(app))}",
            "if not %status%==0 pause",
            "exit /b %status%",
            ""])
    return ("#!/bin/bash\n"
            f"{UPDATE_MARK}: {purpose}.\n"
            f"/usr/bin/python3 {shlex.quote(os.path.join(HERE, 'vivarc.py'))} {subcommand}\n"
            "status=$?\n"
            "open -a Vivaldi\n"
            "exit $status\n")


def write_command(path, purpose, subcommand, app=None, data=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_atomic(path, command_script(purpose, subcommand, app=app, data=data))
    if not IS_WIN:
        os.chmod(path, 0o755)


def write_update_command(path, app=None, data=None):
    write_command(path, "updates Vivarc and brings it back after a Vivaldi update", "update", app, data)


def write_uninstall_command(path, app=None, data=None):
    write_command(path, "removes Vivarc and puts Vivaldi back as it was", "uninstall", app, data)


def powershell(script, env=None):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, env={**os.environ, **(env or {})},
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def register_protocol(scheme, command):
    script = ("$k = \"HKCU:\\Software\\Classes\\$env:VIVARC_PROTOCOL\"; New-Item -Path \"$k\\shell\\open\\command\" -Force | Out-Null; "
              "Set-ItemProperty -Path $k -Name '(default)' -Value \"URL:$env:VIVARC_PROTOCOL\"; "
              "New-ItemProperty -Path $k -Name 'URL Protocol' -Value '' -Force | Out-Null; "
              "Set-ItemProperty -Path \"$k\\shell\\open\\command\" -Name '(default)' -Value \"`\"$env:VIVARC_TARGET`\"\"")
    powershell(script, {"VIVARC_PROTOCOL": scheme, "VIVARC_TARGET": command})


def unregister_protocol(scheme, command):
    """Only a link that runs our own update script goes."""
    script = ("$k = \"HKCU:\\Software\\Classes\\$env:VIVARC_PROTOCOL\"; "
              "$run = (Get-ItemProperty -Path \"$k\\shell\\open\\command\" -ErrorAction SilentlyContinue).'(default)'; "
              "if ($run -like \"*$env:VIVARC_TARGET*\") { Remove-Item -Path $k -Recurse -Force }")
    powershell(script, {"VIVARC_PROTOCOL": scheme, "VIVARC_TARGET": command})


def write_update_app(app, command, scheme=None):
    if IS_WIN:
        # A Start Menu shortcut to the .cmd, so "Update Vivarc" can be found by typing it in Start.
        os.makedirs(os.path.dirname(app), exist_ok=True)
        script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:VIVARC_LNK); "
                  "$s.TargetPath = $env:VIVARC_TARGET; $s.WorkingDirectory = $env:VIVARC_HOME; "
                  "$s.Description = $env:VIVARC_MARK; "
                  "if (Test-Path $env:VIVARC_ICON) { $s.IconLocation = \"$env:VIVARC_ICON,0\" }; $s.Save()")
        out = powershell(script, {"VIVARC_LNK": app, "VIVARC_TARGET": command, "VIVARC_HOME": HOME_DIR,
                                  "VIVARC_MARK": UPDATE_MARK, "VIVARC_ICON": vivaldi_exe(DEFAULT_APP)})
        if out.returncode != 0:
            say(f"Could not create the Start Menu shortcut {os.path.basename(app)}: {out.stderr.strip()}")
        if scheme:
            register_protocol(scheme, command)
        return
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.dirname(app), exist_ok=True)
    run = f'do shell script "open -a Terminal " & quoted form of {json.dumps(command, ensure_ascii=False)} & " {UPDATE_MARK}"'
    lines = [run]
    if scheme:
        lines = ["on openUpdate()", run, "end openUpdate", "on run", "openUpdate()", "end run",
                 "on open location theURL", f'if theURL is "{scheme}://update" then openUpdate()', "end open location"]
    subprocess.run(["osacompile", "-o", app, *[a for line in lines for a in ("-e", line)]], check=True, capture_output=True)
    if scheme:
        plist = os.path.join(app, "Contents", "Info.plist")
        with open(plist, "rb") as f:
            info = plistlib.load(f)
        info["CFBundleURLTypes"] = [{"CFBundleURLName": "Vivarc", "CFBundleURLSchemes": [scheme]}]
        with open(plist, "wb") as f:
            plistlib.dump(info, f)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app], check=False, capture_output=True)
        subprocess.run([LSREGISTER, "-f", app], check=False, capture_output=True)


def _ours_lnk(path):
    """A .lnk keeps its description as UTF-16 (or ANSI in old files): look for our mark in the raw bytes."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return False
    return UPDATE_MARK.encode("utf-16-le") in data or UPDATE_MARK.encode() in data


def remove_update_app(app, scheme=None):
    if IS_WIN:
        if scheme:
            unregister_protocol(scheme, UPDATE_COMMAND)
        if os.path.exists(app) and _ours_lnk(app):
            os.remove(app)
            try:
                os.rmdir(os.path.dirname(app))  # only goes when empty
            except OSError:
                pass
        return
    source = os.path.join(app, "Contents", "Resources", "Scripts", "main.scpt")
    if os.path.exists(source) and UPDATE_MARK in subprocess.run(["osadecompile", source], capture_output=True, text=True).stdout:
        shutil.rmtree(app)


def remove_update_command(path):
    if os.path.exists(path) and UPDATE_MARK in read_text(path):
        os.remove(path)


def needs_reapply(resources):
    html_path = os.path.join(resources, "window.html")
    if not os.path.exists(html_path):
        return False
    return BEGIN not in read_text(html_path) or not os.path.exists(os.path.join(resources, "vivarc.js"))


MB_OK, MB_YESNO, MB_ICONINFORMATION, MB_ICONQUESTION, MB_SETFOREGROUND, MB_TOPMOST = 0x0, 0x4, 0x40, 0x20, 0x10000, 0x40000
IDYES = 6


def message_box(message, flags, timeout_ms=300000):
    """A Windows dialog from a windowless process; gives up after `timeout_ms` like the macOS dialog does."""
    import ctypes
    user32 = ctypes.windll.user32
    flags |= MB_SETFOREGROUND | MB_TOPMOST
    try:  # undocumented but present since Windows XP; falls back to a dialog without timeout
        return user32.MessageBoxTimeoutW(None, message, "Vivarc", flags, 0, timeout_ms)
    except AttributeError:
        return user32.MessageBoxW(None, message, "Vivarc", flags)


def prompt_update(message):
    if IS_WIN:
        return message_box(message, MB_YESNO | MB_ICONQUESTION) == IDYES
    script = (f'display dialog "{message}" with title "Vivarc" buttons {{"Later", "Update Vivarc"}} '
              'default button "Update Vivarc" giving up after 300')
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return "button returned:Update Vivarc" in out.stdout


def notify_quiet(message):
    if not IS_WIN:
        subprocess.run(["osascript", "-e", f'display notification "{message}" with title "Vivarc"'], capture_output=True)


def notify(message):
    if IS_WIN:
        message_box(message, MB_OK | MB_ICONINFORMATION)


def open_in_terminal(path):
    if IS_WIN:
        os.startfile(path)  # a .cmd opens in its own console window
        return
    subprocess.run(["open", "-a", "Terminal", path], check=False)


def launchctl(*args):
    subprocess.run(["launchctl", *args], capture_output=True, check=False)


def schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, check=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def reminder_task_command(app):
    parts = [f'"{windowless_python()}"', f'"{os.path.join(HERE, "vivarc.py")}"']
    if os.path.normcase(app) != os.path.normcase(DEFAULT_APP):
        parts += ["--app", f'"{app}"']
    return " ".join(parts + ["remind"])


def reminder_enabled():
    if IS_WIN:
        return schtasks("/Query", "/TN", REMINDER_TASK).returncode == 0
    return os.path.exists(REMINDER_PLIST)


def enable_reminder(app):
    if IS_WIN:
        # Every 30 minutes while you are logged in: re-applies Vivarc to a freshly updated Vivaldi on its own.
        out = schtasks("/Create", "/F", "/TN", REMINDER_TASK, "/SC", "MINUTE", "/MO", "30", "/IT",
                       "/TR", reminder_task_command(app))
        if out.returncode != 0:
            say(f"Could not create the scheduled task: {(out.stderr or out.stdout).strip()}")
        return
    script = os.path.join(HERE, "vivarc.py")
    for folder in ("Documents", "Desktop", "Downloads"):
        if HERE.startswith(os.path.join(HOME, folder) + os.sep):
            installed = os.path.join(HOME_DIR, "app", "vivarc.py")
            if os.path.exists(installed):
                script = installed
            else:
                say(f"Note: macOS does not let background jobs read ~/{folder}, so the reminder cannot run from this copy. "
                    "Use the copy the one-line install puts in ~/.vivarc/app.")
    agent = {
        "Label": REMINDER_LABEL,
        "ProgramArguments": ["/usr/bin/python3", script, "--app", app, "remind"],
        "RunAtLoad": True,
        "StartInterval": 3600,
        "WatchPaths": [os.path.join(app, "Contents", "Info.plist")],
    }
    os.makedirs(os.path.dirname(REMINDER_PLIST), exist_ok=True)
    with open(REMINDER_PLIST, "wb") as f:
        plistlib.dump(agent, f)
    domain = f"gui/{os.getuid()}"
    launchctl("bootout", f"{domain}/{REMINDER_LABEL}")
    launchctl("bootstrap", domain, REMINDER_PLIST)


def disable_reminder():
    if IS_WIN:
        schtasks("/Delete", "/F", "/TN", REMINDER_TASK)
        return
    launchctl("bootout", f"gui/{os.getuid()}/{REMINDER_LABEL}")
    if os.path.exists(REMINDER_PLIST):
        os.remove(REMINDER_PLIST)


def permission_hint(error):
    if IS_WIN:
        die(f"{error}\nWindows blocked writing into Vivaldi's folder. If Vivaldi is installed for all users "
            "(Program Files), run this from a terminal opened with 'Run as administrator'.")
    die(f"{error}\nmacOS blocked writing into Vivaldi.app. Open System Settings > Privacy & Security > "
        "App Management, allow your terminal app, then run the command again.")


# ---------------------------------------------------------------- commands
def cmd_install(args):
    app, data = args.app, args.data_dir
    resources = resources_dir(app)
    if not os.path.isdir(resources):
        die(f"Vivaldi not found at {app} (use --app)")
    if not args.dry_run:
        check_owner(HOME_DIR)
        ensure_vivaldi_closed()
        preflight(resources)
    profiles = find_profiles(read_json(os.path.join(data, "Local State")))
    say(f"Vivaldi {app_version(app)}; profiles: {', '.join(f'{n} ({d})' for d, n in profiles)}")
    if args.dry_run:
        say("dry run: nothing written")
        return

    state = load_state()
    backup = backup_dir()
    sync_guide()
    config_path = os.path.join(HOME_DIR, "config.json")
    if not os.path.exists(config_path):
        write_json(config_path, {})

    if not args.no_peek:
        try:
            fetch_peek()
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
        new, snap = patch_preferences(prefs, actions, reapply=directory in state["profiles"])
        state["profiles"].setdefault(directory, snap)
        write_json(prefs_path, new)
        say(f"  {name}: configured")

    state["version"] = VERSION
    save_state(state)

    try:
        apply_js(app, resources, not args.no_peek)
    except PermissionError as error:
        permission_hint(error)
    write_update_command(UPDATE_COMMAND, app, data)
    write_update_app(UPDATE_APP, UPDATE_COMMAND, scheme=UPDATE_SCHEME)
    write_uninstall_command(UNINSTALL_COMMAND, app, data)
    write_update_app(UNINSTALL_APP, UNINSTALL_COMMAND)
    remove_update_command(LEGACY_UPDATE_COMMAND)
    if IS_WIN:
        # Every Vivaldi update on Windows lands in a new folder without Vivarc: bring it back on its own.
        enable_reminder(app)
        say("Vivarc will re-apply itself after Vivaldi updates (scheduled task \"Vivarc\\Reapply\"). "
            f"Turn it off with: python \"{os.path.join(HERE, 'vivarc.py')}\" reminder off")
        say("Done. Open Vivaldi. \"Update Vivarc\" and \"Uninstall Vivarc\" are in the Start Menu.")
        return
    if os.path.exists(REMINDER_PLIST):
        enable_reminder(app)
    elif (ask("Show a reminder when a Vivaldi update removes Vivarc? [y/N] ") or "").lower() in ("y", "yes"):
        enable_reminder(app)
        say("Reminder on. Turn it off any time with: python3 ~/.vivarc/app/vivarc.py reminder off")
    say("Done. Open Vivaldi. After a Vivaldi update, open \"Update Vivarc\" to bring Vivarc back. Find it in Finder: "
        "Cmd+Shift+H, then the Applications folder. Drag it to your Dock to keep it close.")


def cmd_apply(args):
    resources = resources_dir(args.app)
    check_owner(HOME_DIR)
    preflight(resources)
    sync_guide()
    try:
        apply_js(args.app, resources, os.path.exists(os.path.join(HOME_DIR, "peek", "VividPeek.js")))
    except PermissionError as error:
        permission_hint(error)
    say(f"Re-applied to Vivaldi {app_version(args.app)}" + (". Restart Vivaldi to see it." if vivaldi_running() else ""))


def cmd_update(args):
    if vivaldi_running():
        say("Closing Vivaldi...")
        quit_vivaldi()
        if vivaldi_running():
            die(f"Vivaldi did not close. Quit it yourself ({QUIT_KEYS}), then run this again. Nothing was changed.")
    extra = ["--no-peek"] if args.no_peek else []
    if os.path.isdir(os.path.join(HERE, ".git")):
        try:
            pulled = subprocess.run(["git", "-C", HERE, "pull", "--ff-only"], capture_output=True, text=True)
        except FileNotFoundError:  # no git on PATH (common on Windows)
            pulled = subprocess.CompletedProcess([], 1, "", "git is not installed")
        if pulled.returncode == 0:
            argv = [sys.executable, os.path.join(HERE, "vivarc.py"), "--app", args.app, "--data-dir", args.data_dir, "install", *extra]
            run_instead(sys.executable, argv, os.environ)
        say(f"git pull did not work ({pulled.stderr.strip()}); re-applying the code you have.")
    else:
        latest = latest_release_tag()
        if is_newer(latest, VERSION):
            say(f"Updating Vivarc {VERSION} to {latest.lstrip('v')}...")
            env = {**os.environ, "VIVARC_APP": args.app, "VIVARC_DATA_DIR": args.data_dir}
            if IS_WIN:
                argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "install.ps1"), *extra]
            else:
                argv = ["/bin/bash", os.path.join(HERE, "install.sh"), *extra]
            run_instead(argv[0], argv, env)
        elif latest is None:
            say("Could not check for a new version (offline?). Re-applying the one you have.")
        else:
            say(f"Vivarc {VERSION} is up to date. Re-applying it.")
    cmd_install(args)


def run_instead(program, argv, env):
    """Hand over to another program for good. Windows has no real exec, so wait for it and pass on its exit code."""
    if IS_WIN:
        sys.exit(subprocess.run(argv, env=env).returncode)
    os.execve(shutil.which(program) or program, argv, env)


def reapply_silently(args, resources):
    """Windows: a Vivaldi update came with a fresh folder. Only Vivaldi's own UI files need Vivarc again (the profiles
    keep their settings), and those are safe to write while Vivaldi runs: it picks them up at the next start."""
    try:
        apply_js(args.app, resources, os.path.exists(os.path.join(HOME_DIR, "peek", "VividPeek.js")))
    except OSError:
        return False
    version = app_version(args.app)
    stamp = os.path.join(HOME_DIR, "reapplied")
    if not (os.path.exists(stamp) and read_text(stamp) == version):
        write_atomic(stamp, version)
        notify(f"Vivaldi was updated to {version}. Vivarc has been re-applied: restart Vivaldi to see it.")
    return True


def cmd_remind(args):
    resources = resources_dir(args.app)
    if IS_WIN and needs_reapply(resources) and reapply_silently(args, resources):
        return
    if needs_reapply(resources):
        stamp = os.path.join(HOME_DIR, "reminded")
        if os.path.exists(stamp) and time.time() - float(read_text(stamp)) < REMIND_EVERY:
            return
        value = str(time.time())
        message = "Vivaldi was updated and Vivarc is no longer active. Bring it back now? Vivaldi will close and reopen."
    else:
        latest = latest_release_tag()
        offered = os.path.join(HOME_DIR, "offered")
        if not is_newer(latest, VERSION) or (os.path.exists(offered) and read_text(offered) == latest):
            return
        os.makedirs(HOME_DIR, exist_ok=True)
        write_atomic(offered, latest)
        notify_quiet(f"Vivarc {latest.lstrip('v')} is available. Open Vivaldi's sidebar to update.")
        return
    os.makedirs(HOME_DIR, exist_ok=True)
    write_atomic(stamp, value)
    if prompt_update(message):
        if not os.path.exists(UPDATE_COMMAND):
            write_update_command(UPDATE_COMMAND, args.app, args.data_dir)
        open_in_terminal(UPDATE_COMMAND)


def cmd_reminder(args):
    if args.state == "on":
        enable_reminder(args.app)
        say("On: Vivarc re-applies itself after a Vivaldi update." if IS_WIN
            else "Reminder on: you will be asked when a Vivaldi update removes Vivarc.")
    else:
        disable_reminder()
        say("Reminder off.")


def cmd_uninstall(args):
    resources = resources_dir(args.app)
    ensure_vivaldi_closed()
    preflight(resources)
    state = load_state()
    for directory, snap in state["profiles"].items():
        prefs_path = os.path.join(args.data_dir, directory, "Preferences")
        if os.path.exists(prefs_path):
            write_json(prefs_path, restore_preferences(read_json(prefs_path), snap))
            say(f"  {directory}: restored")
    ls_path = os.path.join(args.data_dir, "Local State")
    if os.path.exists(ls_path):
        blank = {".".join(path): {"present": False, "value": None} for path in TOUCHED}
        for directory, _name in find_profiles(read_json(ls_path)):
            prefs_path = os.path.join(args.data_dir, directory, "Preferences")
            if directory in state["profiles"] or not os.path.exists(prefs_path):
                continue
            prefs = read_json(prefs_path)
            if looks_configured(prefs):
                write_json(prefs_path, restore_preferences(prefs, blank))  # set up by the JS later: defaults were the original
                say(f"  {directory}: reset to Vivaldi defaults (configured by Vivarc at runtime)")
    html_path = os.path.join(resources, "window.html")
    try:
        if os.path.exists(html_path):
            write_atomic(html_path, remove_window_html(read_text(html_path)))
        bundle = os.path.join(resources, "vivarc.js")
        if os.path.exists(bundle):
            os.remove(bundle)
    except PermissionError as error:
        permission_hint(error)
    remove_update_command(UPDATE_COMMAND)
    remove_update_command(LEGACY_UPDATE_COMMAND)
    remove_update_app(UPDATE_APP, scheme=UPDATE_SCHEME)
    remove_update_command(UNINSTALL_COMMAND)
    remove_update_app(UNINSTALL_APP)
    disable_reminder()
    if args.purge:
        shutil.rmtree(HOME_DIR, ignore_errors=True)
    say("Vivarc removed. Your bookmarks (including the Vivarc folder) were left alone.")


def cmd_status(args):
    resources = resources_dir(args.app)
    html_path = os.path.join(resources, "window.html")
    injected = os.path.exists(html_path) and BEGIN in read_text(html_path)
    say(f"Vivarc {VERSION}; Vivaldi {app_version(args.app)} (running: {vivaldi_running()})")
    say(f"JS injected: {injected}" + ("" if injected else "  -> run ./vivarc.py apply"))
    say(f"{'Re-apply after Vivaldi updates' if IS_WIN else 'Update reminder'}: {'on' if reminder_enabled() else 'off'}")
    state = load_state()
    for directory, name in find_profiles(read_json(os.path.join(args.data_dir, "Local State"))):
        path = os.path.join(args.data_dir, directory, "Preferences")
        ours = directory in state["profiles"] or (os.path.exists(path) and looks_configured(read_json(path)))
        say(f"  {name} ({directory}): {'configured' if ours else 'not configured yet (set up when opened)'}")


def default_arc_dir():
    if not IS_WIN:
        return os.path.join(HOME, "Library", "Application Support", "Arc")
    # Arc for Windows is a packaged (MSIX) app: its data sits in the package's private LocalCache.
    for package in sorted(glob.glob(os.path.join(LOCALAPPDATA, "Packages", "TheBrowserCompany.Arc*"))):
        candidate = os.path.join(package, "LocalCache", "Local", "Arc")
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(LOCALAPPDATA, "Packages", "TheBrowserCompany.Arc", "LocalCache", "Local", "Arc")


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
    install.add_argument("--no-peek", action="store_true")
    install.add_argument("--dry-run", action="store_true")
    sub.add_parser("apply")
    sub.add_parser("remind", help="ask to re-apply when Vivaldi has been updated (run by the reminder)")
    reminder = sub.add_parser("reminder", help="turn the update reminder on or off")
    reminder.add_argument("state", choices=["on", "off"])
    update = sub.add_parser("update")
    update.add_argument("--no-peek", action="store_true")
    update.set_defaults(dry_run=False)
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--purge", action="store_true", help="also delete ~/.vivarc")
    sub.add_parser("status")
    imp = sub.add_parser("import-arc")
    imp.add_argument("--arc-dir", default=default_arc_dir())
    args = parser.parse_args(argv)
    if IS_WIN:
        args.app = win_app_dir(args.app)
    if platform.system() not in ("Darwin", "Windows"):
        die("Vivarc supports macOS and Windows only")
    check_not_root()
    {"install": cmd_install, "apply": cmd_apply, "update": cmd_update, "remind": cmd_remind, "reminder": cmd_reminder, "uninstall": cmd_uninstall,
     "status": cmd_status, "import-arc": cmd_import_arc}[args.command](args)


if __name__ == "__main__":
    main()
