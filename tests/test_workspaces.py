import json
import shutil
import unittest

from jsrun import run_js


def js(expr, **data):
    return run_js("07-workspaces.js", expr, **data)


def tab(id, workspace=None, index=0, active=False, accessed=None):
    t = {"id": id, "index": index, "active": active, "vivExtData": json.dumps({"workspaceId": workspace} if workspace else {})}
    if accessed is not None:
        t["lastAccessed"] = accessed
    return t


WORK = {"id": 1792776132092, "name": "Work", "emoji": "📚", "icon": "<svg/>"}
SIDE = {"id": 1792856044277, "name": "Side", "emoji": "🎁", "icon": "<svg/>"}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class WhichSpace(unittest.TestCase):
    def test_a_tab_belongs_to_the_workspace_vivaldi_stored_in_its_data(self):
        self.assertEqual(js("workspaces.of(t)", t=tab(1, WORK["id"])), WORK["id"])

    def test_a_tab_without_a_workspace_is_in_the_default_space(self):
        self.assertEqual(js("workspaces.of(t)", t=tab(1)), 0)
        self.assertEqual(js("workspaces.of({ vivExtData: 'not json' })"), 0)
        self.assertEqual(js("workspaces.of({})"), 0)

    def test_the_active_tab_decides_the_active_space(self):
        tabs = [tab(1, active=True), tab(2, WORK["id"]), tab(3, SIDE["id"])]
        self.assertEqual(js("workspaces.activeId(tabs)", tabs=tabs), 0)
        tabs = [tab(1), tab(2, WORK["id"], active=True)]
        self.assertEqual(js("workspaces.activeId(tabs)", tabs=tabs), WORK["id"])

    def test_without_an_active_tab_the_default_space_is_active(self):
        self.assertEqual(js("workspaces.activeId(tabs)", tabs=[tab(1, WORK["id"])]), 0)

    def test_tabs_in_a_space_are_only_that_spaces_tabs(self):
        tabs = [tab(1), tab(2, WORK["id"]), tab(3, SIDE["id"]), tab(4, WORK["id"])]
        self.assertEqual([t["id"] for t in js("workspaces.tabsIn(tabs, id)", tabs=tabs, id=WORK["id"])], [2, 4])
        self.assertEqual([t["id"] for t in js("workspaces.tabsIn(tabs, 0)", tabs=tabs)], [1])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Scope(unittest.TestCase):
    TABS = [tab(1, active=True), tab(2, WORK["id"]), tab(3, WORK["id"], index=1), tab(4, SIDE["id"])]

    def scope(self, tabs, workspaces):
        return js("workspaces.scope(tabs, list)", tabs=tabs, list=workspaces)

    def test_the_sidebar_shows_only_the_tabs_of_the_active_space(self):
        got = self.scope(self.TABS, [WORK, SIDE])
        self.assertEqual((got["active"], [t["id"] for t in got["tabs"]]), (0, [1]))
        tabs = [{**t, "active": t["id"] == 3} for t in self.TABS]
        got = self.scope(tabs, [WORK, SIDE])
        self.assertEqual((got["active"], [t["id"] for t in got["tabs"]]), (WORK["id"], [2, 3]))

    def test_when_the_workspace_list_is_unknown_every_tab_is_shown_so_nothing_looks_lost(self):
        got = self.scope(self.TABS, [])
        self.assertEqual((got["active"], [t["id"] for t in got["tabs"]]), (0, [1, 2, 3, 4]))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class SpaceList(unittest.TestCase):
    def items(self, workspaces):
        return js("workspaces.items(list, 'Home')", list=workspaces)

    def test_a_profile_without_workspaces_has_no_space_bar(self):
        self.assertEqual(self.items([]), [])
        self.assertEqual(js("workspaces.items(undefined, 'Home')"), [])

    def test_the_default_space_comes_first_followed_by_the_workspaces_in_vivaldis_order(self):
        items = self.items([WORK, SIDE])
        self.assertEqual([(i["id"], i["name"]) for i in items], [(0, "Home"), (WORK["id"], "Work"), (SIDE["id"], "Side")])

    def test_each_space_keeps_its_emoji_and_the_default_has_none(self):
        self.assertEqual([i["emoji"] for i in self.items([WORK])], ["", "📚"])

    def test_the_most_recently_used_tab_of_a_space_is_where_switching_goes(self):
        tabs = [tab(1, WORK["id"], accessed=100), tab(2, WORK["id"], accessed=300), tab(3, WORK["id"], accessed=200), tab(4, accessed=900)]
        self.assertEqual(js("workspaces.recentTab(tabs, id).id", tabs=tabs, id=WORK["id"]), 2)

    def test_without_access_times_the_last_tab_of_the_space_is_used(self):
        tabs = [tab(1, WORK["id"], index=0), tab(2, WORK["id"], index=5), tab(3, WORK["id"], index=2)]
        self.assertEqual(js("workspaces.recentTab(tabs, id).id", tabs=tabs, id=WORK["id"]), 2)

    def test_an_empty_space_has_no_tab_to_switch_to(self):
        self.assertIsNone(js("workspaces.recentTab(tabs, id)", tabs=[tab(1)], id=WORK["id"]))


