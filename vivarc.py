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
import hashlib
import json
import os
import pathlib
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request

VERSION = "0.1.16"
HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.join(HOME, ".vivarc")
IS_WINDOWS = platform.system() == "Windows"
DEFAULT_APP = os.environ.get("VIVARC_APP", "/Applications/Vivaldi.app")
DEFAULT_DATA = os.environ.get("VIVARC_DATA_DIR", os.path.join(HOME, "Library", "Application Support", "Vivaldi"))
UPDATE_COMMAND = os.path.join(HOME_DIR, "Update Vivarc.command")
UPDATE_APP = os.path.join(HOME, "Applications", "Update Vivarc.app")
LEGACY_UPDATE_COMMAND = os.path.join(HOME, "Applications", "Update Vivarc.command")
UNINSTALL_COMMAND = os.path.join(HOME_DIR, "Uninstall Vivarc.command")
UNINSTALL_APP = os.path.join(HOME, "Applications", "Uninstall Vivarc.app")
UPDATE_MARK = "# Created by Vivarc"
RELEASES_LATEST = "https://github.com/KASOGIT/vivarc/releases/latest"
REMINDER_LABEL = "com.vivarc.reminder"
REMINDER_PLIST = os.path.join(HOME, "Library", "LaunchAgents", f"{REMINDER_LABEL}.plist")
REMIND_EVERY = 12 * 3600
RESOURCES = "Contents/Frameworks/Vivaldi Framework.framework/Resources/vivaldi"


def resource_dir(app):
    if IS_WINDOWS:
        from windows_support import find_resources
        return find_resources(app)
    return os.path.join(app, RESOURCES)


