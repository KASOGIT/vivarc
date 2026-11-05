"""Windows support. Most of it is plain logic and runs on any OS with IS_WIN switched on; the rest needs Windows."""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402
from platforms import use_keys, windows_only  # noqa: E402

WIN_DEFAULTS = {  # an excerpt of Vivaldi 8.3's "default" (Windows) actions
    "COMMAND_NEW_TAB": {"shortcuts": ["ctrl+t"]},
    "COMMAND_SHOW_QUICK_COMMANDS": {"shortcuts": ["ctrl+e", "f2"]},
    "COMMAND_SAVE_PAGE": {"shortcuts": ["ctrl+s"]},
    "COMMAND_COPY_SELECTION_TO_NOTE": {"shortcuts": ["ctrl+shift+c"]},
    "COMMAND_PAGE_COPY_URL": {"shortcuts": []},
    "COMMAND_PAGE_BACK": {"shortcuts": ["alt+left", "ctrl+left", "backspace", "z"]},
    "COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR": {"shortcuts": []},
}


class WinCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch.object(vivarc, "IS_WIN", True)
        p.start()
        self.addCleanup(p.stop)

    def version(self, app, name, ui=True):
        res = os.path.join(app, name, "resources", "vivaldi")
        os.makedirs(res)
        if ui:
            with open(os.path.join(res, "window.html"), "w", encoding="utf8") as f:
                f.write("<html><body>\n</body></html>\n")
        return res


class VersionFolders(WinCase):
    def test_the_newest_version_folder_with_vivaldis_ui_is_the_one_in_use(self):
        app = os.path.join(self.tmp, "Application")
        self.version(app, "8.3.4191.26")
        newest = self.version(app, "8.10.0.1")  # numeric, not alphabetical
        self.version(app, "9.0.0.0", ui=False)  # an update still unpacking
        os.makedirs(os.path.join(app, "SetupMetrics"))
        self.assertEqual(vivarc.win_version_dir(app), "8.10.0.1")
        self.assertEqual(vivarc.resources_dir(app), newest)
        self.assertEqual(vivarc.app_version(app), "8.10.0.1")

    def test_no_vivaldi_gives_a_path_that_does_not_exist(self):
        self.assertIsNone(vivarc.win_version_dir(os.path.join(self.tmp, "nowhere")))
        self.assertFalse(os.path.isdir(vivarc.resources_dir(os.path.join(self.tmp, "nowhere"))))
        self.assertEqual(vivarc.app_version(os.path.join(self.tmp, "nowhere")), "unknown")

    def test_a_standalone_vivaldi_without_version_folders_is_found(self):
        app = os.path.join(self.tmp, "Application")
        flat = os.path.join(app, "resources", "vivaldi")
        os.makedirs(flat)
        with open(os.path.join(flat, "window.html"), "w", encoding="utf8") as f:
            f.write("<html></html>")
        self.assertEqual(vivarc.resources_dir(app), flat)

    def test_a_version_folder_wins_over_a_flat_resources_folder(self):
        app = os.path.join(self.tmp, "Application")
        versioned = self.version(app, "8.3.4191.26")
        os.makedirs(os.path.join(app, "resources", "vivaldi"))
        self.assertEqual(vivarc.resources_dir(app), versioned)

    def test_the_app_can_be_given_as_the_vivaldi_exe(self):
        self.assertEqual(vivarc.win_app_dir(os.path.join("D:\\", "V", "Application", "vivaldi.exe")),
                         os.path.join("D:\\", "V", "Application"))
        self.assertEqual(vivarc.win_app_dir(os.path.join("D:\\", "V", "Application", "VIVALDI.EXE")),
                         os.path.join("D:\\", "V", "Application"))
        self.assertEqual(vivarc.win_app_dir(os.path.join("D:\\", "V", "Application")), os.path.join("D:\\", "V", "Application"))


