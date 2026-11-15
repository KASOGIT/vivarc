import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("01-settings.js", expr, **data)


def resolve(config=None, saved=None):
    return js("settings.resolve(settings.SCHEMA, config, saved)", config=config or {}, saved=saved or {})


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Resolve(unittest.TestCase):
    def test_without_anything_saved_the_defaults_apply(self):
        self.assertEqual(resolve(), {"glass": False, "glassOpacity": 55, "urlBar": False, "commandBarAddress": False, "spaceBar": True, "compactBottomBar": True, "searchSuggestions": True,
                                    "archive": False, "archiveHours": 12, "updateCheck": True,
                                    "peek": True, "peekPinned": True, "peekShortcut": "alt", "peekDim": True})

    def test_the_install_config_sets_the_starting_point(self):
        values = resolve(config={"compactBottomBar": False, "suggestions": "off"})
        self.assertFalse(values["compactBottomBar"])
        self.assertFalse(values["searchSuggestions"])

    def test_suggestions_are_on_unless_the_config_says_off(self):
        for value in ("on", "ddg", "google"):
            self.assertTrue(resolve(config={"suggestions": value})["searchSuggestions"], value)
        self.assertFalse(resolve(config={"suggestions": "off"})["searchSuggestions"])
        self.assertFalse(resolve(config={"suggestions": False})["searchSuggestions"])

    def test_what_the_user_saved_wins_over_the_install_config(self):
        values = resolve(config={"compactBottomBar": False}, saved={"compactBottomBar": True, "spaceBar": False})
        self.assertTrue(values["compactBottomBar"])
        self.assertFalse(values["spaceBar"])

    def test_a_saved_value_of_the_wrong_type_or_an_unknown_key_is_ignored(self):
        values = resolve(saved={"spaceBar": "no", "nonsense": True})
        self.assertTrue(values["spaceBar"])
        self.assertNotIn("nonsense", values)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class GlassOpacity(unittest.TestCase):
    def test_a_saved_opacity_is_used(self):
        self.assertEqual(resolve(saved={"glassOpacity": 80})["glassOpacity"], 80)

    def test_an_opacity_outside_the_range_is_pulled_back_in(self):
        self.assertEqual(resolve(saved={"glassOpacity": 5})["glassOpacity"], 15)
        self.assertEqual(resolve(saved={"glassOpacity": 400})["glassOpacity"], 95)

    def test_something_that_is_not_a_number_is_ignored(self):
        self.assertEqual(resolve(saved={"glassOpacity": "high"})["glassOpacity"], 55)
        self.assertEqual(resolve(saved={"glassOpacity": True})["glassOpacity"], 55)

    def test_the_opacity_becomes_a_css_variable_in_percent(self):
        out = js("settings.vars(settings.SCHEMA, values)", values={"glassOpacity": 72})
        self.assertEqual(out, {"--vm-glass-opacity": "72%"})


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class MarkerClasses(unittest.TestCase):
    def classes(self, values):
        return js("settings.classes(settings.SCHEMA, values)", values=values)

    def test_compact_bottom_bar_is_a_class_while_on(self):
        self.assertTrue(self.classes({"compactBottomBar": True})["vm-compact-bottom"])
        self.assertFalse(self.classes({"compactBottomBar": False})["vm-compact-bottom"])

    def test_liquid_glass_is_a_class_while_on_and_off_by_default(self):
        self.assertTrue(self.classes({"glass": True})["vm-glass"])
        self.assertFalse(self.classes({"glass": False})["vm-glass"])
        self.assertFalse(resolve()["glass"])

    def test_hiding_the_space_bar_is_a_class_while_it_is_off(self):
        self.assertTrue(self.classes({"spaceBar": False})["vm-no-space-bar"])
        self.assertFalse(self.classes({"spaceBar": True})["vm-no-space-bar"])

    def test_the_url_bar_is_a_class_while_on_and_off_by_default(self):
        self.assertTrue(self.classes({"urlBar": True})["vm-url-bar"])
        self.assertFalse(self.classes({"urlBar": False})["vm-url-bar"])
        self.assertFalse(resolve()["urlBar"])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class ArchiveHours(unittest.TestCase):
    def test_a_saved_number_of_hours_is_used(self):
        self.assertEqual(resolve(saved={"archiveHours": 48})["archiveHours"], 48)

    def test_hours_outside_the_range_are_pulled_back_in(self):
        self.assertEqual(resolve(saved={"archiveHours": 0})["archiveHours"], 1)
        self.assertEqual(resolve(saved={"archiveHours": 1000})["archiveHours"], 168)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class PeekSettings(unittest.TestCase):
    def test_peek_is_on_by_default_and_previews_links_from_pinned_tabs(self):
        values = resolve()
        self.assertTrue(values["peek"])
        self.assertTrue(values["peekPinned"])

    def test_the_peek_shortcut_keeps_a_saved_choice_from_its_list(self):
        self.assertEqual(resolve(saved={"peekShortcut": "shift"})["peekShortcut"], "shift")
        self.assertEqual(resolve(saved={"peekShortcut": "none"})["peekShortcut"], "none")

    def test_a_peek_shortcut_outside_the_list_falls_back_to_the_default(self):
        self.assertEqual(resolve(saved={"peekShortcut": "meta"})["peekShortcut"], "alt")
        self.assertEqual(resolve(saved={"peekShortcut": True})["peekShortcut"], "alt")

    def test_the_peek_rows_are_shown_only_when_peek_is_installed(self):
        shown = lambda config: js("settings.visible(settings.SCHEMA, config).map((s) => s.key)", config=config)
        self.assertNotIn("peek", shown({}))
        self.assertNotIn("peekShortcut", shown({"peekInstalled": False}))
        self.assertIn("peek", shown({"peekInstalled": True}))
        self.assertIn("peekDim", shown({"peekInstalled": True}))
        self.assertIn("glass", shown({}))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Sections(unittest.TestCase):
    def test_the_settings_page_reads_as_five_sections_in_this_order(self):
        out = js("settings.sections(settings.SCHEMA, config).map((s) => s.title)", config={"peekInstalled": True})
        self.assertEqual(out, ["Appearance", "Sidebar", "Tabs", "Link preview", "General"])

    def test_every_setting_is_in_exactly_one_section(self):
        out = js("settings.sections(settings.SCHEMA, config).flatMap((s) => s.items.map((i) => i.key)).sort()", config={"peekInstalled": True})
        self.assertEqual(out, sorted(resolve().keys()))

    def test_the_link_preview_section_is_left_out_without_peek(self):
        out = js("settings.sections(settings.SCHEMA, config).map((s) => s.title)", config={})
        self.assertNotIn("Link preview", out)

    def test_a_setting_that_depends_on_another_is_shown_only_while_that_one_is_on(self):
        shown = lambda values: js("settings.shownRows(settings.SCHEMA, values).map((s) => s.key)", values=values)
        self.assertNotIn("glassOpacity", shown({"glass": False}))
        self.assertIn("glassOpacity", shown({"glass": True}))
        self.assertNotIn("peekShortcut", shown({"peek": False}))
        self.assertIn("peekShortcut", shown({"peek": True}))


if __name__ == "__main__":
    unittest.main()