if IS_WINDOWS:
    from windows_support import detect_app
    DEFAULT_APP = os.environ.get("VIVARC_APP", detect_app())
    DEFAULT_DATA = os.environ.get("VIVARC_DATA_DIR", os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Vivaldi", "User Data"))
    UPDATE_COMMAND = os.path.join(HOME_DIR, "Update Vivarc.bat")
    UNINSTALL_COMMAND = os.path.join(HOME_DIR, "Uninstall Vivarc.bat")

BEGIN, END = "<!-- vivarc:begin -->", "<!-- vivarc:end -->"
BLOCK = f'{BEGIN}\n<script src="vivarc.js"></script>\n{END}'
FREED_KEY = "meta+t"  # the command bar listens for Cmd+T itself
COPY_URL_KEY = "shift+meta+c"
PROFILE_KEYS = ("ctrl+meta+left", "ctrl+meta+right")  # the profile switcher's previous/next, handled by the JS
SPACE_KEYS = {"COMMAND_WORKSPACE_SWITCH_BACK_ORDER": "alt+meta+left", "COMMAND_WORKSPACE_SWITCH_FORWARD_ORDER": "alt+meta+right",
              "COMMAND_WORKSPACE_CREATE_NEW": "ctrl+meta+n"}  # like Arc's spaces; Ctrl+Cmd+N opens Vivaldi's own Create Workspace dialog
TOGGLE_SIDEBAR_KEY = "meta+s"
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


def patch_preferences(prefs, default_actions):
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
    taken = PROFILE_KEYS + tuple(SPACE_KEYS.values())
    for name, cmd in defaults.items():
        if any(key in cmd.get("shortcuts", []) for key in taken):
            _command(actions, defaults, name)
    for cmd in actions.values():
        if isinstance(cmd, dict):
            cmd["shortcuts"] = [s for s in cmd.get("shortcuts", []) if s != TOGGLE_SIDEBAR_KEY and s not in taken]
    for name, key in SPACE_KEYS.items():
        cmd = _command(actions, defaults, name)
        cmd["shortcuts"] = [s for s in cmd["shortcuts"] if s not in ("meta+left", "meta+right", "alt+meta+left", "alt+meta+right", "alt+ctrl+left", "alt+ctrl+right")]
        cmd["shortcuts"].append(key)
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


SETTINGS_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_AppBundles"


def ask(prompt):
    """Read an answer from the terminal even when stdin is a pipe; None when there is no terminal."""
    try:
        with open("/dev/tty", "w") as out, open("/dev/tty") as tty:
            out.write(prompt)
            out.flush()
            return tty.readline().strip()
    except OSError:
        return None


def open_settings():
    subprocess.run(["open", SETTINGS_PANE], check=False)


def quit_vivaldi():
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
    if os.geteuid() == 0:
        die("Do not run Vivarc with sudo. It does not help (macOS asks for a separate permission, see below) "
            "and it leaves files in your home folder that only root can change.\n"
            "Run the same command without sudo. If macOS blocks it, allow your terminal under "
            "System Settings > Privacy & Security > App Management.")


def check_owner(path):
    if os.path.exists(path) and os.stat(path).st_uid != os.getuid():
        die(f"{path} belongs to another user, probably from an earlier run with sudo. Fix it with:\n"
            f"  sudo chown -R \"$(whoami)\" \"{path}\"\nthen run the command again (without sudo).")


def ensure_vivaldi_closed(ask=ask, quit_app=quit_vivaldi):
    if not vivaldi_running():
        return
    answer = ask("Vivaldi is open and must be closed first. Quit it now? [Y/n] ")
    if answer is None:
        die("Quit Vivaldi (Cmd+Q) first, then run this again. Nothing was changed.")
    if answer.lower() in ("", "y", "yes"):
        quit_app()
        if not vivaldi_running():
            return
        die("Vivaldi did not close. Quit it yourself (Cmd+Q), then run this again. Nothing was changed.")
    die("Vivaldi has to be closed first. Nothing was changed.")


def preflight(resources, ask=ask, open_settings=open_settings):
    """macOS only lets an app with the 'App Management' permission edit Vivaldi.app. Check before changing anything."""
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
    with open(temp, "w", encoding="utf8") as f:
        f.write(text)
    os.replace(temp, path)


def load_state():
    path = os.path.join(HOME_DIR, "state.json")
    return read_json(path) if os.path.exists(path) else {"profiles": {}, "version": VERSION}


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
    if with_peek and os.path.exists(os.path.join(peek_dir, "VividPeek.js")):
        extras.append(("peek-stubs.js", read_text(os.path.join(HERE, "src/optional/peek-stubs.js"))))
        extras.append(("VividPeek.js", read_text(os.path.join(peek_dir, "VividPeek.js"))))
        extras.append(("VividPeek.css", style_script("vivarc-peek-css", read_text(os.path.join(peek_dir, "VividPeek.css")))))
    start_page = pathlib.Path(HOME_DIR, "start", "index.html").as_uri()
    config = {**load_config(), "startUrl": start_page, "platform": platform.system()}
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


def write_command(path, purpose, subcommand):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    script = ("#!/bin/bash\n"
              f"{UPDATE_MARK}: {purpose}.\n"
              f"/usr/bin/python3 {shlex.quote(os.path.join(HERE, 'vivarc.py'))} {subcommand}\n"
              "status=$?\n"
              "open -a Vivaldi\n"
              "exit $status\n")
    write_atomic(path, script)
    os.chmod(path, 0o755)


def write_update_command(path):
    write_command(path, "updates Vivarc and brings it back after a Vivaldi update", "update")


def write_uninstall_command(path):
    write_command(path, "removes Vivarc and puts Vivaldi back as it was", "uninstall")


def write_update_app(app, command):
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.dirname(app), exist_ok=True)
    script = f'do shell script "open -a Terminal " & quoted form of {json.dumps(command, ensure_ascii=False)} & " {UPDATE_MARK}"'
    subprocess.run(["osacompile", "-o", app, "-e", script], check=True, capture_output=True)


def remove_update_app(app):
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


def prompt_update(message):
    script = (f'display dialog "{message}" with title "Vivarc" buttons {{"Later", "Update Vivarc"}} '
              'default button "Update Vivarc" giving up after 300')
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return "button returned:Update Vivarc" in out.stdout


