import shutil
import unittest

from jsrun import run_js

HOUR_MS = 3600 * 1000


def js(expr, **data):
    return run_js("46-update.js", expr, **data)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class IsNewer(unittest.TestCase):
    def test_compares_release_tags_numerically(self):
        self.assertTrue(js('update.isNewer("v0.1.26", "0.1.25")'))
        self.assertTrue(js('update.isNewer("v0.1.10", "0.1.9")'))
        self.assertTrue(js('update.isNewer("v0.2.0", "0.1.25")'))

    def test_an_equal_or_older_release_is_not_newer(self):
        self.assertFalse(js('update.isNewer("v0.1.25", "0.1.25")'))
        self.assertFalse(js('update.isNewer("v0.1.24", "0.1.25")'))

    def test_garbage_is_not_newer(self):
        for tag in (None, "", "latest", "v1.x.0"):
            self.assertFalse(js("update.isNewer(tag, '0.1.25')", tag=tag), tag)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class ShouldCheck(unittest.TestCase):
    NOW = 1_000_000_000_000

    def test_checks_when_it_never_did(self):
        self.assertTrue(js("update.shouldCheck(now, undefined)", now=self.NOW))

    def test_waits_an_hour_between_checks(self):
        self.assertFalse(js("update.shouldCheck(now, now - 59 * m)", now=self.NOW, m=HOUR_MS // 60))
        self.assertTrue(js("update.shouldCheck(now, now - h)", now=self.NOW, h=HOUR_MS))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class PillState(unittest.TestCase):
    RELEASE = {"tag": "v0.1.26", "url": "https://github.com/KASOGIT/vivarc/releases/tag/v0.1.26"}

    def state(self, release, current="0.1.25", dismissed=None):
        return js("update.pillState(release, current, dismissed)", release=release, current=current, dismissed=dismissed)

    def test_shows_a_newer_release(self):
        self.assertEqual(self.state(self.RELEASE), {"show": True, "tag": "v0.1.26", "url": self.RELEASE["url"]})

    def test_hidden_without_a_known_release_or_when_up_to_date(self):
        self.assertFalse(self.state(None)["show"])
        self.assertFalse(self.state(self.RELEASE, current="0.1.26")["show"])
        self.assertFalse(self.state(self.RELEASE, current="0.1.27")["show"])

    def test_later_hides_that_release(self):
        self.assertFalse(self.state(self.RELEASE, dismissed="v0.1.26")["show"])

    def test_a_still_newer_release_shows_again_after_later(self):
        newer = {"tag": "v0.1.27", "url": "https://github.com/KASOGIT/vivarc/releases/tag/v0.1.27"}
        self.assertTrue(self.state(newer, dismissed="v0.1.26")["show"])


if __name__ == "__main__":
    unittest.main()
