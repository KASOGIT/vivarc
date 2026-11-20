import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("11-autohide.js", expr, **data)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Delays(unittest.TestCase):
    def test_the_setting_becomes_vivaldis_close_delay_with_a_shorter_slide(self):
        self.assertEqual(js("autohide.prefs(150)"), {"vivaldi.biscuit.auto_hide_close_delay": 150,
                                                     "vivaldi.biscuit.auto_hide_closing_animation_speed": 150})

    def test_the_slide_never_outlasts_a_short_delay(self):
        self.assertEqual(js("autohide.prefs(100)")["vivaldi.biscuit.auto_hide_closing_animation_speed"], 100)
        self.assertEqual(js("autohide.prefs(1500)")["vivaldi.biscuit.auto_hide_closing_animation_speed"], 150)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Releasable(unittest.TestCase):
    def test_a_clicked_button_gives_up_its_focus(self):
        self.assertTrue(js("autohide.releasable({ tagName: 'BUTTON' })"))
        self.assertTrue(js("autohide.releasable({ tagName: 'DIV' })"))

    def test_a_field_being_typed_in_keeps_it(self):
        for tag in ("INPUT", "TEXTAREA", "SELECT"):
            self.assertFalse(js("autohide.releasable({ tagName: tag })", tag=tag), tag)
        self.assertFalse(js("autohide.releasable({ tagName: 'DIV', isContentEditable: true })"))

    def test_nothing_focused_is_left_alone(self):
        self.assertFalse(js("autohide.releasable(null)"))
        self.assertFalse(js("autohide.releasable({ tagName: 'BODY' })"))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Setting(unittest.TestCase):
    def test_the_delay_is_kept_within_vivaldis_range(self):
        resolve = lambda saved: run_js("01-settings.js", "settings.resolve(settings.SCHEMA, {}, saved)", saved=saved)["hideDelay"]
        self.assertEqual(resolve({}), 150)
        self.assertEqual(resolve({"hideDelay": 400}), 400)
        self.assertEqual(resolve({"hideDelay": 0}), 100)
        self.assertEqual(resolve({"hideDelay": 9000}), 1500)


if __name__ == "__main__":
    unittest.main()
