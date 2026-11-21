import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import arc_import  # noqa: E402


def tab(item_id, url, title):
    return {"id": item_id, "title": title, "data": {"tab": {"savedURL": url, "savedTitle": title}}, "childrenIds": []}


SIDEBAR = {"sidebar": {"containers": [{}, {
    "items": [
        {"id": "pinned", "data": {"list": {}}, "childrenIds": ["f1", "t1"]},
        {"id": "unpinned", "data": {"list": {}}, "childrenIds": ["t3"]},
        {"id": "fav", "data": {"list": {}}, "childrenIds": ["t4"]},
        {"id": "f1", "title": "Work", "data": {"list": {}}, "childrenIds": ["t2"]},
        tab("t1", "https://a.example/x", "A & B"),
        tab("t2", "https://b.example/", "B"),
        tab("t3", "https://c.example/", "C"),
        tab("t4", "https://mail.example/", "Mail"),
    ],
    "spaces": [{"title": "Home", "profile": "p1", "newContainerIDs": ["pinned", "unpinned"]}],
    "topAppsContainerIDs": ["p1", "fav"],
}]}}


class ProfileMarkers(unittest.TestCase):
    def test_accepts_dict_profile_markers_like_arcs_default_profile(self):
        sidebar = {"sidebar": {"containers": [{"spaces": [{"title": "S", "profile": {"default": True},
                                                          "newContainerIDs": ["p", "u"]}],
                                               "items": [{"id": "p", "data": {"list": {}}, "childrenIds": []},
                                                         {"id": "u", "data": {"list": {}}, "childrenIds": []},
                                                         {"id": "f", "data": {"list": {}}, "childrenIds": ["t"]},
                                                         tab("t", "https://x.example/", "X")],
                                               "topAppsContainerIDs": [{"default": True}, "f"]}]}}
        text, urls = arc_import.spaces_to_html(sidebar)["S"]
        self.assertEqual(urls, ["https://x.example/"])


class ContainerMarkers(unittest.TestCase):
    """Arc tags each container id with the marker before it, and can list the unpinned one first."""
    def setUp(self):
        sidebar = {"sidebar": {"containers": [{}, {
            "items": [
                {"id": "U", "data": {"list": {}}, "childrenIds": ["today"]},
                {"id": "P", "data": {"list": {}}, "childrenIds": ["kept"]},
                tab("today", "https://today.example/", "Today"),
                tab("kept", "https://kept.example/", "Kept"),
            ],
            "spaces": [{"title": "S", "profile": "p1",
                        "newContainerIDs": [{"unpinned": {"_0": {"shared": {}}}}, "U", {"pinned": {}}, "P"]}],
            "topAppsContainerIDs": [],
        }]}}
        self.text, _ = arc_import.spaces_to_html(sidebar)["S"]

    def section(self, heading):
        start = self.text.index(f"<H3>{heading}</H3>")
        return self.text[start:self.text.index("</DL><p>", start)]

    def test_the_pinned_marker_picks_the_pinned_folder_even_when_unpinned_comes_first(self):
        self.assertIn("https://kept.example/", self.section("Pinned"))
        self.assertNotIn("https://today.example/", self.section("Pinned"))

    def test_the_unpinned_marker_picks_the_unpinned_folder(self):
        self.assertIn("https://today.example/", self.section("Unpinned (today)"))

    def test_the_pinned_marker_first_is_read_the_same_way(self):
        ids = [{"pinned": {}}, "P", {"unpinned": {"_0": {"shared": {}}}}, "U"]
        self.assertEqual(arc_import.containers(ids), {"pinned": "P", "unpinned": "U"})

    def test_a_single_marker_gives_the_other_role_to_the_other_id(self):
        self.assertEqual(arc_import.containers([{"unpinned": {}}, "U", "P"]), {"pinned": "P", "unpinned": "U"})
        self.assertEqual(arc_import.containers(["U", {"pinned": {}}, "P"]), {"pinned": "P", "unpinned": "U"})


class ArcImport(unittest.TestCase):
    def setUp(self):
        self.text, self.urls = arc_import.spaces_to_html(SIDEBAR)["Home"]

    def test_wraps_the_space_in_an_arc_folder_with_favorites_pinned_and_unpinned(self):
        for heading in ("Arc - Home", "Favorites", "Pinned", "Unpinned (today)"):
            self.assertIn(f"<H3>{heading}</H3>", self.text)

    def test_keeps_the_folder_tree_and_escapes_titles(self):
        self.assertIn("<H3>Work</H3>", self.text)
        self.assertIn('<A HREF="https://a.example/x">A &amp; B</A>', self.text)
        self.assertLess(self.text.index("<H3>Work</H3>"), self.text.index("https://b.example/"))

    def test_lists_every_link_once(self):
        self.assertCountEqual(self.urls, ["https://mail.example/", "https://a.example/x", "https://b.example/", "https://c.example/"])

    def test_origin_strips_the_path(self):
        self.assertEqual(arc_import.origin("https://a.example/x?y=1"), "https://a.example")
        self.assertEqual(arc_import.origin("not a url"), "")


if __name__ == "__main__":
    unittest.main()