def folder(id, title):
    return {"id": id, "title": title}


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class Folders(unittest.TestCase):
    def assign(self, folders, workspaces):
        return js("workspaces.assign(folders, list)", folders=folders, list=workspaces)

    def test_a_workspace_gets_the_pinned_folder_with_its_name_even_with_arcs_prefix_and_other_case(self):
        folders = [folder("a", "Vivarc"), folder("b", "Arc - work")]
        got = self.assign(folders, [WORK])
        self.assertEqual(got["byId"][str(WORK["id"])]["id"], "b")
        self.assertEqual(got["default"]["id"], "a")

    def test_the_default_space_is_the_first_folder_no_workspace_claims(self):
        folders = [folder("a", "Arc - Work"), folder("b", "Arc - Home"), folder("c", "Arc - Side")]
        got = self.assign(folders, [WORK, SIDE])
        self.assertEqual(got["default"]["id"], "b")
        self.assertEqual({k: v["id"] for k, v in got["byId"].items()}, {str(WORK["id"]): "a", str(SIDE["id"]): "c"})

    def test_a_workspace_without_a_folder_has_none_yet(self):
        got = self.assign([folder("a", "Vivarc")], [WORK])
        self.assertEqual(got["byId"], {})

    def test_with_no_workspaces_the_first_folder_is_the_default_as_before(self):
        self.assertEqual(self.assign([folder("a", "Vivarc"), folder("b", "Arc - Work")], [])["default"]["id"], "a")

    def test_one_folder_that_a_workspace_claims_still_serves_as_the_default(self):
        got = self.assign([folder("a", "Work")], [WORK])
        self.assertEqual(got["default"]["id"], "a")

    def test_without_any_folder_there_is_no_default(self):
        self.assertIsNone(self.assign([], [WORK])["default"])

    def test_the_label_drops_arcs_prefix(self):
        self.assertEqual(js("workspaces.label({ title: 'Arc - Home' })"), "Home")
        self.assertEqual(js("workspaces.label({ title: 'Vivarc' })"), "Vivarc")


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class NewTabs(unittest.TestCase):
    def stamped(self, t, active, window=1):
        out = js("workspaces.stamp(t, active, window)", t=t, active=active, window=window)
        return json.loads(out) if out else None

    def test_a_tab_opened_while_a_space_is_active_joins_that_space(self):
        self.assertEqual(self.stamped({**tab(1), "windowId": 1}, WORK["id"]), {"workspaceId": WORK["id"]})

    def test_a_tab_opened_in_another_window_is_left_to_that_window(self):
        t = {**tab(1), "windowId": 2}
        self.assertIsNone(self.stamped(t, WORK["id"], window=1))
        self.assertEqual(self.stamped({**tab(1), "windowId": 1}, WORK["id"], window=1), {"workspaceId": WORK["id"]})

    def test_the_tabs_other_data_is_kept(self):
        t = {"id": 1, "windowId": 1, "vivExtData": json.dumps({"tiling": {"id": "t"}})}
        self.assertEqual(self.stamped(t, WORK["id"]), {"tiling": {"id": "t"}, "workspaceId": WORK["id"]})

    def test_nothing_is_written_in_the_default_space(self):
        self.assertIsNone(self.stamped({**tab(1), "windowId": 1}, 0))

    def test_a_tab_that_already_has_a_workspace_is_left_alone(self):
        self.assertIsNone(self.stamped({**tab(1, SIDE["id"]), "windowId": 1}, WORK["id"]))
        self.assertIsNone(self.stamped({"id": 1, "windowId": 1, "vivExtData": json.dumps({"workspaceId": 0})}, WORK["id"]))


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class CreateSpace(unittest.TestCase):
    def test_the_hint_names_the_key_the_install_binds_to_create_workspace(self):
        import vivarc
        names = {"ctrl": "Ctrl", "meta": "Cmd", "alt": "Option", "shift": "Shift"}
        shown = "+".join(names.get(k, k.upper()) for k in vivarc.SPACE_KEYS["COMMAND_WORKSPACE_CREATE_NEW"].split("+"))
        self.assertEqual(js("workspaces.CREATE_HINT"), f"Press {shown} to create a space")


