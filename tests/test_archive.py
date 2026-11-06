import shutil
import unittest

from jsrun import run_js

HOUR = 3600 * 1000
NOW = 1_000 * HOUR


def stale(tabs, hours=12):
    return [t["id"] for t in run_js("12-archive.js", "archive.stale(tabs, now, hours, (t) => !!t.keep)", tabs=tabs, now=NOW, hours=hours)]


def tab(id, idle_hours, **extra):
    return {"id": id, "lastAccessed": NOW - idle_hours * HOUR, **extra}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the tab archive's JavaScript")
class Stale(unittest.TestCase):
    def test_a_tab_idle_longer_than_the_limit_is_stale(self):
        self.assertEqual(stale([tab(1, 13), tab(2, 11), tab(3, 30)]), [1, 3])

    def test_the_limit_follows_the_setting(self):
        self.assertEqual(stale([tab(1, 3), tab(2, 1)], hours=2), [1])

    def test_a_tab_idle_for_exactly_the_limit_is_kept(self):
        self.assertEqual(stale([tab(1, 12)]), [])

    def test_the_active_tab_is_never_stale(self):
        self.assertEqual(stale([tab(1, 50, active=True), tab(2, 50)]), [2])

    def test_a_vivaldi_pinned_tab_is_kept(self):
        self.assertEqual(stale([tab(1, 50, pinned=True)]), [])

    def test_a_tab_playing_sound_is_kept(self):
        self.assertEqual(stale([tab(1, 50, audible=True)]), [])

    def test_a_tab_the_caller_wants_kept_is_kept(self):
        self.assertEqual(stale([tab(1, 50, keep=True), tab(2, 50)]), [2])

    def test_a_tab_without_a_last_access_time_is_kept(self):
        self.assertEqual(stale([{"id": 1}]), [])
