import shutil
import unittest

from jsrun import run_js


def row(phrase):
    return run_js("20-command-bar.js", "commandBar.suggestionRow(phrase)", phrase=phrase)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the command bar's JavaScript")
class SuggestionRowType(unittest.TestCase):
    def test_navigation_urls_in_suggestions_become_url_rows(self):
        self.assertEqual(row("https://www.diy.com/"),
                         {"type": "url", "url": "https://www.diy.com/", "label": "https://www.diy.com/", "sub": "Open"})
        self.assertEqual(row("http://example.com/"),
                         {"type": "url", "url": "http://example.com/", "label": "http://example.com/", "sub": "Open"})

    def test_phrases_with_dots_remain_search_suggestions(self):
        for phrase in ["node.js", "vue.js", "asp.net"]:
            with self.subTest(phrase=phrase):
                r = row(phrase)
                self.assertEqual(r["type"], "suggest")
                self.assertEqual(r["query"], phrase)



@unittest.skipUnless(shutil.which("node"), "node is needed to test the command bar's JavaScript")
class MoveToSpacePicker(unittest.TestCase):
    SPACES = [{"id": 0, "name": "Home", "emoji": ""}, {"id": 7, "name": "Work", "emoji": "💼"}, {"id": 9, "name": "Reading", "emoji": ""}]

    def pick(self, text):
        return run_js("20-command-bar.js", """(() => {
          window.__vm.moveTargets = () => spaces;
          window.dispatchEvent = () => {};
          globalThis.CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init?.detail; } };
          const moved = [];
          window.__vm.moveTabToSpaceAndGo = async (tabId, id) => { moved.push([tabId, id]); };
          const rows = commandBar.moveToSpacePicker({ id: 42 }).pick(text);
          rows.forEach((r) => r.run());
          return { labels: rows.map((r) => r.label), moved };
        })()""", spaces=self.SPACES, text=text)

    def test_it_lists_the_other_spaces_with_their_emoji(self):
        self.assertEqual(self.pick("")["labels"], ["Home", "💼 Work", "Reading"])

    def test_typing_narrows_the_list_by_name(self):
        self.assertEqual(self.pick("re")["labels"], ["Reading"])
        self.assertEqual(self.pick("WOR")["labels"], ["💼 Work"])

    def test_choosing_a_space_moves_this_tab_there(self):
        self.assertEqual(self.pick("work")["moved"], [[42, 7]])


if __name__ == "__main__":
    unittest.main()
