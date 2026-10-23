import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402


class IsNewer(unittest.TestCase):
    def test_compares_release_tags_numerically(self):
        self.assertTrue(vivarc.is_newer("v0.1.10", "0.1.9"))
        self.assertTrue(vivarc.is_newer("v0.2.0", "0.1.9"))
        self.assertFalse(vivarc.is_newer("v0.1.2", "0.1.2"))
        self.assertFalse(vivarc.is_newer("v0.1.1", "0.1.2"))

    def test_an_unreadable_tag_is_never_newer(self):
        self.assertFalse(vivarc.is_newer(None, "0.1.2"))
        self.assertFalse(vivarc.is_newer("latest", "0.1.2"))


class UpdateCommandFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "Applications", "Update Vivarc.command")

    def test_is_a_double_clickable_script_that_runs_update_from_this_copy(self):
        vivarc.write_update_command(self.path)
        self.assertTrue(os.stat(self.path).st_mode & stat.S_IXUSR)
        with open(self.path) as f:
            script = f.read()
        self.assertTrue(script.startswith("#!/bin/bash"))
        self.assertIn(os.path.join(vivarc.HERE, "vivarc.py"), script)
        self.assertIn("update", script)
        self.assertIn("open -a Vivaldi", script)

    def test_quotes_a_path_with_spaces(self):
        with mock.patch.object(vivarc, "HERE", "/Users/some one/vivarc"):
            vivarc.write_update_command(self.path)
        with open(self.path) as f:
            self.assertIn("'/Users/some one/vivarc/vivarc.py'", f.read())

    def test_removal_only_touches_a_file_made_by_vivarc(self):
        vivarc.write_update_command(self.path)
        vivarc.remove_update_command(self.path)
        self.assertFalse(os.path.exists(self.path))
        with open(self.path, "w") as f:
            f.write("#!/bin/bash\necho mine\n")
        vivarc.remove_update_command(self.path)
        self.assertTrue(os.path.exists(self.path))
        vivarc.remove_update_command(os.path.join(self.tmp, "missing"))


class Replaced(Exception):
    """os.execve never returns; the fake stops the run the same way."""


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = os.path.join(self.tmp, ".vivarc", "app")
        os.makedirs(self.copy)
        self.args = mock.Mock(app="/Apps/Vivaldi.app", data_dir="/data", no_peek=False, dry_run=False)

    def run_update(self, here, latest, git_ok=True):
        out = io.StringIO()
        calls = {"install": [], "execve": [], "git": []}

        def fake_execve(*a):
            calls["execve"].append(a)
            raise Replaced

        def fake_git(cmd, **kwargs):
            calls["git"].append(cmd)
            return mock.Mock(returncode=0 if git_ok else 1, stdout="", stderr="not a fast-forward")

        with mock.patch.object(vivarc, "HERE", here), \
                mock.patch.object(vivarc, "HOME_DIR", os.path.join(self.tmp, ".vivarc")), \
                mock.patch.object(vivarc, "latest_release_tag", return_value=latest), \
                mock.patch.object(vivarc, "cmd_install", side_effect=lambda a: calls["install"].append(a)), \
                mock.patch("os.execve", side_effect=fake_execve), \
                mock.patch("subprocess.run", side_effect=fake_git), \
                redirect_stdout(out), redirect_stderr(io.StringIO()):
            try:
                vivarc.cmd_update(self.args)
            except Replaced:
                pass
        return calls, out.getvalue()

    def test_a_newer_release_hands_over_to_the_installer_script_with_the_same_app_and_data(self):
        calls, out = self.run_update(self.copy, "v9.0.0")
        self.assertEqual(calls["install"], [])
        (program, argv, env), = calls["execve"]
        self.assertEqual(program, "/bin/bash")
        self.assertEqual(argv[1], os.path.join(self.copy, "install.sh"))
        self.assertEqual(env["VIVARC_APP"], "/Apps/Vivaldi.app")
        self.assertEqual(env["VIVARC_DATA_DIR"], "/data")
        self.assertIn("9.0.0", out)

    def test_no_peek_is_passed_on_to_the_installer(self):
        self.args.no_peek = True
        calls, _ = self.run_update(self.copy, "v9.0.0")
        self.assertIn("--no-peek", calls["execve"][0][1])

    def test_when_already_up_to_date_it_reapplies_in_place(self):
        calls, out = self.run_update(self.copy, "v" + vivarc.VERSION)
        self.assertEqual(calls["install"], [self.args])
        self.assertEqual(calls["execve"], [])
        self.assertIn("up to date", out.lower())

    def test_when_offline_it_reapplies_what_it_has(self):
        calls, out = self.run_update(self.copy, None)
        self.assertEqual(calls["install"], [self.args])
        self.assertEqual(calls["execve"], [])
        self.assertIn("could not check", out.lower())

    def test_a_git_checkout_pulls_then_reruns_itself_to_load_the_new_code(self):
        checkout = os.path.join(self.tmp, "checkout")
        os.makedirs(os.path.join(checkout, ".git"))
        calls, _ = self.run_update(checkout, "v9.0.0")
        self.assertEqual(calls["git"], [["git", "-C", checkout, "pull", "--ff-only"]])
        (program, argv, env), = calls["execve"]
        self.assertEqual(program, sys.executable)
        self.assertEqual(argv[1:], [os.path.join(checkout, "vivarc.py"), "--app", "/Apps/Vivaldi.app",
                                    "--data-dir", "/data", "install"])
        self.assertEqual(calls["install"], [])

    def test_a_git_checkout_that_cannot_fast_forward_still_reapplies(self):
        checkout = os.path.join(self.tmp, "checkout")
        os.makedirs(os.path.join(checkout, ".git"))
        calls, out = self.run_update(checkout, "v9.0.0", git_ok=False)
        self.assertEqual(calls["execve"], [])
        self.assertEqual(calls["install"], [self.args])
        self.assertIn("git pull", out)


if __name__ == "__main__":
    unittest.main()
