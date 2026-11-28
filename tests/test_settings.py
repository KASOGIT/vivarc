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
        self.assertEqual(resolve(), {"glass": False, "glassOpacity": 55, "spaceGradient": True, "density": "default", "corners": "default", "motion": "full", "urlBar": False, "commandBarAddress": False, "spaceBar": True, "compactBottomBar": True, "searchSuggestions": True,
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
class SpaceGradient(unittest.TestCase):
    def classes(self, values):
        return js("settings.classes(settings.SCHEMA, values)", values=values)

    def test_the_gradient_is_on_by_default_and_a_class_while_on(self):
        self.assertTrue(resolve().get("spaceGradient"))
        self.assertTrue(self.classes(resolve()).get("vm-gradient"))

    def test_a_saved_off_drops_the_class(self):
        values = resolve(saved={"spaceGradient": False})
        self.assertIs(values.get("spaceGradient"), False)
        self.assertIs(self.classes(values).get("vm-gradient"), False)

    def test_the_appearance_section_lists_glass_opacity_gradient_then_density_corners_motion(self):
        out = js("settings.sections(settings.SCHEMA, config).find((s) => s.title === 'Appearance').items.map((i) => i.key)", config={})
        self.assertEqual(out, ["glass", "glassOpacity", "spaceGradient", "density", "corners", "motion"])

    def test_the_hint_is_the_same_on_mac_and_windows(self):
        for platform in ("mac", "win"):
            hints = js("settings.SCHEMA.filter((s) => s.key === 'spaceGradient').map((s) => settings.hint(s, platform))", platform=platform)
            self.assertEqual(hints, ["Blend each space's colour into a soft gradient."], platform)

    def test_the_gradient_row_is_labelled_and_shown_even_with_glass_off(self):
        shown = js("settings.shownRows(settings.SCHEMA, values).filter((s) => s.key === 'spaceGradient').map((s) => s.label)", values={"glass": False})
        self.assertEqual(shown, ["Space gradient"])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class AppearanceChoices(unittest.TestCase):
    CHOICES = {
        "density": ("vm-density", ["compact", "default", "comfortable"], "default"),
        "corners": ("vm-corners", ["sharp", "default", "round"], "default"),
        "motion": ("vm-motion", ["full", "reduced", "off"], "full"),
    }

    def classes(self, values):
        return js("settings.classes(settings.SCHEMA, values)", values=values)

    def with_prefix(self, classes, prefix):
        return {k: v for k, v in classes.items() if k.startswith(prefix + "-")}

    def test_each_choice_is_one_class_per_option_true_for_the_chosen_one(self):
        for key, (prefix, options, _default) in self.CHOICES.items():
            for chosen in options:
                with self.subTest(key=key, chosen=chosen):
                    expected = {f"{prefix}-{o}": o == chosen for o in options}
                    self.assertEqual(self.with_prefix(self.classes(resolve(saved={key: chosen})), prefix), expected)

    def test_the_defaults_give_density_default_corners_default_and_motion_full(self):
        classes = self.classes(resolve())
        self.assertIs(classes.get("vm-density-default"), True)
        self.assertIs(classes.get("vm-corners-default"), True)
        self.assertIs(classes.get("vm-motion-full"), True)

    def test_the_defaults_are_the_middle_density_and_corners_and_full_motion(self):
        values = resolve()
        self.assertEqual([values.get("density"), values.get("corners"), values.get("motion")], ["default", "default", "full"])

    def test_a_saved_value_outside_the_list_falls_back_to_the_default(self):
        self.assertEqual(resolve(saved={"density": "huge"}).get("density"), "default")
        self.assertEqual(resolve(saved={"corners": "square"}).get("corners"), "default")
        self.assertEqual(resolve(saved={"motion": "slow"}).get("motion"), "full")
        self.assertEqual(resolve(saved={"motion": True}).get("motion"), "full")

    def test_a_saved_value_from_the_list_is_kept(self):
        self.assertEqual(resolve(saved={"density": "compact"}).get("density"), "compact")
        self.assertEqual(resolve(saved={"corners": "round"}).get("corners"), "round")
        self.assertEqual(resolve(saved={"motion": "off"}).get("motion"), "off")

    def test_a_fallback_value_still_marks_the_default_class(self):
        classes = self.classes(resolve(saved={"density": "huge"}))
        self.assertEqual(self.with_prefix(classes, "vm-density"), {"vm-density-compact": False, "vm-density-default": True, "vm-density-comfortable": False})

    def test_a_choice_without_a_class_prefix_adds_no_class(self):
        self.assertEqual(self.classes(resolve(saved={"peekShortcut": "shift"})), self.classes(resolve()))
        self.assertFalse([k for k in self.classes(resolve()) if "shift" in k or "alt" in k])

    def test_the_settings_are_choices_with_these_labels_options_and_prefixes(self):
        out = js("settings.SCHEMA.filter((s) => ['density', 'corners', 'motion'].includes(s.key)).map((s) => [s.key, s.type, s.label, s.default, s.options, s.classPrefix])")
        self.assertEqual(out, [
            ["density", "choice", "Density", "default", [["compact", "Compact"], ["default", "Default"], ["comfortable", "Comfortable"]], "vm-density"],
            ["corners", "choice", "Corners", "default", [["sharp", "Sharp"], ["default", "Default"], ["round", "Round"]], "vm-corners"],
            ["motion", "choice", "Motion", "full", [["full", "Full"], ["reduced", "Reduced"], ["off", "Off"]], "vm-motion"],
        ])

    def test_the_rows_are_shown_without_any_other_setting_or_install(self):
        shown = js("settings.shownRows(settings.visible(settings.SCHEMA, config), values).map((s) => s.key)", config={}, values={"glass": False})
        for key in self.CHOICES:
            self.assertIn(key, shown)

    def test_the_hints_are_the_same_on_both_platforms_for_density_and_corners(self):
        hint = lambda key, platform: js("(() => { const item = settings.SCHEMA.find((s) => s.key === key); return item ? settings.hint(item, platform) : null; })()", key=key, platform=platform)
        for platform in ("mac", "win"):
            self.assertEqual(hint("density", platform), "Height of the rows in the sidebar.", platform)
            self.assertEqual(hint("corners", platform), "Roundness of rows, menus and dialogs.", platform)

    def test_the_motion_hint_names_the_system_option_for_each_platform(self):
        hint = lambda platform: js("(() => { const item = settings.SCHEMA.find((s) => s.key === 'motion'); return item ? settings.hint(item, platform) : null; })()", platform=platform)
        self.assertEqual(hint("mac"), "Reduced keeps fades and drops movement. Reduce Motion in macOS settings always applies.")
        self.assertEqual(hint("win"), "Reduced keeps fades and drops movement. Turning off animation effects in Windows always applies.")


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class ReduceMotion(unittest.TestCase):
    def reduce(self, motion, system):
        return js("typeof settings.reduceMotion === 'function' ? settings.reduceMotion({ motion }, system) : 'reduceMotion is missing'", motion=motion, system=system)

    def test_full_motion_follows_the_system(self):
        self.assertIs(self.reduce("full", False), False)
        self.assertIs(self.reduce("full", True), True)

    def test_reduced_and_off_reduce_whatever_the_system_says(self):
        self.assertIs(self.reduce("reduced", False), True)
        self.assertIs(self.reduce("off", False), True)
        self.assertIs(self.reduce("off", True), True)
        self.assertIs(self.reduce("reduced", True), True)


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


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Hints(unittest.TestCase):
    SAME = {
        "glassOpacity": None,
        "spaceGradient": "Blend each space's colour into a soft gradient.",
        "density": "Height of the rows in the sidebar.",
        "corners": "Roundness of rows, menus and dialogs.",
        "urlBar": "Always show the address bar. Off, it appears when you edit the address.",
        "spaceBar": "The row of space tiles at the bottom.",
        "compactBottomBar": "A tighter row for profiles and downloads.",
        "archive": "Close tabs left unopened, like Arc. Pins, favorites and tabs playing sound stay.",
        "archiveHours": None,
        "peek": "Open some links in a floating window over the page. Esc closes it.",
        "peekPinned": "A link to another site opens in the preview, like Arc.",
        "peekDim": None,
        "searchSuggestions": "From your default search engine, in the command bar.",
        "updateCheck": "Ask GitHub now and then for a new Vivarc release. Off, nothing is requested.",
    }
    BY_PLATFORM = {
        "commandBarAddress": {
            "mac": "Cmd+L opens the address in the command bar, like Arc. Off, it is edited in the sidebar.",
            "win": "Ctrl+L opens the address in the command bar, like Arc. Off, it is edited in the sidebar.",
        },
        "peekShortcut": {
            "mac": "Click a link with this key held. Cmd+click still opens a new tab.",
            "win": "Click a link with this key held. Ctrl+click still opens a new tab.",
        },
        "glass": {
            "mac": "Translucent, blurred sidebar, menus and dialogs. Follows Reduce Transparency.",
            "win": "Translucent, blurred sidebar, menus and dialogs.",
        },
        "motion": {
            "mac": "Reduced keeps fades and drops movement. Reduce Motion in macOS settings always applies.",
            "win": "Reduced keeps fades and drops movement. Turning off animation effects in Windows always applies.",
        },
    }

    def hint(self, key, platform):
        return js("(() => { const item = settings.SCHEMA.find((s) => s.key === key); return item ? settings.hint(item, platform) : null; })()", key=key, platform=platform)

    def test_the_shortcut_and_glass_hints_follow_the_platform(self):
        for key, by_platform in self.BY_PLATFORM.items():
            for platform, expected in by_platform.items():
                with self.subTest(key=key, platform=platform):
                    self.assertEqual(self.hint(key, platform), expected)

    def test_the_other_hints_are_the_same_on_both_platforms(self):
        for key, expected in self.SAME.items():
            for platform in ("mac", "win"):
                with self.subTest(key=key, platform=platform):
                    self.assertEqual(self.hint(key, platform), expected)

    def test_every_setting_is_covered_by_the_hint_tables(self):
        self.assertEqual(sorted(list(self.SAME) + list(self.BY_PLATFORM)), sorted(resolve().keys()))

    MAC_ONLY_TERMS = ("Cmd", "Option", "⌘", "⌥", "⌃", "Reduce Transparency", "System Settings", "Finder")

    def test_no_windows_hint_names_a_macos_only_term(self):
        hints = js("settings.SCHEMA.map((s) => [s.key, settings.hint(s, 'win')])")
        self.assertTrue(hints)
        for key, text in hints:
            if text is None:
                continue
            for term in self.MAC_ONLY_TERMS:
                with self.subTest(key=key, term=term):
                    self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
