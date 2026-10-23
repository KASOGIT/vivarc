import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402


class CanWrite(unittest.TestCase):
    def test_true_for_a_writable_folder_and_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(vivarc.can_write(d))
            self.assertEqual(os.listdir(d), [])

    def test_false_for_a_folder_that_refuses_writes(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
            try:
                self.assertFalse(vivarc.can_write(d))
            finally:
                os.chmod(d, stat.S_IRWXU)


class Preflight(unittest.TestCase):
    def run_preflight(self, writes, answers):
        out, err = io.StringIO(), io.StringIO()
        opened = []
        replies = iter(answers)
        with mock.patch.object(vivarc, "can_write", side_effect=writes), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                vivarc.preflight("/x", ask=lambda prompt: next(replies), open_settings=lambda: opened.append(1))
                failed = False
            except SystemExit:
                failed = True
        return failed, opened, out.getvalue(), err.getvalue()

    def test_does_nothing_when_writing_is_already_allowed(self):
        failed, opened, _, _ = self.run_preflight([True], [])
        self.assertFalse(failed)
        self.assertEqual(opened, [])

    def test_opens_the_settings_pane_waits_and_retries_until_allowed(self):
        failed, opened, out, _ = self.run_preflight([False, False, True], ["", ""])
        self.assertFalse(failed)
        self.assertEqual(len(opened), 1)
        self.assertIn("App Management", out)

    def test_stops_without_changing_anything_when_there_is_no_terminal_to_ask(self):
        failed, _, _, err = self.run_preflight([False], [None])
        self.assertTrue(failed)
        self.assertIn("nothing was changed", err.lower())

    def test_stops_when_the_user_cancels(self):
        failed, _, _, _ = self.run_preflight([False], ["q"])
        self.assertTrue(failed)


class RootAndOwnership(unittest.TestCase):
    def test_refuses_to_run_as_root(self):
        with mock.patch("os.geteuid", return_value=0), redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                vivarc.check_not_root()
        self.assertIn("sudo", err.getvalue())

    def test_a_folder_owned_by_someone_else_gets_the_exact_fix_command(self):
        with tempfile.TemporaryDirectory() as d:
            real = os.getuid()
            with mock.patch("os.getuid", return_value=real + 1), redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit):
                    vivarc.check_owner(d)
            self.assertIn("chown", err.getvalue())
            self.assertIn(d, err.getvalue())

    def test_a_missing_folder_is_fine(self):
        vivarc.check_owner("/definitely/not/here")


class WriteAtomic(unittest.TestCase):
    def test_replaces_an_existing_read_only_file_without_leaving_temp_files(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "vivarc.js")
            with open(path, "w") as f:
                f.write("old")
            os.chmod(path, 0o444)
            vivarc.write_atomic(path, "new")
            with open(path) as f:
                self.assertEqual(f.read(), "new")
            self.assertEqual(os.listdir(d), ["vivarc.js"])


class EnsureVivaldiClosed(unittest.TestCase):
    def run_it(self, running, answer):
        state = {"open": running}
        quit_called = []

        def quit_app():
            quit_called.append(1)
            state["open"] = False

        with mock.patch.object(vivarc, "vivaldi_running", side_effect=lambda: state["open"]), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                vivarc.ensure_vivaldi_closed(ask=lambda p: answer, quit_app=quit_app)
                failed = False
            except SystemExit:
                failed = True
        return failed, quit_called

    def test_nothing_to_do_when_vivaldi_is_closed(self):
        self.assertEqual(self.run_it(False, "n"), (False, []))

    def test_quits_vivaldi_when_the_user_agrees(self):
        self.assertEqual(self.run_it(True, ""), (False, [1]))
        self.assertEqual(self.run_it(True, "y"), (False, [1]))

    def test_stops_when_the_user_declines_or_cannot_be_asked(self):
        self.assertTrue(self.run_it(True, "n")[0])
        self.assertTrue(self.run_it(True, None)[0])


if __name__ == "__main__":
    unittest.main()