class Running(unittest.TestCase):
    def test_reads_tasklists_answer(self):
        self.assertTrue(vivarc._tasklist_has_vivaldi("\nvivaldi.exe                  21796 Console                    1    245,312 K\n"))
        self.assertFalse(vivarc._tasklist_has_vivaldi("INFO: No tasks are running which match the specified criteria.\n"))
        self.assertFalse(vivarc._tasklist_has_vivaldi("vivaldi_proxy.exe 1 Console 1 1 K\n"))


class WindowsKeys(unittest.TestCase):
    def setUp(self):
        use_keys(self, "win")
        new, _ = vivarc.patch_preferences({}, [WIN_DEFAULTS])
        self.new = new
        self.actions = new["vivaldi"]["actions"][0]

    def test_ctrl_t_is_freed_for_the_command_bar(self):
        self.assertEqual(self.actions["COMMAND_NEW_TAB"]["shortcuts"], [])
        self.assertEqual(self.actions["COMMAND_SHOW_QUICK_COMMANDS"]["shortcuts"], ["ctrl+e", "f2"])

    def test_ctrl_shift_c_moves_from_copy_to_note_to_copy_url(self):
        self.assertEqual(self.actions["COMMAND_PAGE_COPY_URL"]["shortcuts"], ["ctrl+shift+c"])
        self.assertEqual(self.actions["COMMAND_COPY_SELECTION_TO_NOTE"]["shortcuts"], [])

    def test_ctrl_s_toggles_the_sidebar_instead_of_saving(self):
        self.assertEqual(self.actions["COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR"]["shortcuts"], ["ctrl+s"])
        self.assertEqual(self.actions["COMMAND_SAVE_PAGE"]["shortcuts"], [])

    def test_ctrl_alt_arrows_switch_spaces_and_back_keeps_its_own_keys(self):
        self.assertEqual(self.actions["COMMAND_WORKSPACE_SWITCH_BACK_ORDER"]["shortcuts"], ["ctrl+alt+left"])
        self.assertEqual(self.actions["COMMAND_WORKSPACE_SWITCH_FORWARD_ORDER"]["shortcuts"], ["ctrl+alt+right"])
        self.assertEqual(self.actions["COMMAND_WORKSPACE_CREATE_NEW"]["shortcuts"], ["ctrl+alt+n"])
        self.assertEqual(self.actions["COMMAND_PAGE_BACK"]["shortcuts"], ["alt+left", "ctrl+left", "backspace", "z"])

    def test_a_profile_set_up_like_this_is_recognised_and_no_win_key_is_used(self):
        self.assertTrue(vivarc.looks_configured(self.new))
        self.assertFalse(any("meta" in key for key in vivarc.KEYS["win"].values()))

    def test_the_js_fallback_table_matches_the_installers(self):
        if not shutil.which("node"):
            self.skipTest("node is needed")
        with open(os.path.join(vivarc.HERE, "src", "js", "00-core.js"), encoding="utf8") as f:
            literal = re.search(r"const KEYMAPS = (\{.*?\n  \});", f.read(), re.S).group(1)
        out = subprocess.run(["node", "-e", "console.log(JSON.stringify(eval('(' + process.argv[1] + ')')))", literal],
                             capture_output=True, encoding="utf8", check=True).stdout
        self.assertEqual(json.loads(out), vivarc.KEYS)


