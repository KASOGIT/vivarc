import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("03-peek.js", expr, **data)


ON = {"peek": True, "peekPinned": True, "peekShortcut": "alt", "peekDim": True}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Triggers(unittest.TestCase):
    def triggers(self, **changes):
        return js("peek.triggers(values)", values={**ON, **changes})

    def test_off_peek_intercepts_no_click_at_all(self):
        out = self.triggers(peek=False)
        self.assertEqual(out["clickOpenModifiers"], [])
        self.assertEqual(out["longPressButtons"], [])
        self.assertEqual(out["autoOpenList"], [])

    def test_on_a_plain_click_opens_peek_only_from_a_pinned_tab_never_on_google(self):
        out = self.triggers()
        self.assertEqual(out["autoOpenList"], ["pin"])
        self.assertNotIn("*.google.com", out["autoOpenList"])

    def test_without_the_pinned_tab_option_a_plain_click_is_never_taken(self):
        self.assertEqual(self.triggers(peekPinned=False)["autoOpenList"], [])

    def test_the_shortcut_choice_is_the_modifier_for_a_click(self):
        self.assertEqual(self.triggers()["clickOpenModifiers"], ["alt"])
        self.assertEqual(self.triggers(peekShortcut="shift")["clickOpenModifiers"], ["shift"])
        self.assertEqual(self.triggers(peekShortcut="none")["clickOpenModifiers"], [])

    def test_cmd_and_ctrl_click_are_never_taken_by_peek(self):
        for shortcut in ("alt", "shift", "none"):
            mods = self.triggers(peekShortcut=shortcut)["clickOpenModifiers"]
            self.assertNotIn("meta", mods)
            self.assertNotIn("ctrl", mods)

    def test_holding_the_middle_button_opens_peek_while_on(self):
        self.assertEqual(self.triggers()["longPressButtons"], ["middle"])

    def test_dimming_the_page_behind_follows_its_setting(self):
        self.assertTrue(self.triggers()["scaleBackgroundPage"])
        self.assertFalse(self.triggers(peekDim=False)["scaleBackgroundPage"])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class PeekTabs(unittest.TestCase):
    def is_peek(self, tab, ids=()):
        return js("peek.isPeekTab(tab, new Set(ids))", tab=tab, ids=list(ids))

    def test_a_tab_peek_preloads_in_the_background_is_a_peek_tab(self):
        self.assertTrue(self.is_peek({"id": 7, "vivExtData": '{"workspaceId": 3}'}, ids=[7]))

    def test_the_tab_behind_an_open_preview_is_a_peek_tab(self):
        tab = {"id": 9, "vivExtData": '{"panelId": "arcpeek-x", "arcPeekRuntime": {"createdBy": "ArcPeek", "webviewId": "x"}}'}
        self.assertTrue(self.is_peek(tab))

    def test_an_ordinary_tab_is_not_a_peek_tab(self):
        self.assertFalse(self.is_peek({"id": 4, "vivExtData": '{"workspaceId": 3}'}, ids=[7]))
        self.assertFalse(self.is_peek({"id": 5}))
        self.assertFalse(self.is_peek({"id": 6, "vivExtData": "not json"}))

    def test_peek_tabs_are_left_out_of_a_tab_list(self):
        tabs = [{"id": 1}, {"id": 2, "vivExtData": '{"arcPeekRuntime": {"webviewId": "x"}}'}, {"id": 3}]
        self.assertEqual(js("peek.withoutPeekTabs(tabs).map((t) => t.id)", tabs=tabs), [1, 3])


if __name__ == "__main__":
    unittest.main()