def open_in_terminal(path):
    subprocess.run(["open", "-a", "Terminal", path], check=False)


def launchctl(*args):
    subprocess.run(["launchctl", *args], capture_output=True, check=False)


def enable_reminder(app):
    for folder in ("Documents", "Desktop", "Downloads"):
        if HERE.startswith(os.path.join(HOME, folder) + os.sep):
            say(f"Note: macOS does not let background jobs read ~/{folder}, so the reminder cannot run from this copy. "
                "Use the copy the one-line install puts in ~/.vivarc/app.")
    agent = {
        "Label": REMINDER_LABEL,
        "ProgramArguments": ["/usr/bin/python3", os.path.join(HERE, "vivarc.py"), "--app", app, "remind"],
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
    launchctl("bootout", f"gui/{os.getuid()}/{REMINDER_LABEL}")
    if os.path.exists(REMINDER_PLIST):
        os.remove(REMINDER_PLIST)


def permission_hint(error):
    die(f"{error}\nmacOS blocked writing into Vivaldi.app. Open System Settings > Privacy & Security > "
        "App Management, allow your terminal app, then run the command again.")


# ---------------------------------------------------------------- commands
def cmd_install(args):
    app, data = args.app, args.data_dir
    resources = resource_dir(app)
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
        new, snap = patch_preferences(prefs, actions)
        state["profiles"].setdefault(directory, snap)
        write_json(prefs_path, new)
        say(f"  {name}: configured")

    state["version"] = VERSION
    save_state(state)

    try:
        apply_js(app, resources, not args.no_peek)
    except PermissionError as error:
        permission_hint(error)
    write_update_command(UPDATE_COMMAND)
    if not IS_WINDOWS:
        write_update_app(UPDATE_APP, UPDATE_COMMAND)
    write_uninstall_command(UNINSTALL_COMMAND)
    if not IS_WINDOWS:
        write_update_app(UNINSTALL_APP, UNINSTALL_COMMAND)
    remove_update_command(LEGACY_UPDATE_COMMAND)
    if IS_WINDOWS:
        say("Automatic reminders are not available on Windows.")
    elif os.path.exists(REMINDER_PLIST):
        enable_reminder(app)
    elif (ask("Show a reminder when a Vivaldi update removes Vivarc? [y/N] ") or "").lower() in ("y", "yes"):
        enable_reminder(app)
        say("Reminder on. Turn it off any time with: python3 ~/.vivarc/app/vivarc.py reminder off")
    if IS_WINDOWS:
        say(f"Done. Open Vivaldi. Update and uninstall launchers: {HOME_DIR}")
        return
    say("Done. Open Vivaldi. After a Vivaldi update, open \"Update Vivarc\" to bring Vivarc back. Find it in Finder: "
        "Cmd+Shift+H, then the Applications folder. Drag it to your Dock to keep it close.")


def cmd_apply(args):
    resources = resource_dir(args.app)
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
            die("Vivaldi did not close. Quit it yourself (Cmd+Q), then run this again. Nothing was changed.")
    extra = ["--no-peek"] if args.no_peek else []
    if os.path.isdir(os.path.join(HERE, ".git")):
        pulled = subprocess.run(["git", "-C", HERE, "pull", "--ff-only"], capture_output=True, text=True)
        if pulled.returncode == 0:
            argv = [sys.executable, os.path.join(HERE, "vivarc.py"), "--app", args.app, "--data-dir", args.data_dir, "install", *extra]
            os.execve(sys.executable, argv, os.environ)
        say(f"git pull did not work ({pulled.stderr.strip()}); re-applying the code you have.")
    else:
        latest = latest_release_tag()
        if is_newer(latest, VERSION):
            say(f"Updating Vivarc {VERSION} to {latest.lstrip('v')}...")
            env = {**os.environ, "VIVARC_APP": args.app, "VIVARC_DATA_DIR": args.data_dir}
            if IS_WINDOWS:
                import windows_support
                windows_support.update_release(args, extra)
                return
            os.execve("/bin/bash", ["/bin/bash", os.path.join(HERE, "install.sh"), *extra], env)
        elif latest is None:
            say("Could not check for a new version (offline?). Re-applying the one you have.")
        else:
            say(f"Vivarc {VERSION} is up to date. Re-applying it.")
    cmd_install(args)


def cmd_remind(args):
    resources = resource_dir(args.app)
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
        stamp, value = offered, latest
        message = f"Vivarc {latest.lstrip('v')} is available. Update now? Vivaldi will close and reopen."
    os.makedirs(HOME_DIR, exist_ok=True)
    write_atomic(stamp, value)
    if prompt_update(message):
        if not os.path.exists(UPDATE_COMMAND):
            write_update_command(UPDATE_COMMAND)
        open_in_terminal(UPDATE_COMMAND)


def cmd_reminder(args):
    if args.state == "on":
        enable_reminder(args.app)
        say("Reminder on: you will be asked when a Vivaldi update removes Vivarc.")
    else:
        disable_reminder()
        say("Reminder off.")


def cmd_uninstall(args):
    resources = resource_dir(args.app)
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
            html = read_text(html_path)
            with open(html_path, "w", encoding="utf8") as f:
                f.write(remove_window_html(html))
        bundle = os.path.join(resources, "vivarc.js")
        if os.path.exists(bundle):
            os.remove(bundle)
    except PermissionError as error:
        permission_hint(error)
    remove_update_command(UPDATE_COMMAND)
    remove_update_command(LEGACY_UPDATE_COMMAND)
    if not IS_WINDOWS:
        remove_update_app(UPDATE_APP)
    remove_update_command(UNINSTALL_COMMAND)
    if not IS_WINDOWS:
        remove_update_app(UNINSTALL_APP)
    disable_reminder()
    if args.purge:
        shutil.rmtree(HOME_DIR, ignore_errors=True)
    say("Vivarc removed. Your bookmarks (including the Vivarc folder) were left alone.")


def cmd_status(args):
    resources = resource_dir(args.app)
    html_path = os.path.join(resources, "window.html")
    injected = os.path.exists(html_path) and BEGIN in read_text(html_path)
    say(f"Vivarc {VERSION}; Vivaldi {app_version(args.app)} (running: {vivaldi_running()})")
    say(f"JS injected: {injected}" + ("" if injected else "  -> run ./vivarc.py apply"))
    say("Update reminder: unavailable on Windows" if IS_WINDOWS else f"Update reminder: {'on' if os.path.exists(REMINDER_PLIST) else 'off'}")
    state = load_state()
    for directory, name in find_profiles(read_json(os.path.join(args.data_dir, "Local State"))):
        path = os.path.join(args.data_dir, directory, "Preferences")
        ours = directory in state["profiles"] or (os.path.exists(path) and looks_configured(read_json(path)))
        say(f"  {name} ({directory}): {'configured' if ours else 'not configured yet (set up when opened)'}")


def cmd_import_arc(args):
    if IS_WINDOWS and not os.path.isfile(os.path.join(args.arc_dir, "StorableSidebar.json")):
        die("Arc Windows import is not supported yet. Use --arc-dir with an exported macOS Arc folder containing StorableSidebar.json.")
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
    imp.add_argument("--arc-dir", default=os.path.join(HOME, "Library", "Application Support", "Arc"))
    args = parser.parse_args(argv)
    if platform.system() not in ("Darwin", "Windows"):
        die("Vivarc supports macOS and Windows")
    if IS_WINDOWS:
        import windows_support
        windows_support.configure(sys.modules[__name__], args)
    check_not_root()
    {"install": cmd_install, "apply": cmd_apply, "update": cmd_update, "remind": cmd_remind, "reminder": cmd_reminder, "uninstall": cmd_uninstall,
     "status": cmd_status, "import-arc": cmd_import_arc}[args.command](args)


if __name__ == "__main__":
    main()
