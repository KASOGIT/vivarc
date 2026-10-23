import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("06-spaces.js", expr, **data)


def profile(name, path, active=False, guest=False, **extra):
    return {"name": name, "path": path, "active": active, "guest": guest, "image": "img-" + name, **extra}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class ProfileChips(unittest.TestCase):
    def chips(self, profiles):
        return js("spaces.profileChips(profiles)", profiles=profiles)

    def test_a_single_profile_needs_no_switcher(self):
        self.assertEqual(self.chips([profile("Solo", "/p/1", active=True)]), [])

    def test_guest_profiles_are_left_out(self):
        chips = self.chips([profile("A", "/p/1", active=True), profile("B", "/p/2"), profile("Guest", "/p/g", guest=True)])
        self.assertEqual([c["name"] for c in chips], ["A", "B"])

    def test_every_other_profile_is_listed_with_the_active_one_marked_and_sorted_by_name(self):
        chips = self.chips([profile("zeta", "/p/3"), profile("Alpha", "/p/1"), profile("Mid", "/p/2", active=True)])
        self.assertEqual([(c["name"], c["active"]) for c in chips], [("Alpha", False), ("Mid", True), ("zeta", False)])

    def test_profiles_with_the_same_name_stay_distinct_by_path(self):
        chips = self.chips([profile("Work", "/p/1", active=True), profile("Work", "/p/2")])
        self.assertEqual([c["path"] for c in chips], ["/p/1", "/p/2"])

    def test_a_custom_avatar_wins_over_the_stock_image(self):
        chips = self.chips([profile("A", "/p/1", active=True, customAvatar="custom"), profile("B", "/p/2")])
        self.assertEqual([c["avatar"] for c in chips], ["custom", "img-B"])

    def test_each_chip_has_a_letter_and_a_stable_colour_for_when_the_avatar_does_not_load(self):
        chips = self.chips([profile("creacard", "/p/1", active=True), profile("Perso", "/p/2")])
        self.assertEqual([c["letter"] for c in chips], ["C", "P"])
        again = self.chips([profile("creacard", "/p/1", active=True), profile("Perso", "/p/2")])
        self.assertEqual([c["hue"] for c in chips], [c["hue"] for c in again])
        self.assertNotEqual(chips[0]["hue"], chips[1]["hue"])

    def test_the_nth_shortcut_picks_the_nth_chip_unless_it_is_the_active_profile(self):
        profiles = [profile("A", "/p/1"), profile("B", "/p/2", active=True), profile("C", "/p/3")]
        self.assertEqual(js("spaces.pathForShortcut(profiles, 'ctrl+meta+3')", profiles=profiles), "/p/3")
        self.assertIsNone(js("spaces.pathForShortcut(profiles, 'ctrl+meta+2')", profiles=profiles))
        self.assertIsNone(js("spaces.pathForShortcut(profiles, 'ctrl+meta+9')", profiles=profiles))
        self.assertIsNone(js("spaces.pathForShortcut(profiles, 'meta+3')", profiles=profiles))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class AccountButton(unittest.TestCase):
    def test_the_button_is_wanted_only_when_there_are_no_chips_to_replace_it(self):
        two = [profile("A", "/p/1", active=True), profile("B", "/p/2")]
        self.assertFalse(js("spaces.wantsAccountButton(profiles)", profiles=two))
        self.assertTrue(js("spaces.wantsAccountButton(profiles)", profiles=two[:1]))
        self.assertTrue(js("spaces.wantsAccountButton(profiles)", profiles=[]))

    BOTTOM = ["NewTab", "FlexibleSpacer", "AccountButton", "FlexibleSpacer", "PanelDownloads", "UpdateButton"]

    def test_the_account_button_leaves_the_bottom_toolbar_when_the_chips_replace_it(self):
        out = js("spaces.withAccountButton(list, false)", list=self.BOTTOM)
        self.assertEqual(out, ["NewTab", "FlexibleSpacer", "FlexibleSpacer", "PanelDownloads", "UpdateButton"])

    def test_it_comes_back_where_it_was_when_there_is_one_profile_again(self):
        gone = ["NewTab", "FlexibleSpacer", "FlexibleSpacer", "PanelDownloads", "UpdateButton"]
        self.assertEqual(js("spaces.withAccountButton(list, true)", list=gone), self.BOTTOM)

    def test_a_list_that_is_already_right_is_returned_unchanged(self):
        self.assertEqual(js("spaces.withAccountButton(list, true)", list=self.BOTTOM), self.BOTTOM)
        gone = ["NewTab", "FlexibleSpacer", "PanelDownloads"]
        self.assertEqual(js("spaces.withAccountButton(list, false)", list=gone), gone)

    def test_without_a_spacer_it_goes_first(self):
        self.assertEqual(js("spaces.withAccountButton(list, true)", list=["PanelDownloads"]), ["AccountButton", "PanelDownloads"])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class DownloadsButton(unittest.TestCase):
    def test_a_list_without_downloads_gets_it_before_the_update_button(self):
        out = js("spaces.withDownloads(list)", list=["NewTab", "FlexibleSpacer", "FlexibleSpacer", "UpdateButton"])
        self.assertEqual(out, ["NewTab", "FlexibleSpacer", "FlexibleSpacer", "PanelDownloads", "UpdateButton"])

    def test_without_an_update_button_it_goes_last(self):
        out = js("spaces.withDownloads(list)", list=["NewTab", "FlexibleSpacer"])
        self.assertEqual(out, ["NewTab", "FlexibleSpacer", "PanelDownloads"])

    def test_a_list_that_already_has_it_is_returned_unchanged(self):
        both = ["NewTab", "PanelDownloads", "UpdateButton"]
        self.assertEqual(js("spaces.withDownloads(list)", list=both), both)


if __name__ == "__main__":
    unittest.main()