class Launchers(WinCase):
    def script(self, here, app, python=r"C:\Py\python.exe", data=r"C:\D"):
        with mock.patch.object(vivarc, "HERE", here):
            # os.path.join joins with "/" off Windows; the launcher is judged as cmd.exe would read it
            script = vivarc.command_script("updates Vivarc", "update", app=app, python=python, data=data)
        return re.sub(r"(?<=[\w%])/(?=\w)", lambda _: "\\", script)

    def test_the_cmd_runs_update_with_python_then_reopens_vivaldi(self):
        script = self.script(r"C:\Users\some one\.vivarc\app", r"C:\Users\some one\AppData\Local\Vivaldi\Application")
        self.assertTrue(script.startswith("@echo off\r\n"))
        self.assertIn(vivarc.UPDATE_MARK, script)
        self.assertIn(r'"C:\Py\python.exe" "C:\Users\some one\.vivarc\app\vivarc.py" --app "C:\Users\some one\AppData\Local\Vivaldi\Application" '
                      r'--data-dir "C:\D" update', script)
        self.assertIn(r'start "" "C:\Users\some one\AppData\Local\Vivaldi\Application\vivaldi.exe"', script)
        self.assertTrue(script.rstrip().endswith("exit /b %status%"))
        self.assertNotIn("\n", script.replace("\r\n", ""))  # CRLF throughout: cmd.exe misreads bare LF

    def test_percent_signs_in_paths_are_escaped(self):
        script = self.script(r"C:\100%", r"C:\V%", data=r"C:\D%")
        self.assertIn(r'"C:\100%%\vivarc.py"', script)
        self.assertIn(r'--app "C:\V%%"', script)
        self.assertIn(r'--data-dir "C:\D%%"', script)

    def test_a_custom_vivaldi_location_survives_the_launcher(self):
        script = self.script(r"C:\H", r"D:\Portable Vivaldi\Application", data=r"D:\Portable Vivaldi\User Data")
        self.assertIn(r'--app "D:\Portable Vivaldi\Application" --data-dir "D:\Portable Vivaldi\User Data" update', script)

    def test_the_console_switches_to_utf8_before_any_path_is_read(self):
        lines = self.script(r"C:\Users\Zoë\.vivarc\app", r"C:\V").split("\r\n")
        self.assertEqual(lines[:2], ["@echo off", "chcp 65001 >nul"])

    def test_the_console_python_is_used_even_from_the_windowless_task(self):
        folder = os.path.join(self.tmp, "py")
        os.makedirs(folder)
        for name in ("python.exe", "pythonw.exe"):
            open(os.path.join(folder, name), "w").close()
        with mock.patch.object(sys, "executable", os.path.join(folder, "pythonw.exe")):
            self.assertEqual(vivarc.console_python(), os.path.join(folder, "python.exe"))
        with mock.patch.object(sys, "executable", os.path.join(folder, "python.exe")):
            self.assertEqual(vivarc.windowless_python(), os.path.join(folder, "pythonw.exe"))

    def test_only_a_start_menu_shortcut_made_by_vivarc_is_removed(self):
        ours, theirs = os.path.join(self.tmp, "Vivarc", "Update Vivarc.lnk"), os.path.join(self.tmp, "Other.lnk")
        os.makedirs(os.path.dirname(ours))
        with open(ours, "wb") as f:
            f.write(b"L\0\0\0" + vivarc.UPDATE_MARK.encode("utf-16-le"))
        with open(theirs, "wb") as f:
            f.write(b"L\0\0\0" + "someone else".encode("utf-16-le"))
        vivarc.remove_update_app(ours)
        vivarc.remove_update_app(theirs)
        vivarc.remove_update_app(os.path.join(self.tmp, "missing.lnk"))
        self.assertFalse(os.path.exists(ours))
        self.assertFalse(os.path.exists(os.path.dirname(ours)))  # the empty Vivarc folder goes too
        self.assertTrue(os.path.exists(theirs))

    @windows_only
    def test_the_cmd_really_runs_and_keeps_the_exit_code(self):
        fake = os.path.join(self.tmp, "app dir")
        os.makedirs(fake)
        with open(os.path.join(fake, "vivarc.py"), "w") as f:
            f.write("import sys; print('ran', sys.argv[-1]); sys.exit(3)\n")
        path = os.path.join(self.tmp, "Update Vivarc.cmd")
        with mock.patch.object(vivarc, "HERE", fake), mock.patch.object(vivarc, "DEFAULT_APP", os.path.join(self.tmp, "none")):
            vivarc.write_update_command(path)
        result = subprocess.run(["cmd", "/c", path], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 3)
        self.assertIn("ran update", result.stdout)
        with open(path, "rb") as f:
            self.assertIn(b"\r\n", f.read())


