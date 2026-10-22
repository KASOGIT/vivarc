import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402

DEFAULTS = {
    "COMMAND_NEW_TAB": {"shortcuts": ["meta+t"], "gestures": ["2"]},
    "COMMAND_SHOW_QUICK_COMMANDS": {"shortcuts": ["meta+t", "meta+e", "f2"]},
    "COMMAND_PAGE_COPY_URL": {"shortcuts": ["meta+c"]},
    "COMMAND_CLOSE_TAB": {"shortcuts": ["meta+w"]},
    "COMMAND_SAVE_PAGE": {"shortcuts": ["meta+s"]},
    "COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR": {"shortcuts": []},
}


def prefs(**extra):
    base = {"vivaldi": {"toolbars": {"tabbar_before": ["TabButton", "AddressField", "Spacer"]}}}
    base.update(extra)
    return base


class PatchPreferences(unittest.TestCase):
    def test_creates_the_full_default_action_list_when_the_profile_has_none(self):
        new, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        actions = new["vivaldi"]["actions"][0]
        self.assertIn("COMMAND_CLOSE_TAB", actions)
        self.assertEqual(actions["COMMAND_CLOSE_TAB"]["shortcuts"], ["meta+w"])

    def test_frees_cmd_t_and_binds_copy_url(self):
        new, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        actions = new["vivaldi"]["actions"][0]
        self.assertEqual(actions["COMMAND_NEW_TAB"]["shortcuts"], [])
        self.assertEqual(actions["COMMAND_NEW_TAB"]["gestures"], ["2"])
        self.assertEqual(actions["COMMAND_SHOW_QUICK_COMMANDS"]["shortcuts"], ["meta+e", "f2"])
        self.assertIn("shift+meta+c", actions["COMMAND_PAGE_COPY_URL"]["shortcuts"])

    def test_keeps_the_users_own_shortcuts(self):
        mine = {"COMMAND_CLOSE_TAB": {"shortcuts": ["ctrl+q"]}, "COMMAND_NEW_TAB": {"shortcuts": ["meta+t", "ctrl+n"]}}
        new, _ = vivarc.patch_preferences(prefs(vivaldi={"actions": [mine], "toolbars": {}}), [DEFAULTS])
        actions = new["vivaldi"]["actions"][0]
        self.assertEqual(actions["COMMAND_CLOSE_TAB"]["shortcuts"], ["ctrl+q"])
        self.assertEqual(actions["COMMAND_NEW_TAB"]["shortcuts"], ["ctrl+n"])

    def test_removes_the_tab_bar_spacer_and_sets_left_tabs(self):
        new, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        self.assertEqual(new["vivaldi"]["toolbars"]["tabbar_before"], ["TabButton", "AddressField"])
        self.assertEqual(new["vivaldi"]["tabs"]["bar"]["position"], 1)
        self.assertNotIn("appearance", new["vivaldi"])

    def test_cmd_s_toggles_the_sidebar_instead_of_saving_the_page(self):
        new, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        actions = new["vivaldi"]["actions"][0]
        self.assertEqual(actions["COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR"]["shortcuts"], ["meta+s"])
        self.assertEqual(actions["COMMAND_SAVE_PAGE"]["shortcuts"], [])

    def test_drops_the_workspace_button_and_swaps_vpn_for_downloads(self):
        p = prefs(vivaldi={"toolbars": {
            "tabbar_before": ["WorkspaceButton", "TabButton", "AddressField", "Spacer"],
            "tabbar_after": ["NewTab", "AccountButton", "VPNButton", "UpdateButton"]}})
        new, _ = vivarc.patch_preferences(p, [DEFAULTS])
        self.assertEqual(new["vivaldi"]["toolbars"]["tabbar_before"], ["TabButton", "AddressField"])
        self.assertEqual(new["vivaldi"]["toolbars"]["tabbar_after"], ["NewTab", "AccountButton", "PanelDownloads", "UpdateButton"])

    def test_a_fresh_profile_gets_the_address_bar_inside_the_sidebar_and_none_on_top(self):
        new, _ = vivarc.patch_preferences({}, [DEFAULTS])
        bar = new["vivaldi"]["toolbars"]["tabbar_before"]
        self.assertEqual(bar[-1], "AddressField")
        self.assertIn("Back", bar)
        self.assertNotIn("WorkspaceButton", bar)
        self.assertIs(new["vivaldi"]["address_bar"]["visible"], False)

    def test_a_fresh_profile_gets_the_profile_and_downloads_buttons_at_the_sidebar_bottom(self):
        new, _ = vivarc.patch_preferences({}, [DEFAULTS])
        after = new["vivaldi"]["toolbars"]["tabbar_after"]
        self.assertIn("AccountButton", after)
        self.assertIn("PanelDownloads", after)
        self.assertNotIn("VPNButton", after)

    def test_moves_the_panel_bar_to_the_right_and_enables_auto_hide_for_cmd_s(self):
        new, _ = vivarc.patch_preferences({}, [DEFAULTS])
        self.assertEqual(new["vivaldi"]["panels"]["position"], 1)
        self.assertIs(new["vivaldi"]["auto_hide"]["enabled"], True)
        self.assertIs(new["vivaldi"]["auto_hide"]["panel"], True)

    def test_keeps_a_sidebar_width_the_user_already_chose(self):
        mine = {"vivaldi": {"tabs": {"bar": {"width": 500}}}}
        new, _ = vivarc.patch_preferences(mine, [DEFAULTS])
        self.assertEqual(new["vivaldi"]["tabs"]["bar"]["width"], 500)
        fresh, _ = vivarc.patch_preferences({}, [DEFAULTS])
        self.assertEqual(fresh["vivaldi"]["tabs"]["bar"]["width"], 323)

    def test_does_not_add_a_second_downloads_button(self):
        p = prefs(vivaldi={"toolbars": {"tabbar_after": ["AccountButton", "PanelDownloads", "VPNButton"]}})
        new, _ = vivarc.patch_preferences(p, [DEFAULTS])
        self.assertEqual(new["vivaldi"]["toolbars"]["tabbar_after"], ["AccountButton", "PanelDownloads"])

    def test_restore_brings_back_both_toolbars(self):
        p = prefs(vivaldi={"toolbars": {
            "tabbar_before": ["WorkspaceButton", "TabButton"], "tabbar_after": ["VPNButton"]}})
        new, snap = vivarc.patch_preferences(p, [DEFAULTS])
        restored = vivarc.restore_preferences(new, snap)
        self.assertEqual(restored["vivaldi"]["toolbars"]["tabbar_before"], ["WorkspaceButton", "TabButton"])
        self.assertEqual(restored["vivaldi"]["toolbars"]["tabbar_after"], ["VPNButton"])
        self.assertNotIn("address_bar", restored["vivaldi"])
        self.assertNotIn("panels", restored["vivaldi"])
        self.assertNotIn("auto_hide", restored["vivaldi"])

    def test_is_idempotent(self):
        once, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        twice, _ = vivarc.patch_preferences(copy.deepcopy(once), [DEFAULTS])
        self.assertEqual(once, twice)

    def test_does_not_mutate_its_input(self):
        original = prefs()
        snapshot = copy.deepcopy(original)
        vivarc.patch_preferences(original, [DEFAULTS])
        self.assertEqual(original, snapshot)

    def test_restore_brings_back_the_original_values_and_removes_added_keys(self):
        original = prefs(vivaldi={"toolbars": {"tabbar_before": ["TabButton", "Spacer"]}, "tabs": {"bar": {"position": 0}}})
        new, snap = vivarc.patch_preferences(original, [DEFAULTS])
        restored = vivarc.restore_preferences(new, snap)
        self.assertEqual(restored["vivaldi"]["toolbars"]["tabbar_before"], ["TabButton", "Spacer"])
        self.assertEqual(restored["vivaldi"]["tabs"]["bar"]["position"], 0)
        self.assertNotIn("actions", restored["vivaldi"])

    def test_recognises_a_profile_that_was_configured_by_vivarc(self):
        new, _ = vivarc.patch_preferences(prefs(), [DEFAULTS])
        self.assertTrue(vivarc.looks_configured(new))
        self.assertFalse(vivarc.looks_configured(prefs()))


