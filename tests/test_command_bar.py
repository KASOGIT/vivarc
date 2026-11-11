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


if __name__ == "__main__":
    unittest.main()
