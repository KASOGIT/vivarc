import shutil
import unittest

from jsrun import run_js


def rows(keys, sigs=None):
    sigs = sigs or {}
    return [{"key": k, "sig": sigs.get(k, "1")} for k in keys]


def plan(prev, next):
    return run_js("09-keyed.js", "window.__vm.keyed.plan(prev, next)", prev=prev, next=next)


def apply(prev_keys, ops):
    keys = list(prev_keys)
    for o in ops:
        if o["op"] == "remove":
            keys.remove(o["key"])
        elif o["op"] in ("insert", "move"):
            if o["op"] == "move":
                keys.remove(o["key"])
            assert o["before"] is None or o["before"] in keys, f"anchor {o['before']} is not in {keys} when {o} runs"
            at = len(keys) if o["before"] is None else keys.index(o["before"])
            keys.insert(at, o["key"])
    return keys


def count(ops, op):
    return len([o for o in ops if o["op"] == op])


@unittest.skipUnless(shutil.which("node"), "node is needed to test the keyed planner's JavaScript")
class Keyed(unittest.TestCase):
    def test_identical_lists_need_no_operation(self):
        self.assertEqual(plan(rows("abc"), rows("abc")), [])

    def test_a_row_missing_from_next_is_removed(self):
        self.assertEqual(plan(rows("abc"), rows("ac")), [{"op": "remove", "key": "b"}])

    def test_a_kept_row_with_a_new_sig_is_replaced(self):
        self.assertEqual(plan(rows("abc"), rows("abc", {"b": "2"})), [{"op": "replace", "key": "b"}])

    def test_a_new_row_is_inserted_before_the_next_row_or_at_the_end(self):
        self.assertEqual(plan(rows("ab"), rows("abx")), [{"op": "insert", "key": "x", "before": None}])
        self.assertEqual(plan(rows("ab"), rows("axb")), [{"op": "insert", "key": "x", "before": "b"}])

    def test_a_swap_is_one_move(self):
        ops = plan(rows("abc"), rows("bac"))
        self.assertEqual(len(ops), 1)
        self.assertIn(ops[0], [{"op": "move", "key": "a", "before": "c"}, {"op": "move", "key": "b", "before": "a"}])
        self.assertEqual(apply("abc", ops), list("bac"))

    def test_a_rotation_moves_only_the_row_that_jumped(self):
        self.assertEqual(plan(rows("abcd"), rows("dabc")), [{"op": "move", "key": "d", "before": "a"}])

    def test_removes_come_first_then_replaces_then_inserts_and_moves(self):
        ops = plan(rows("abcd"), rows("cxad", {"c": "2"}))
        self.assertEqual(ops[:2], [{"op": "remove", "key": "b"}, {"op": "replace", "key": "c"}])
        self.assertEqual(apply("abcd", ops), list("cxad"))
        self.assertEqual(count(ops, "insert"), 1)
        self.assertLessEqual(count(ops, "move"), 1)
        self.assertEqual(len(ops), 2 + count(ops, "insert") + count(ops, "move"))

    def test_an_empty_list_gets_every_row_inserted_in_order(self):
        self.assertEqual(plan([], rows("ab")), [{"op": "insert", "key": "a", "before": None}, {"op": "insert", "key": "b", "before": None}])

    def test_rows_added_at_the_front_anchor_on_the_first_stable_row(self):
        self.assertEqual(plan(rows("ab"), rows("xyab")), [{"op": "insert", "key": "x", "before": "a"}, {"op": "insert", "key": "y", "before": "a"}])

    def test_an_insert_anchors_on_a_stable_row_not_on_a_row_that_moves(self):
        self.assertEqual(plan(rows("abc"), rows("cxab")), [{"op": "move", "key": "c", "before": "a"}, {"op": "insert", "key": "x", "before": "a"}])

    def test_an_emptied_list_removes_every_row_in_order(self):
        self.assertEqual(plan(rows("ab"), []), [{"op": "remove", "key": "a"}, {"op": "remove", "key": "b"}])


if __name__ == "__main__":
    unittest.main()