class WindowHtml(unittest.TestCase):
    HTML = "<html><body>\n</body></html>"

    def test_injects_one_script_block_before_body_end(self):
        out = vivarc.inject_window_html(self.HTML)
        self.assertEqual(out.count("vivarc.js"), 1)
        self.assertLess(out.index("vivarc.js"), out.index("</body>"))

    def test_injection_is_idempotent_and_removable(self):
        once = vivarc.inject_window_html(self.HTML)
        self.assertEqual(vivarc.inject_window_html(once), once)
        self.assertEqual(vivarc.remove_window_html(once).strip(), self.HTML.strip())


class Profiles(unittest.TestCase):
    def test_lists_profiles_from_local_state_in_order(self):
        ls = {"profile": {"info_cache": {"Profile 2": {"name": "Work"}, "Default": {"name": "Me"}}}}
        self.assertEqual(vivarc.find_profiles(ls), [("Default", "Me"), ("Profile 2", "Work")])

    def test_returns_default_when_local_state_has_no_profiles(self):
        self.assertEqual(vivarc.find_profiles({}), [("Default", "Default")])


class Bundle(unittest.TestCase):
    def test_orders_files_by_name_and_prepends_config(self):
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("20-b.js", "B();"), ("00-a.js", "A();")):
                with open(os.path.join(d, name), "w") as f:
                    f.write(body)
            out = vivarc.build_bundle(d, {"suggestions": "off"}, extras=[("peek", "P();")])
        self.assertTrue(out.startswith("window.__vmConfig = " + json.dumps({"suggestions": "off"})))
        self.assertLess(out.index("A();"), out.index("B();"))
        self.assertIn("P();", out)


class StyleScript(unittest.TestCase):
    def test_embeds_the_css_as_a_style_element_with_the_text_intact(self):
        css = "#browser.vm-on { --vm-css: 1; content: \"x\"; }"
        js = vivarc.style_script("vivarc-css", css)
        self.assertIn("createElement(\"style\")", js)
        self.assertIn(json.dumps(css), js)


class BundleOrder(unittest.TestCase):
    def test_pre_scripts_run_before_the_modules_that_read_their_globals(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "00-core.js"), "w") as f:
                f.write("CORE();")
            out = vivarc.build_bundle(d, {}, extras=[("peek", "PEEK();")], pre=[("icons", "ICONS();")])
        self.assertLess(out.index("ICONS();"), out.index("CORE();"))
        self.assertLess(out.index("CORE();"), out.index("PEEK();"))


if __name__ == "__main__":
    unittest.main()
