import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vivarc  # noqa: E402

REAL_DEFS = os.path.join(vivarc.DEFAULT_APP, vivarc.RESOURCES, "prefs_definitions.json")
FAKE_DEFS = {"vivaldi": {"actions": {"default_mac": [{
    "COMMAND_NEW_TAB": {"shortcuts": ["meta+t"]},
    "COMMAND_SHOW_QUICK_COMMANDS": {"shortcuts": ["meta+t", "meta+e", "f2"]},
    "COMMAND_PAGE_COPY_URL": {"shortcuts": ["meta+c"]},
}], "default": [{}], "default_linux": [{}]}}}


class InstallFlow(unittest.TestCase):
    """Runs install and uninstall against a fake Vivaldi app and data folder (a fresh-profile simulation)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.app = os.path.join(self.tmp, "Vivaldi.app")
        res = os.path.join(self.app, vivarc.RESOURCES)
        os.makedirs(res)
        with open(os.path.join(res, "prefs_definitions.json"), "w") as f:
            json.dump(FAKE_DEFS, f)
        with open(os.path.join(res, "window.html"), "w") as f:
            f.write("<html><body>\n</body></html>\n")
        self.data = os.path.join(self.tmp, "data")
        for name in ("Default", "Profile 1"):
            os.makedirs(os.path.join(self.data, name))
            with open(os.path.join(self.data, name, "Preferences"), "w") as f:
                json.dump({"vivaldi": {"toolbars": {"tabbar_before": ["TabButton", "Spacer"]}}}, f)
        with open(os.path.join(self.data, "Local State"), "w") as f:
            json.dump({"profile": {"info_cache": {"Default": {"name": "Me"}, "Profile 1": {"name": "Work"}}}}, f)
        self.home = os.path.join(self.tmp, "home")
        patches = [
            mock.patch.object(vivarc, "HOME_DIR", self.home),
            mock.patch.object(vivarc, "vivaldi_running", return_value=False),
            mock.patch.object(vivarc, "app_version", return_value="9.9.9"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_cli(self, *args):
        vivarc.main(["--app", self.app, "--data-dir", self.data, *args])

    def prefs(self, name):
        with open(os.path.join(self.data, name, "Preferences")) as f:
            return json.load(f)

    def test_install_configures_every_profile_and_injects_the_js(self):
        self.run_cli("install", "--no-peek")
        for name in ("Default", "Profile 1"):
            vivaldi = self.prefs(name)["vivaldi"]
            self.assertEqual(vivaldi["toolbars"]["tabbar_before"], ["TabButton"])
            self.assertEqual(vivaldi["appearance"]["css_ui_mods_directory"], os.path.join(self.home, "css"))
            self.assertEqual(vivaldi["actions"][0]["COMMAND_NEW_TAB"]["shortcuts"], [])
        res = os.path.join(self.app, vivarc.RESOURCES)
        with open(os.path.join(res, "window.html")) as f:
            self.assertIn("vivarc.js", f.read())
        with open(os.path.join(res, "vivarc.js")) as f:
            bundle = f.read()
        self.assertIn("[vivarc] core started", bundle)
        self.assertTrue(os.path.exists(os.path.join(self.home, "css", "vivarc.css")))
        with open(os.path.join(self.data, "Local State")) as f:
            self.assertIn("vivaldi-css-mods@1", json.load(f)["browser"]["enabled_labs_experiments"])

    def test_running_install_twice_keeps_the_original_snapshot(self):
        self.run_cli("install", "--no-peek")
        self.run_cli("install", "--no-peek")
        self.run_cli("uninstall")
        self.assertEqual(self.prefs("Default")["vivaldi"]["toolbars"]["tabbar_before"], ["TabButton", "Spacer"])

    def test_uninstall_restores_prefs_flags_and_window_html(self):
        before = self.prefs("Default")
        self.run_cli("install", "--no-peek")
        self.run_cli("uninstall")
        self.assertEqual(self.prefs("Default"), before)
        res = os.path.join(self.app, vivarc.RESOURCES)
        with open(os.path.join(res, "window.html")) as f:
            self.assertNotIn("vivarc", f.read())
        self.assertFalse(os.path.exists(os.path.join(res, "vivarc.js")))
        with open(os.path.join(self.data, "Local State")) as f:
            self.assertEqual(json.load(f)["browser"]["enabled_labs_experiments"], [])

    def test_bundle_tells_the_js_where_the_css_lives(self):
        self.run_cli("install", "--no-peek")
        res = os.path.join(self.app, vivarc.RESOURCES)
        with open(os.path.join(res, "vivarc.js")) as f:
            self.assertIn(json.dumps(os.path.join(self.home, "css")), f.read())

    def test_install_puts_the_guide_page_in_place_and_tells_the_js_its_url(self):
        self.run_cli("install", "--no-peek")
        page = os.path.join(self.home, "start", "index.html")
        self.assertTrue(os.path.exists(page))
        res = os.path.join(self.app, vivarc.RESOURCES)
        with open(os.path.join(res, "vivarc.js")) as f:
            self.assertIn(json.dumps(pathlib.Path(page).as_uri()), f.read())

    def test_uninstall_also_cleans_profiles_the_js_configured_on_its_own(self):
        self.run_cli("install", "--no-peek", "--profiles", "Default")
        # "Profile 1" was configured at runtime by the JS: our css dir and defaults-based keys, no snapshot
        path = os.path.join(self.data, "Profile 1", "Preferences")
        with open(path, "w") as f:
            json.dump({"vivaldi": {"appearance": {"css_ui_mods_directory": os.path.join(self.home, "css")},
                                   "tabs": {"bar": {"position": 1}}, "actions": [{"COMMAND_NEW_TAB": {"shortcuts": []}}]}}, f)
        self.run_cli("uninstall")
        self.assertEqual(self.prefs("Profile 1"), {})

    def test_apply_alone_also_puts_the_stylesheet_in_place(self):
        self.run_cli("apply")
        self.assertTrue(os.path.exists(os.path.join(self.home, "css", "vivarc.css")))

    def test_refuses_to_run_while_vivaldi_is_open(self):
        with mock.patch.object(vivarc, "vivaldi_running", return_value=True):
            with self.assertRaises(SystemExit):
                self.run_cli("install", "--no-peek")

    def test_skips_a_profile_that_already_uses_css_mods_unless_forced(self):
        path = os.path.join(self.data, "Default", "Preferences")
        with open(path, "w") as f:
            json.dump({"vivaldi": {"appearance": {"css_ui_mods_directory": "/other"}}}, f)
        self.run_cli("install", "--no-peek")
        self.assertEqual(self.prefs("Default")["vivaldi"]["appearance"]["css_ui_mods_directory"], "/other")
        self.run_cli("install", "--no-peek", "--force")
        self.assertEqual(self.prefs("Default")["vivaldi"]["appearance"]["css_ui_mods_directory"],
                         os.path.join(self.home, "css"))


if __name__ == "__main__":
    unittest.main()
