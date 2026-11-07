import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("15-search.js", expr, **data)


DDG = {"guid": "ddg-guid", "name": "DuckDuckGo", "keyword": "d", "url": "https://duckduckgo.com/?q={searchTerms}&{ddg:Referral}",
       "suggestUrl": "https://duckduckgo.com/ac/?q={searchTerms}&type=list", "suggestPostParams": ""}
GOOGLE = {"guid": "google-guid", "name": "Google", "keyword": "g",
          "url": "{google:baseURL}search?q={searchTerms}&{google:originalQueryForSuggestion}ie={inputEncoding}",
          "suggestUrl": "https://www.google.com/complete/search?client=chrome&q={searchTerms}", "suggestPostParams": ""}
STARTPAGE = {"guid": "sp-guid", "name": "Startpage", "keyword": "sp", "url": "https://www.startpage.com/sp/search?query=%s",
             "suggestUrl": "", "suggestPostParams": ""}
REPLY = {"templateUrls": [DDG, GOOGLE, STARTPAGE], "defaultSearch": "google-guid", "defaultPrivate": "ddg-guid"}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class DefaultEngine(unittest.TestCase):
    def test_the_engine_picked_in_vivaldi_is_used(self):
        self.assertEqual(js("search.defaultEngine(reply, false).name", reply=REPLY), "Google")

    def test_a_private_window_uses_vivaldis_private_default(self):
        self.assertEqual(js("search.defaultEngine(reply, true).name", reply=REPLY), "DuckDuckGo")

    def test_a_private_window_without_its_own_default_uses_the_normal_one(self):
        self.assertEqual(js("search.defaultEngine(reply, true).name", reply={**REPLY, "defaultPrivate": ""}), "Google")

    def test_no_answer_or_an_unknown_engine_gives_nothing_so_the_fallback_applies(self):
        self.assertIsNone(js("search.defaultEngine(null, false)"))
        self.assertIsNone(js("search.defaultEngine(reply, false)", reply={**REPLY, "defaultSearch": "gone"}))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Fill(unittest.TestCase):
    def test_the_query_is_encoded_and_other_placeholders_dropped(self):
        self.assertEqual(js("search.fill(t, 'a b&c')", t=DDG["url"]), "https://duckduckgo.com/?q=a%20b%26c&")

    def test_percent_s_templates_work_too(self):
        self.assertEqual(js("search.fill(t, 'x')", t=STARTPAGE["url"]), "https://www.startpage.com/sp/search?query=x")

    def test_a_template_only_vivaldi_can_expand_gives_nothing(self):
        self.assertIsNone(js("search.fill(t, 'x')", t=GOOGLE["url"]))

    def test_a_template_without_a_query_or_web_address_gives_nothing(self):
        self.assertIsNone(js("search.fill('https://example.com/', 'x')"))
        self.assertIsNone(js("search.fill('javascript:alert({searchTerms})', 'x')"))
        self.assertIsNone(js("search.fill('', 'x')"))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Suggestions(unittest.TestCase):
    def test_suggestions_come_from_the_default_engine(self):
        self.assertEqual(js("search.suggestUrl(e, 'cats')", e=GOOGLE), "https://www.google.com/complete/search?client=chrome&q=cats")

    def test_an_engine_without_a_suggest_url_sends_nothing_anywhere(self):
        self.assertIsNone(js("search.suggestUrl(e, 'cats')", e=STARTPAGE))
        self.assertIsNone(js("search.suggestUrl(e, 'cats')", e={**GOOGLE, "suggestPostParams": "q={searchTerms}"}))

    def test_opensearch_and_googles_guarded_replies_are_read(self):
        self.assertEqual(js("search.parseSuggestions(t)", t='["cat",["cats","catan"],[],{}]'), ["cats", "catan"])
        self.assertEqual(js("search.parseSuggestions(t)", t=')]}\'\n["cat",["cats"]]'), ["cats"])

    def test_duckduckgos_phrase_list_is_read(self):
        self.assertEqual(js("search.parseSuggestions(t)", t='[{"phrase":"cats"},{"phrase":"catan"}]'), ["cats", "catan"])

    def test_navigation_urls_in_suggestions_are_read(self):
        self.assertEqual(js("search.parseSuggestions(t)", t='["b&q",["b&q near me","https://www.diy.com/"]]'),
                         ["b&q near me", "https://www.diy.com/"])

    def test_garbage_gives_no_suggestions(self):
        self.assertEqual(js("search.parseSuggestions('<html>')"), [])
        self.assertEqual(js("search.parseSuggestions('{}')"), [])


if __name__ == "__main__":
    unittest.main()
