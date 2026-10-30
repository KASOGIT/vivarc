import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import windows_support as win


class WindowsSupport(unittest.TestCase):
    def test_versioned_resources_are_sorted_numerically(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version in ('8.9.1', '8.10.1'):
                resources = Path(tmp, version, 'resources', 'vivaldi')
                resources.mkdir(parents=True)
                (resources / 'window.html').write_text('<body></body>')
            self.assertIn('8.10.1', win.find_resources(tmp))
            self.assertEqual(win.find_resources(tmp), win.find_resources(str(Path(tmp, 'vivaldi.exe'))))

    def test_tasklist_checks_image_name_not_substrings(self):
        with mock.patch.object(win.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '"vivaldi.exe","123","Console","1","1 K"\n')):
            self.assertTrue(win.running())
        with mock.patch.object(win.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'INFO: No tasks are running\n')):
            self.assertFalse(win.running())

    def test_install_reapply_and_uninstall_restore_preferences(self):
        # Load a private copy so adapter bindings cannot leak to the macOS tests.
        spec = importlib.util.spec_from_file_location('vivarc_windows_test', Path(__file__).parents[1] / 'vivarc.py')
        v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / 'Vivaldi app'
            resources = app / '8.10.1' / 'resources' / 'vivaldi'
            resources.mkdir(parents=True)
            html = '<html><body></body></html>'
            (resources / 'window.html').write_text(html)
            actions = [{'COMMAND_NEW_TAB': {'shortcuts': ['ctrl+t']}, 'COMMAND_SAVE_PAGE': {'shortcuts': ['ctrl+s']}}]
            (resources / 'prefs_definitions.json').write_text(json.dumps({'vivaldi': {'actions': {'default': actions}}}))
            data = root / 'User Data'
            (data / 'Default').mkdir(parents=True)
            (data / 'Local State').write_text('{}')
            original = {'vivaldi': {'actions': actions}}
            prefs = data / 'Default' / 'Preferences'
            prefs.write_text(json.dumps(original))
            v.IS_WINDOWS = True
            v.HOME_DIR = str(root / 'vivarc home')
            v.UPDATE_COMMAND = str(root / 'vivarc home' / 'Update Vivarc.bat')
            v.UNINSTALL_COMMAND = str(root / 'vivarc home' / 'Uninstall Vivarc.bat')
            v.LEGACY_UPDATE_COMMAND = str(root / 'missing.command')
            args = argparse.Namespace(app=str(app), data_dir=str(data), no_peek=True, dry_run=False, purge=False)
            win.configure(v, args)
            with mock.patch.object(v, 'ensure_vivaldi_closed'), mock.patch.object(v.platform, 'system', return_value='Windows'):
                v.cmd_install(args)
                patched = json.loads(prefs.read_text())
                self.assertEqual(patched['vivaldi']['actions'][0]['COMMAND_NEW_TAB']['shortcuts'], [])
                self.assertIn(v.BEGIN, (resources / 'window.html').read_text())
                self.assertIn('"platform": "Windows"', (resources / 'vivarc.js').read_text(encoding='utf8'))
                launcher = Path(v.UPDATE_COMMAND).read_text(encoding='utf8')
                self.assertIn('"' + str(data) + '"', launcher)
                self.assertIn('"' + str(app) + '"', launcher)
                v.cmd_install(args)
                v.cmd_uninstall(args)
                self.assertEqual(json.loads(prefs.read_text()), original)
                self.assertNotIn(v.BEGIN, (resources / 'window.html').read_text())
                self.assertFalse((resources / 'vivarc.js').exists())
                self.assertFalse(Path(v.UPDATE_COMMAND).exists())
                self.assertFalse(Path(v.UNINSTALL_COMMAND).exists())

    def test_release_update_uses_batch_and_preserves_paths(self):
        args = argparse.Namespace(app='D:\\Vivaldi', data_dir='D:\\Profile')
        with mock.patch.object(win.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            win.update_release(args, ['--no-peek'])
            self.assertIn('install.bat', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['env']['VIVARC_DATA_DIR'], args.data_dir)
            self.assertIn('--no-peek', run.call_args.args[0])

    def test_windows_javascript_shortcuts_match_installer(self):
        source = (Path(__file__).parents[1] / 'src/js/00-core.js').read_text(encoding='utf8')
        mapping = source[source.index('  const windows ='):source.index('  const subscribers =')]
        script = ('const config = {platform: "Windows"};' + mapping
                  + 'console.log(JSON.stringify(["meta+t", "meta+s", "shift+meta+c", "ctrl+meta+left", "ctrl+meta+n", "alt+meta+left"].map(shortcut)));')
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, encoding='utf8', check=True)
        self.assertEqual(json.loads(result.stdout), ['ctrl+t', 'ctrl+s', 'shift+ctrl+c', 'ctrl+shift+left', 'alt+ctrl+n', 'alt+left'])

    @unittest.skipUnless(os.name == 'nt', 'requires Windows cmd.exe')
    def test_batch_installer_downloads_local_archive_and_passes_arguments(self):
        import shutil
        import sys
        import zipfile
        with tempfile.TemporaryDirectory(prefix='vivarc batch ') as temporary:
            root = Path(temporary)
            batch = root / 'installer & files' / 'install.bat'
            batch.parent.mkdir()
            shutil.copy2(Path(__file__).parents[1] / 'install.bat', batch)
            archive = root / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('release/vivarc.py', 'import json,sys; from pathlib import Path; Path(__file__).with_name("called.json").write_text(json.dumps(sys.argv[1:]))')
                package.writestr('release/windows_support.py', '')
                package.writestr('release/install.bat', batch.read_text(encoding='utf8'))
            home = root / 'user home'
            env = {**os.environ, 'USERPROFILE': str(home), 'VIVARC_PYTHON': sys.executable, 'VIVARC_ZIP_URL': archive.as_uri()}
            comspec = os.environ.get('COMSPEC', 'cmd.exe')
            command = f'"{comspec}" /d /s /c ""{batch}" --no-peek"'
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((home / '.vivarc/app/called.json').read_text()), ['install', '--no-peek'])
            self.assertTrue((home / '.vivarc/app/install.bat').is_file())
