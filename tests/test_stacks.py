import json
import shutil
import unittest

from jsrun import run_js


def tab(id, index, group=None, title=None):
    ext = {"group": group} if group else {}
    if title:
        ext["fixedGroupTitle"] = title
    return {"id": id, "index": index, "title": f"t{id}", "vivExtData": json.dumps(ext)}


def layout(tabs):
    return run_js("09-stacks.js", "window.__vm.stacks.layout(tabs).map((e) => e.type === 'stack' ? [e.id, e.tabs.map((t) => t.id)] : e.tab.id)", tabs=tabs)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the stacks' JavaScript")
class Stacks(unittest.TestCase):
    def test_a_stack_is_listed_where_its_newest_tab_would_be_with_its_tabs_oldest_first(self):
        tabs = [tab(1, 0), tab(2, 1, "g"), tab(3, 2), tab(4, 3, "g"), tab(5, 4)]
        self.assertEqual(layout(tabs), [5, ["g", [2, 4]], 3, 1])

    def test_a_stack_of_one_tab_is_shown_as_a_plain_tab(self):
        self.assertEqual(layout([tab(1, 0, "g"), tab(2, 1)]), [2, 1])

    def test_the_stack_name_is_vivaldis_own_title_when_set(self):
        self.assertEqual(run_js("09-stacks.js", "window.__vm.stacks.nameOf(tabs)", tabs=[tab(1, 0, "g"), tab(2, 1, "g", "Reading")]), "Reading")
        self.assertEqual(run_js("09-stacks.js", "window.__vm.stacks.nameOf(tabs)", tabs=[tab(1, 0, "g")]), "")

    def test_unreadable_data_is_a_loose_tab(self):
        self.assertEqual(run_js("09-stacks.js", "window.__vm.stacks.groupOf({ vivExtData: 'not json' })"), "")

    def test_shift_click_takes_every_tab_between_the_anchor_and_the_click(self):
        self.assertEqual(run_js("09-stacks.js", "window.__vm.stacks.range([5, 4, 3, 2, 1], 2, 4)"), [4, 3, 2])
        self.assertEqual(run_js("09-stacks.js", "window.__vm.stacks.range([5, 4, 3], 9, 4)"), [4])