class ReapplyTask(WinCase):
    def test_the_task_runs_remind_windowless_every_half_hour_while_logged_in(self):
        with mock.patch.object(vivarc, "schtasks", return_value=mock.Mock(returncode=0)) as schtasks, \
                mock.patch.object(vivarc, "windowless_python", return_value=r"C:\Py\pythonw.exe"), \
                mock.patch.object(vivarc, "HERE", r"C:\Users\me\.vivarc\app"):
            vivarc.enable_reminder(vivarc.DEFAULT_APP)
            vivarc.disable_reminder()
        create, delete = (c.args for c in schtasks.call_args_list)
        self.assertEqual(create[:9], ("/Create", "/F", "/TN", vivarc.REMINDER_TASK, "/SC", "MINUTE", "/MO", "30", "/IT"))
        self.assertEqual(create[-1].replace("/", "\\"), r'"C:\Py\pythonw.exe" "C:\Users\me\.vivarc\app\vivarc.py" remind')
        self.assertEqual(delete, ("/Delete", "/F", "/TN", vivarc.REMINDER_TASK))

    def test_a_vivaldi_in_another_folder_is_passed_along(self):
        with mock.patch.object(vivarc, "windowless_python", return_value="pyw"):
            command = vivarc.reminder_task_command(r"D:\Vivaldi\Application")
        self.assertIn(r'--app "D:\Vivaldi\Application" remind', command)


class SilentReapply(WinCase):
    def setUp(self):
        super().setUp()
        self.app = os.path.join(self.tmp, "Application")
        self.home = os.path.join(self.tmp, "home")
        self.res = self.version(self.app, "8.4.0.1")
        for p in (mock.patch.object(vivarc, "HOME_DIR", self.home),
                  mock.patch.object(vivarc, "latest_release_tag", return_value=None)):
            p.start()
            self.addCleanup(p.stop)

    def remind(self):
        notes, asked = [], []
        with mock.patch.object(vivarc, "notify", side_effect=notes.append), \
                mock.patch.object(vivarc, "prompt_update", side_effect=lambda m: asked.append(m) or False), \
                redirect_stdout(io.StringIO()):
            vivarc.cmd_remind(mock.Mock(app=self.app))
        return notes, asked

    def html(self):
        with open(os.path.join(self.res, "window.html"), encoding="utf8") as f:
            return f.read()

    def test_a_new_vivaldi_folder_gets_vivarc_back_without_a_question_and_one_notice(self):
        notes, asked = self.remind()
        self.assertIn(vivarc.BEGIN, self.html())
        self.assertTrue(os.path.exists(os.path.join(self.res, "vivarc.js")))
        self.assertEqual(asked, [])
        self.assertEqual(len(notes), 1)
        self.assertIn("8.4.0.1", notes[0])

    def test_the_notice_is_shown_once_per_vivaldi_version(self):
        self.remind()
        os.remove(os.path.join(self.res, "vivarc.js"))  # say Vivaldi repaired itself: re-apply quietly
        notes, _ = self.remind()
        self.assertEqual(notes, [])
        self.assertTrue(os.path.exists(os.path.join(self.res, "vivarc.js")))

    def test_when_the_folder_cannot_be_written_it_falls_back_to_asking(self):
        with mock.patch.object(vivarc, "apply_js", side_effect=PermissionError("denied")):
            notes, asked = self.remind()
        self.assertEqual(notes, [])
        self.assertEqual(len(asked), 1)


class Preflight(WinCase):
    def test_a_writable_vivaldi_folder_needs_nothing(self):
        vivarc.preflight(self.tmp, ask=lambda p: self.fail("asked"), open_settings=lambda: self.fail("opened"))

    def test_a_program_files_install_says_to_run_as_administrator(self):
        err = io.StringIO()
        with mock.patch.object(vivarc, "can_write", return_value=False), mock.patch("sys.stderr", err):
            with self.assertRaises(SystemExit):
                vivarc.preflight(self.tmp)
        self.assertIn("administrator", err.getvalue())
        self.assertIn("Nothing was changed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
