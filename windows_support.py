"""Windows adapters for Vivarc. No third-party Python dependencies."""
import csv
import io
import os
from pathlib import Path
import subprocess
import sys
import time


def detect_app():
    roots = [os.environ.get(key, '') for key in ('LOCALAPPDATA', 'ProgramFiles', 'ProgramFiles(x86)')]
    for root in roots:
        app = Path(root) / 'Vivaldi' / 'Application'
        if (app / 'vivaldi.exe').is_file():
            return str(app)
    return str(Path(roots[0]) / 'Vivaldi' / 'Application')


def find_resources(app):
    root = Path(app)
    if root.suffix.lower() == '.exe':
        root = root.parent
    candidates = [root / 'resources' / 'vivaldi']
    versions = []
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and all(p.isdigit() for p in child.name.split('.')):
                versions.append(child)
    versions.sort(key=lambda p: tuple(map(int, p.name.split('.'))), reverse=True)
    candidates += [v / 'resources' / 'vivaldi' for v in versions]
    for candidate in candidates:
        if (candidate / 'window.html').is_file():
            return str(candidate)
    return str(candidates[0])


def running():
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq vivaldi.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True, check=True)
    return any(row and row[0].lower() == 'vivaldi.exe' for row in csv.reader(io.StringIO(result.stdout)))


def quit_vivaldi():
    # CloseMainWindow requests a normal shutdown; never force-kill profile writers.
    subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                    "Get-Process vivaldi -ErrorAction SilentlyContinue | Where-Object MainWindowHandle -ne 0 | ForEach-Object { [void]$_.CloseMainWindow() }"], check=True)
    for _ in range(40):
        if not running():
            return
        time.sleep(.5)


def update_release(args, extra):
    env = {**os.environ, 'VIVARC_APP': args.app, 'VIVARC_DATA_DIR': args.data_dir,
           'VIVARC_PYTHON': sys.executable}
    command = str(Path(__file__).with_name('install.bat'))
    comspec = os.environ.get('COMSPEC', 'cmd.exe')
    argv = subprocess.list2cmdline(extra)
    result = subprocess.run(f'"{comspec}" /d /s /c ""{command}" {argv}"', env=env)
    if result.returncode:
        raise SystemExit(result.returncode)


def configure(v, args=None):
    app = args.app if args else v.DEFAULT_APP
    data = args.data_dir if args else v.DEFAULT_DATA
    def ask(prompt):
        try:
            return input(prompt)
        except (EOFError, OSError):
            return None

    def preflight(resources, **kwargs):
        if not v.can_write(resources):
            v.die('Cannot write to ' + resources + '. For a system installation, run this terminal as administrator, keeping --data-dir pointed at your own Vivaldi profile.')

    def version(app):
        parent = Path(find_resources(app)).parent.parent
        return parent.name if all(p.isdigit() for p in parent.name.split('.')) else 'unknown'

    def write_command(path, purpose, subcommand):
        # Batch expands percent signs even inside quoted arguments.
        def quoted(value):
            return '"' + str(value).replace('%', '%%') + '"'
        exe = Path(app)
        if exe.suffix.lower() != '.exe':
            exe /= 'vivaldi.exe'
        script = ('@echo off\nchcp 65001 >nul\nsetlocal DisableDelayedExpansion\nrem ' + v.UPDATE_MARK + ': ' + purpose + '\n'
                  + quoted(sys.executable) + ' ' + quoted(Path(v.HERE) / 'vivarc.py')
                  + ' --app ' + quoted(app) + ' --data-dir ' + quoted(data)
                  + ' ' + subcommand + '\nset "vivarc_status=%errorlevel%"\n'
                  + 'if not "%vivarc_status%"=="0" (\n pause\n exit /b %vivarc_status%\n)\n'
                  + 'start "" ' + quoted(exe) + '\nexit /b 0\n')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        v.write_atomic(path, script)

    v.ask = ask
    # Existing default arguments capture the macOS functions at definition time.
    original_closed = getattr(v, "_windows_original_closed", v.ensure_vivaldi_closed)
    v._windows_original_closed = original_closed
    v.ensure_vivaldi_closed = lambda: original_closed(ask=ask, quit_app=quit_vivaldi)
    v.vivaldi_running = running
    v.quit_vivaldi = quit_vivaldi
    v.app_version = version
    v.check_not_root = lambda: None
    v.check_owner = lambda path: None
    v.preflight = preflight
    v.permission_hint = lambda error: v.die(str(error) + '\nCheck Windows permissions on the Vivaldi installation directory.')
    v.write_command = write_command
    v.disable_reminder = lambda: None
    v.cmd_reminder = lambda args: v.die('Automatic reminders are not available on Windows.')
    v.cmd_remind = lambda args: None
    v.FREED_KEY = 'ctrl+t'
    v.COPY_URL_KEY = 'shift+ctrl+c'
    v.TOGGLE_SIDEBAR_KEY = 'ctrl+s'
    v.PROFILE_KEYS = ('ctrl+shift+left', 'ctrl+shift+right')
    v.SPACE_KEYS = {'COMMAND_WORKSPACE_SWITCH_BACK_ORDER': 'alt+left',
                    'COMMAND_WORKSPACE_SWITCH_FORWARD_ORDER': 'alt+right',
                    'COMMAND_WORKSPACE_CREATE_NEW': 'alt+ctrl+n'}
