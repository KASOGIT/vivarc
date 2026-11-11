import shutil
import unittest

from jsrun import run_js


def should_close(tab, source, no_history=True, kept=False):
    return run_js("13-back.js", "back.shouldClose({ tab, source, noHistory, kept })", tab=tab, source=source, noHistory=no_history, kept=kept)


OPENED = {"id": 2, "windowId": 1}
SOURCE = {"id": 1, "windowId": 1}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the Back behaviour's JavaScript")
class ShouldClose(unittest.TestCase):
    def test_an_opened_tab_with_no_history_closes(self):
        self.assertTrue(should_close(OPENED, SOURCE))

    def test_a_tab_that_can_go_back_stays(self):
        self.assertFalse(should_close(OPENED, SOURCE, no_history=False))

    def test_an_unknown_history_state_keeps_the_tab(self):
        self.assertFalse(should_close(OPENED, SOURCE, no_history=None))

    def test_a_tab_whose_source_is_gone_stays(self):
        self.assertFalse(should_close(OPENED, None))

    def test_a_source_in_another_window_keeps_the_tab(self):
        self.assertFalse(should_close(OPENED, {"id": 1, "windowId": 7}))

    def test_pinned_and_kept_tabs_stay(self):
        self.assertFalse(should_close({**OPENED, "pinned": True}, SOURCE))
        self.assertFalse(should_close(OPENED, SOURCE, kept=True))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the Back behaviour's JavaScript")
class Keys(unittest.TestCase):
    def test_vivaldi_shortcut_text_matches_the_binding(self):
        self.assertEqual(run_js("13-back.js", "[back.comboKey('Meta+ArrowLeft'), back.comboKey('Left+Alt'), back.comboKey('meta+[')]"),
                         ["left+meta", "alt+left", "[+meta"])

    def test_defaults_per_platform_and_mac_always_has_cmd_bracket(self):
        self.assertEqual(run_js("13-back.js", "back.backKeys(null, 'mac')"), ["left+meta", "[+meta"])
        self.assertEqual(run_js("13-back.js", "back.backKeys(undefined, 'win')"), ["alt+left", "ctrl+left"])

    def test_single_keys_are_left_out(self):
        self.assertEqual(run_js("13-back.js", "back.backKeys(['backspace', 'z', 'alt+left'], 'win')"), ["alt+left"])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the Back behaviour's JavaScript")
class Swipe(unittest.TestCase):
    def test_the_page_script_is_valid_and_names_its_tab(self):
        code = run_js("13-back.js", "back.swipeScript(42)")
        self.assertIn("vivarcBack: 42", code)
        run_js("13-back.js", "(new Function(code), true)", code=code)
