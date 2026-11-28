import os
import shutil
import subprocess
import unittest

from jsrun import JS_DIR

HARNESS = r"""
const fs = require("fs"), vm = require("vm"), assert = require("assert");
globalThis.window = {};
Object.defineProperty(globalThis, "navigator", { value: { platform: "MacIntel" } });
globalThis.indexedDB = { open: () => ({}) };
globalThis.vivaldi = { tabsPrivate: { onKeyboardShortcut: { addListener() {} } } };
globalThis.MutationObserver = class { observe() {} disconnect() {} };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "" });
globalThis.document = { documentElement: { classList: { add() {} } }, querySelector: () => null, addEventListener() {} };
const timers = [];
globalThis.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const leave = (node) => {
  assert.equal(typeof window.__vm.leave, "function", "window.__vm.leave exists");
  return window.__vm.leave(node);
};
const fakeNode = () => {
  const node = { classes: new Set(), removed: 0, listeners: {} };
  node.classList = { add: (c) => node.classes.add(c) };
  node.addEventListener = (name, fn) => { node.listeners[name] = fn; };
  node.remove = () => { node.removed++; };
  return node;
};
"""


def run_core(scenario):
    done = subprocess.run(["node", "-e", HARNESS + scenario, os.path.join(JS_DIR, "00-core.js")],
                          capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(done.stderr)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the leave helper")
class Leave(unittest.TestCase):
    def test_marks_the_node_leaving_and_keeps_it_until_the_transition_ends(self):
        run_core(r"""
const node = fakeNode();
leave(node);
assert.ok(node.classes.has("vm-leaving"), "class vm-leaving added");
assert.equal(node.removed, 0, "not removed yet");
""")

    def test_transitionend_on_the_node_removes_it_once(self):
        run_core(r"""
const node = fakeNode();
leave(node);
node.listeners.transitionend({ target: node });
assert.equal(node.removed, 1);
for (const t of timers) t.fn();
assert.equal(node.removed, 1, "the fallback timer does not remove it again");
""")

    def test_transitionend_from_a_child_does_not_remove_it_and_the_timer_does(self):
        run_core(r"""
const node = fakeNode();
leave(node);
node.listeners.transitionend({ target: fakeNode() });
assert.equal(node.removed, 0, "a child's transition is ignored");
assert.equal(timers.length, 1);
assert.equal(timers[0].ms, 250);
timers[0].fn();
assert.equal(node.removed, 1);
""")

    def test_the_timer_removes_it_after_250_ms_without_any_event(self):
        run_core(r"""
const node = fakeNode();
leave(node);
assert.equal(timers.length, 1);
assert.equal(timers[0].ms, 250);
assert.equal(node.removed, 0);
timers[0].fn();
assert.equal(node.removed, 1);
""")

    def test_a_late_transitionend_after_the_timer_does_not_remove_it_twice(self):
        run_core(r"""
const node = fakeNode();
leave(node);
timers[0].fn();
node.listeners.transitionend({ target: node });
assert.equal(node.removed, 1);
""")

    def test_null_and_undefined_do_nothing(self):
        run_core(r"""
leave(null);
leave(undefined);
assert.equal(timers.length, 0);
""")


if __name__ == "__main__":
    unittest.main()
