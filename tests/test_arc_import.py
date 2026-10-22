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
