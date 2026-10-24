import json
import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("08-pins.js", expr, **data)


def tab(id, url, index=0, active=False, ext=None, status="complete"):
    return {"id": id, "url": url, "index": index, "active": active, "status": status,
            "vivExtData": json.dumps(ext) if ext is not None else ""}


def plan(tabs, pin_list):
    return js("(() => { const r = pins.plan(tabs, list); return { bound: [...r.bound].map(([p, t]) => [p, t.id]), writes: r.writes }; })()",
              tabs=tabs, list=pin_list)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Binding(unittest.TestCase):
    PIN = {"id": "p1", "url": "https://git.example.com/org/repo/actions"}

    def test_a_bound_tab_stays_on_its_pin_wherever_it_navigates(self):
        away = tab(1, "https://git.example.com/org/settings/members", ext={"vivarcPin": "p1"})
        result = plan([away], [self.PIN])
        self.assertEqual(result["bound"], [["p1", 1]])
        self.assertEqual(result["writes"], [])

    def test_a_tab_on_another_site_stays_bound_too(self):
        away = tab(1, "https://other.example.org/", ext={"vivarcPin": "p1"})
        self.assertEqual(plan([away], [self.PIN])["bound"], [["p1", 1]])

    def test_an_unbound_tab_on_the_pinned_page_gets_bound_and_its_landing_url_remembered(self):
        result = plan([tab(1, "https://git.example.com/org/repo/actions/runs/1")], [self.PIN])
        self.assertEqual(result["bound"], [["p1", 1]])
        self.assertEqual(result["writes"], [{"tabId": 1, "patch": {
            "vivarcPin": "p1", "vivarcHome": "https://git.example.com/org/repo/actions/runs/1"}}])

    def test_a_tab_still_loading_is_bound_without_a_landing_url(self):
        result = plan([tab(1, "https://git.example.com/org/repo/actions", status="loading")], [self.PIN])
        self.assertEqual(result["writes"], [{"tabId": 1, "patch": {"vivarcPin": "p1"}}])

    def test_a_bound_tab_without_a_landing_url_gets_one_once_it_has_loaded_on_the_pinned_site(self):
        loaded = tab(1, "https://git.example.com/org/repo/actions/runs/1", ext={"vivarcPin": "p1"})
        self.assertEqual(plan([loaded], [self.PIN])["writes"], [{"tabId": 1, "patch": {
            "vivarcHome": "https://git.example.com/org/repo/actions/runs/1"}}])

    def test_a_bound_tab_that_is_still_loading_or_elsewhere_gets_no_landing_url_yet(self):
        loading = tab(1, "https://git.example.com/org/repo/actions", ext={"vivarcPin": "p1"}, status="loading")
        elsewhere = tab(2, "https://other.example.org/", ext={"vivarcPin": "p2"})
        pin_list = [self.PIN, {"id": "p2", "url": "https://git.example.com/other"}]
        self.assertEqual(plan([loading, elsewhere], pin_list)["writes"], [])

    def test_the_longest_matching_pin_wins(self):
        pin_list = [{"id": "short", "url": "https://x.example.com/a"}, {"id": "long", "url": "https://x.example.com/a/b"}]
        result = plan([tab(1, "https://x.example.com/a/b/c")], pin_list)
        self.assertEqual(result["bound"], [["long", 1]])

    def test_the_active_tab_is_preferred_when_two_tabs_match_one_pin(self):
        tabs = [tab(1, "https://git.example.com/org/repo/actions", index=0),
                tab(2, "https://git.example.com/org/repo/actions", index=1, active=True)]
        self.assertEqual(plan(tabs, [self.PIN])["bound"], [["p1", 2]])

    def test_a_second_tab_on_an_occupied_pin_is_left_alone(self):
        tabs = [tab(1, "https://elsewhere.example.com/", ext={"vivarcPin": "p1"}),
                tab(2, "https://git.example.com/org/repo/actions", index=1)]
        result = plan(tabs, [self.PIN])
        self.assertEqual(result["bound"], [["p1", 1]])
        self.assertEqual(result["writes"], [])

    def test_a_key_pointing_at_a_pin_that_is_gone_is_cleared(self):
        orphan = tab(1, "https://elsewhere.example.com/", ext={"vivarcPin": "trashed", "vivarcHome": "https://x"})
        result = plan([orphan], [self.PIN])
        self.assertEqual(result["bound"], [])
        self.assertEqual(result["writes"], [{"tabId": 1, "patch": {"vivarcPin": None, "vivarcHome": None}}])

    def test_when_two_tabs_claim_one_pin_the_first_one_keeps_it(self):
        tabs = [tab(1, "https://a.example.com/", index=0, ext={"vivarcPin": "p1"}),
                tab(2, "https://b.example.com/", index=1, active=True, ext={"vivarcPin": "p1"})]
        result = plan(tabs, [self.PIN])
        self.assertEqual(result["bound"], [["p1", 1]])
        self.assertEqual([w["tabId"] for w in result["writes"]], [2])

    def test_without_any_pins_nothing_is_cleared(self):
        result = plan([tab(1, "https://a.example.com/", ext={"vivarcPin": "p1"})], [])
        self.assertEqual(result, {"bound": [], "writes": []})

    def test_planning_again_after_the_writes_changes_nothing(self):
        first = [tab(1, "https://git.example.com/org/repo/actions")]
        writes = plan(first, [self.PIN])["writes"]
        settled = [tab(1, first[0]["url"], ext=writes[0]["patch"])]
        self.assertEqual(plan(settled, [self.PIN])["writes"], [])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class AcrossSpaces(unittest.TestCase):
    HERE = {"id": "here", "url": "https://git.example.com/org/repo/actions"}
    ELSEWHERE = {"id": "there", "url": "https://other.example.com/"}

    def plan(self, tabs):
        return js("(() => { const r = pins.plan(tabs, list, all); return { bound: [...r.bound].map(([p, t]) => [p, t.id]), writes: r.writes }; })()",
                  tabs=tabs, list=[self.HERE], all=["here", "there"])

    def test_a_tab_bound_to_a_pin_of_another_space_keeps_its_binding(self):
        result = self.plan([tab(1, "https://other.example.com/", ext={"vivarcPin": "there"})])
        self.assertEqual(result, {"bound": [], "writes": []})

    def test_a_tab_is_still_cleared_when_its_pin_is_in_no_space_at_all(self):
        result = self.plan([tab(1, "https://x.example.com/", ext={"vivarcPin": "gone"})])
        self.assertEqual(result["writes"], [{"tabId": 1, "patch": {"vivarcPin": None, "vivarcHome": None}}])

    def test_pins_of_this_space_still_bind_normally(self):
        result = self.plan([tab(1, "https://git.example.com/org/repo/actions/runs/1")])
        self.assertEqual(result["bound"], [["here", 1]])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class ExtData(unittest.TestCase):
    def test_binding_keeps_the_keys_vivaldi_stores_in_the_same_field(self):
        t = tab(1, "https://x.example.com/", ext={"workspaceId": 7, "tiling": {"id": "t"}})
        merged = json.loads(js("pins.patched(t, { vivarcPin: 'p1' })", t=t))
        self.assertEqual(merged, {"workspaceId": 7, "tiling": {"id": "t"}, "vivarcPin": "p1"})

    def test_an_undefined_patch_value_removes_the_key(self):
        t = tab(1, "https://x.example.com/", ext={"workspaceId": 7, "vivarcPin": "p1"})
        merged = json.loads(js("pins.patched(t, { vivarcPin: undefined })", t=t))
        self.assertEqual(merged, {"workspaceId": 7})

    def test_a_write_is_only_needed_when_something_changes(self):
        t = tab(1, "https://x.example.com/", ext={"vivarcPin": "p1"})
        self.assertFalse(js("pins.needsWrite(t, { vivarcPin: 'p1' })", t=t))
        self.assertTrue(js("pins.needsWrite(t, { vivarcPin: 'p2' })", t=t))
        self.assertFalse(js("pins.needsWrite(t, { vivarcHome: undefined })", t=t))
        self.assertTrue(js("pins.needsWrite(t, { vivarcPin: undefined })", t=t))

    def test_unreadable_data_counts_as_empty(self):
        t = {"id": 1, "url": "https://x.example.com/", "vivExtData": "not json"}
        self.assertIsNone(js("pins.pinOf(t)", t=t))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class AtHome(unittest.TestCase):
    def away(self, tab_url, pin_url, home=None):
        t = tab(1, tab_url, ext={"vivarcPin": "p", **({"vivarcHome": home} if home else {})})
        return js("pins.away(t, pinUrl)", t=t, pinUrl=pin_url)

    def test_a_tab_whose_landing_page_is_not_known_yet_is_never_away(self):
        self.assertFalse(self.away("https://www.example.org/en/redirected-while-loading", "https://www.example.org/"))

    def test_the_pinned_url_itself_is_home_even_with_a_trailing_slash_or_a_hash(self):
        self.assertFalse(self.away("https://docs.example.com/page/", "https://docs.example.com/page"))
        self.assertFalse(self.away("https://docs.example.com/page#section", "https://docs.example.com/page"))

    def test_a_site_that_redirects_off_the_root_is_home_at_its_landing_page(self):
        pin = "https://mail.example.com/"
        home = "https://mail.example.com/mail/u/0"
        self.assertFalse(self.away("https://mail.example.com/mail/u/0/#inbox/abc", pin, home))
        self.assertFalse(self.away("https://mail.example.com/mail/u/0/", pin, home))

    def test_another_page_of_the_site_is_away(self):
        self.assertTrue(self.away("https://video.example.com/watch?v=1", "https://video.example.com/", "https://video.example.com"))
        self.assertTrue(self.away("https://mail.example.com/settings", "https://mail.example.com/", "https://mail.example.com/mail/u/0"))

    def test_a_different_query_counts_as_away(self):
        self.assertTrue(self.away("https://git.example.com/org/repo/actions?query=x", "https://git.example.com/org/repo/actions",
                                  "https://git.example.com/org/repo/actions"))

    def test_another_site_is_away(self):
        self.assertTrue(self.away("https://other.example.org/", "https://docs.example.com/page", "https://docs.example.com/page"))


if __name__ == "__main__":
    unittest.main()
