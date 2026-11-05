import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("09-recent.js", expr, **data)


def tab(id, accessed, active=False):
    return {"id": id, "lastAccessed": accessed, "active": active}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the tab switcher's JavaScript")
class RecentOrder(unittest.TestCase):
    def test_the_current_tab_comes_first_then_the_others_from_most_to_least_recently_used(self):
        tabs = [tab(1, 100), tab(2, 300), tab(3, 200, active=True), tab(4, 400)]
        self.assertEqual([t["id"] for t in js("recent.order(tabs)", tabs=tabs)], [3, 4, 2, 1])

    def test_a_tab_never_used_goes_last(self):
        tabs = [{"id": 1}, tab(2, 50, active=True), tab(3, 10)]
        self.assertEqual([t["id"] for t in js("recent.order(tabs)", tabs=tabs)], [2, 3, 1])

    def test_only_the_five_most_recent_tabs_are_kept(self):
        tabs = [tab(i, i * 10, active=i == 3) for i in range(1, 9)]
        self.assertEqual([t["id"] for t in js("recent.order(tabs)", tabs=tabs)], [3, 8, 7, 6, 5])

    def test_a_tab_that_becomes_current_pushes_out_the_oldest(self):
        tabs = [tab(i, i * 10) for i in range(1, 7)]
        self.assertEqual([t["id"] for t in js("recent.order(tabs)", tabs=tabs)], [6, 5, 4, 3, 2])
        tabs[0] = tab(1, 70, active=True)
        self.assertEqual([t["id"] for t in js("recent.order(tabs)", tabs=tabs)], [1, 6, 5, 4, 3])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the tab switcher's JavaScript")
class Stepping(unittest.TestCase):
    def test_forward_goes_to_the_next_and_wraps_to_the_first(self):
        self.assertEqual(js("recent.step(1, 1, 4)"), 2)
        self.assertEqual(js("recent.step(3, 1, 4)"), 0)

    def test_backward_wraps_to_the_last(self):
        self.assertEqual(js("recent.step(0, -1, 4)"), 3)
        self.assertEqual(js("recent.step(2, -1, 4)"), 1)

    def test_first_press_goes_to_the_previous_tab_forward_and_to_the_oldest_backward(self):
        self.assertEqual(js("recent.first(1, 5)"), 1)
        self.assertEqual(js("recent.first(-1, 5)"), 4)

    def test_with_a_single_tab_there_is_nothing_to_switch_to(self):
        self.assertIsNone(js("recent.first(1, 1)"))

