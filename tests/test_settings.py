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
        self.assertEqual(resolve(), {"spaceBar": True, "compactBottomBar": True, "searchSuggestions": True})

    def test_the_install_config_sets_the_starting_point(self):
        values = resolve(config={"compactBottomBar": False, "suggestions": "off"})
        self.assertFalse(values["compactBottomBar"])
        self.assertFalse(values["searchSuggestions"])

    def test_what_the_user_saved_wins_over_the_install_config(self):
        values = resolve(config={"compactBottomBar": False}, saved={"compactBottomBar": True, "spaceBar": False})
        self.assertTrue(values["compactBottomBar"])
        self.assertFalse(values["spaceBar"])

    def test_a_saved_value_of_the_wrong_type_or_an_unknown_key_is_ignored(self):
        values = resolve(saved={"spaceBar": "no", "nonsense": True})
        self.assertTrue(values["spaceBar"])
        self.assertNotIn("nonsense", values)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class MarkerClasses(unittest.TestCase):
    def classes(self, values):
        return js("settings.classes(settings.SCHEMA, values)", values=values)

    def test_compact_bottom_bar_is_a_class_while_on(self):
        self.assertTrue(self.classes({"compactBottomBar": True})["vm-compact-bottom"])
        self.assertFalse(self.classes({"compactBottomBar": False})["vm-compact-bottom"])

    def test_hiding_the_space_bar_is_a_class_while_it_is_off(self):
        self.assertTrue(self.classes({"spaceBar": False})["vm-no-space-bar"])
        self.assertFalse(self.classes({"spaceBar": True})["vm-no-space-bar"])


if __name__ == "__main__":
    unittest.main()