@unittest.skipUnless(shutil.which("node"), "node is needed to test the sidebar's JavaScript")
class DeleteSpace(unittest.TestCase):
    FAKE = """
      const calls = [];
      const manager = new (class { removeWorkspace(windowId, id) { calls.push([windowId, id]); return "done"; } })();
      const modules = {
        1: function () { return "nothing to see"; },
        2: function () { return "workspaces.removeWorkspace(e,t)"; },
        3: function () { throw new Error("module 3 must not be loaded"); },
      };
      const exportsOf = { 2: Object.defineProperty({}, "Z", { enumerable: true, get: () => manager }) };
      const require = (id) => { if (!(id in exportsOf)) throw new Error("not loaded: " + id); return exportsOf[id]; };
      require.m = modules;
      const chunks = { push: ([ids, extra, run]) => run(require) };
    """

    def fake(self, body):
        return js("(() => {" + self.FAKE + body + "})()")

    def test_the_remover_is_found_in_vivaldis_own_modules_and_removes_the_workspace(self):
        out = self.fake("const remove = workspaces.findRemover(chunks); return [typeof remove, remove(7, 42), calls];")
        self.assertEqual(out, ["function", "done", [[7, 42]]])

    def test_modules_that_do_not_mention_the_remover_are_never_loaded(self):
        self.assertEqual(self.fake("workspaces.findRemover(chunks); return calls;"), [])

    def test_no_remover_when_vivaldi_has_no_such_module(self):
        self.assertIsNone(js("workspaces.findRemover({ push: ([a, b, run]) => run(Object.assign(() => ({}), { m: { 1: function () {} } })) })"))

    def test_no_remover_when_the_chunk_list_is_missing_or_broken(self):
        self.assertIsNone(js("workspaces.findRemover(undefined)"))
        self.assertIsNone(js("workspaces.findRemover({ push: () => { throw new Error('boom'); } })"))

    def test_the_question_names_the_space_and_counts_its_tabs(self):
        self.assertEqual(js("workspaces.removalQuestion('Work', 5)"), "Delete \u201cWork\u201d and close its 5 tabs?")
        self.assertEqual(js("workspaces.removalQuestion('Work', 1)"), "Delete \u201cWork\u201d and close its 1 tab?")
        self.assertEqual(js("workspaces.removalQuestion('Work', 0)"), "Delete \u201cWork\u201d?")


if __name__ == "__main__":
    unittest.main()
