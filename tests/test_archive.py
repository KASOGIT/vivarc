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


def archive(expr, **data):
    return run_js("12-archive.js", expr, **data)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the tab archive's JavaScript")
class ArchivedTabs(unittest.TestCase):
    def test_an_entry_keeps_the_page_its_space_and_only_a_safe_favicon(self):
        e = archive("""(() => { window.__vm.workspaces = { of: (t) => t.ws || 0 };
          return archive.entry({ url: "https://a.com/x", title: "A", favIconUrl: "chrome://favicon/x", ws: 7 }, "Work", 1000); })()""")
        self.assertEqual((e["url"], e["title"], e["space"], e["spaceName"], e["at"], e["favicon"]),
                         ("https://a.com/x", "A", 7, "Work", 1000, ""))

    def test_new_entries_go_first_and_one_address_per_space_is_kept(self):
        ids = archive("""archive.add([{ id: "1", url: "u1", space: 0 }, { id: "2", url: "u2", space: 0 }, { id: "3", url: "u1", space: 5 }],
          [{ id: "4", url: "u1", space: 0 }]).map((e) => e.id)""")
        self.assertEqual(ids, ["4", "2", "3"])  # u1 in space 0 moved to the top; u1 in space 5 is another entry

    def test_the_archive_keeps_at_most_1000_pages_dropping_the_oldest(self):
        self.assertEqual(archive("archive.MAX"), 1000)
        out = archive("""(() => {
          const old = Array.from({ length: 1000 }, (_, i) => ({ id: "old" + i, url: "https://a.com/" + i, space: 0 }));
          const list = archive.add(old, [{ id: "new", url: "https://b.com/", space: 0 }]);
          return [list.length, list[0].id, list.at(-1).id];
        })()""")
        self.assertEqual(out, [1000, "new", "old998"])

    def test_search_matches_every_word_in_title_address_or_space(self):
        ids = archive("""archive.search([
          { id: "a", title: "Figma file", url: "https://figma.com/1", spaceName: "Design" },
          { id: "b", title: "Docs", url: "https://docs.google.com", spaceName: "Work" },
          { id: "c", title: "Figma community", url: "https://figma.com/c", spaceName: "Work" }], "figma work").map((e) => e.id)""")
        self.assertEqual(ids, ["c"])

    def test_each_row_says_the_site_the_space_and_when(self):
        m = 60000
        self.assertEqual(archive(f"archive.ago(0, {30 * 1000})"), "just now")
        self.assertEqual(archive(f"archive.ago(0, {3 * 60 * m})"), "3 h ago")
        self.assertEqual(archive(f"archive.ago(0, {30 * 60 * m})"), "yesterday")
        self.assertEqual(archive(f'archive.describe({{ url: "https://www.a.com/x", spaceName: "Work", at: 0 }}, {5 * m})'),
                         "a.com · Work · 5 min ago")
