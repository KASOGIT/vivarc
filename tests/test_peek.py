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


# Runs the page script Vivarc injects in a fake page window, then lets Peek try to set its own flag.
PAGE = """
const listeners = [];
const page = { addEventListener: (type, fn, capture) => listeners.push({ type, fn, capture }) };
const run = (code) => new Function("window", code)(page);
const press = (mods) => listeners.filter((l) => l.type === "pointerdown").forEach((l) => l.fn({ button: 0, ...mods }));
"""


def page(steps):
    return js("(() => {" + PAGE + steps + "})()")


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class PinnedPage(unittest.TestCase):
    def test_a_vivarc_pin_counts_as_pinned_for_peek(self):
        self.assertTrue(page("run(peek.pinnedScript(true)); return page.__arcpeekCurrentTabIsPinned;"))

    def test_peek_cannot_mark_a_page_pinned_that_is_not_a_vivarc_pin(self):
        out = page("run(peek.pinnedScript(false)); page.__arcpeekCurrentTabIsPinned = true; return page.__arcpeekCurrentTabIsPinned;")
        self.assertFalse(out)

    def test_cmd_or_ctrl_click_in_a_pinned_page_is_not_a_pinned_click(self):
        self.assertFalse(page("run(peek.pinnedScript(true)); press({ metaKey: true }); return page.__arcpeekCurrentTabIsPinned;"))
        self.assertFalse(page("run(peek.pinnedScript(true)); press({ ctrlKey: true }); return page.__arcpeekCurrentTabIsPinned;"))

    def test_a_plain_click_after_a_cmd_click_is_pinned_again(self):
        out = page("run(peek.pinnedScript(true)); press({ metaKey: true }); press({}); return page.__arcpeekCurrentTabIsPinned;")
        self.assertTrue(out)

    def test_the_script_listens_before_peek_in_the_capture_phase_of_window(self):
        out = page("run(peek.pinnedScript(true)); return listeners.filter((l) => l.type === 'pointerdown').map((l) => l.capture);")
        self.assertEqual(out, [True])

    def test_unpinning_updates_an_open_page_without_a_second_listener(self):
        out = page("run(peek.pinnedScript(true)); run(peek.pinnedScript(false)); "
                   "return [page.__arcpeekCurrentTabIsPinned, listeners.length];")
        self.assertEqual(out, [False, 1])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class OpenPreviewTabs(unittest.TestCase):
    def test_the_tabs_of_open_previews_are_peek_tabs(self):
        webviews = [{"parallelTabId": 7, "relatedTabId": 8}, {"relatedTabId": 9}]
        self.assertEqual(sorted(js("[...peek.previewTabIds(webviews)]", webviews=webviews)), [7, 8, 9])

    def test_without_an_open_preview_no_tab_is_a_peek_tab_by_id(self):
        self.assertEqual(js("[...peek.previewTabIds([])]"), [])


ADOPT = "(async () => { const moves = []; const done = await peek.adoptStashedTab(data, active, async (p) => { moves.push(p); }); return { done, moves }; })()"


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class StashedTab(unittest.TestCase):
    def adopt(self, data, active):
        return js(ADOPT, data=data, active=active)

    def test_a_preloaded_tab_opened_as_a_tab_is_moved_by_vivaldi_into_the_space_on_screen(self):
        out = self.adopt({"parallelTabId": 7, "_hiddenWorkspaceId": 5}, {"id": 1, "vivExtData": '{"workspaceId": 3}'})
        self.assertTrue(out["done"])
        self.assertEqual(out["moves"], [{"tabIds": [7], "target": "last", "tweaks": ["do-not-reparent"], "workspaceId": 3}])

    def test_into_the_default_space_it_moves_to_no_workspace(self):
        out = self.adopt({"parallelTabId": 7, "_hiddenWorkspaceId": 5}, {"id": 1, "vivExtData": "{}"})
        self.assertEqual(out["moves"][0]["workspaceId"], None)
        out = self.adopt({"parallelTabId": 7, "_hiddenWorkspaceId": 5}, None)
        self.assertEqual(out["moves"][0]["workspaceId"], None)

    def test_a_preloaded_tab_that_was_never_stashed_is_left_alone(self):
        out = self.adopt({"parallelTabId": 7, "_hiddenWorkspaceId": None}, {"id": 1, "vivExtData": '{"workspaceId": 3}'})
        self.assertEqual(out, {"done": False, "moves": []})
        self.assertEqual(self.adopt({"parallelTabId": None}, None), {"done": False, "moves": []})
        self.assertEqual(self.adopt(None, None), {"done": False, "moves": []})


if __name__ == "__main__":
    unittest.main()
