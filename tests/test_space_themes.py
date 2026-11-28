import json
import os
import shutil
import subprocess
import unittest


HARNESS = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const events = {}, saved = new Map(JSON.parse(process.argv[2]));
class Element {
  constructor() { this.children = []; this.listeners = {}; this.style = {}; this.className = ""; }
  append(...items) { this.children.push(...items); }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  remove() {}
  contains() { return false; }
}
const props = {};
const browser = new Element();
browser.style = { setProperty: (k, v) => props[k] = v, removeProperty: (k) => delete props[k] };
const classes = new Set();
browser.classList = { toggle(name, force) {
  const on = force === undefined ? !classes.has(name) : !!force;
  if (on) classes.add(name); else classes.delete(name);
  return on;
} };
global.document = { querySelector: () => browser, createElement: () => new Element(), addEventListener() {}, body: browser };
global.window = {
  __vm: { store: { get: async (key, fallback) => saved.get(key) ?? fallback, set: async (key, value) => saved.set(key, value) },
    cssLoaded: true, onShortcut() {}, onMark() {} },
  addEventListener: (name, fn) => events[name] = fn,
};
global.BroadcastChannel = undefined;
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const tick = () => new Promise((resolve) => setImmediate(resolve));
const switchTo = async (space) => { events["vm-active-space-changed"]({ detail: space }); await tick(); };
const open = async () => { events["vm-open-theme"](); await tick(); return browser.children.at(-1); };
'''

LEGACY = [["theme", {"on": True, "hue": 250, "sat": 28, "light": 20, "grain": 30}]]


def run_theme(scenario, saved):
    path = os.path.join(os.path.dirname(__file__), "..", "src", "js", "40-theme.js")
    done = subprocess.run(["node", "-e", HARNESS + scenario, path, json.dumps(saved)], capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(done.stderr)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the theme editor")
class SpaceThemes(unittest.TestCase):
    def test_space_themes_are_independent_and_keep_the_existing_theme_as_fallback(self):
        scenario = r'''
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  let pop = await open();
  pop.children[3].children[3].listeners.click(); // red preset
  assert.equal(saved.get("theme:space:0").hue, 355);
  await switchTo(42);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  pop = await open();
  pop.children[3].children[6].listeners.click(); // green preset
  assert.equal(saved.get("theme:space:42").hue, 143);
  await switchTo(0);
  assert.equal(props["--vm-tint"], "hsl(355 65% 62%)");
  pop = await open();
  pop.children.at(-1).listeners.click();
  assert.equal(saved.get("theme:space:0").on, false);
  assert.equal(saved.get("theme:space:42").hue, 143);
  await switchTo(42);
  assert.equal(props["--vm-tint"], "hsl(143 65% 65%)");
  assert.equal(saved.get("theme").hue, 250);
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
        run_theme(scenario, LEGACY)

    def test_a_washed_out_space_theme_marks_the_browser_as_neutral_while_it_is_on(self):
        saved = [
            ["theme:space:0", {"on": True, "hue": 250, "sat": 5, "light": 40, "grain": 30}],
            ["theme:space:1", {"on": True, "hue": 250, "sat": 28, "light": 20, "grain": 30}],
            ["theme:space:2", {"on": True, "hue": 250, "sat": 10, "light": 20, "grain": 30}],
            ["theme:space:3", {"on": True, "hue": 250, "sat": 9, "light": 20, "grain": 30}],
            ["theme:space:4", {"on": False, "hue": 250, "sat": 5, "light": 20, "grain": 30}],
        ]
        scenario = r'''
(async () => {
  await switchTo(0);
  assert.ok(classes.has("vm-tint-neutral"), "sat 5 is neutral");
  await switchTo(1);
  assert.ok(!classes.has("vm-tint-neutral"), "sat 28 clears it");
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  await switchTo(2);
  assert.ok(!classes.has("vm-tint-neutral"), "sat 10 is not neutral");
  await switchTo(3);
  assert.ok(classes.has("vm-tint-neutral"), "sat 9 is neutral");
  await switchTo(4);
  assert.ok(!classes.has("vm-tint-neutral"), "a theme that is off is not neutral");
  await switchTo(0);
  assert.ok(classes.has("vm-tint-neutral"), "back on a sat 5 space");
  const pop = await open();
  pop.children.at(-1).listeners.click(); // reset
  assert.equal(saved.get("theme:space:0").on, false);
  assert.ok(!classes.has("vm-tint-neutral"), "reset clears it");
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
        run_theme(scenario, saved)

    def test_closing_the_pop_up_hands_it_to_leave_and_removes_the_shield_at_once(self):
        scenario = r'''
(async () => {
  const leaves = [], removed = [];
  window.__vm.leave = (node) => leaves.push(node);
  Element.prototype.remove = function () { removed.push(this); };
  await switchTo(0);
  const pop = await open();
  const shield = browser.children.at(-2);
  assert.equal(shield.className, "vm-menu-shield");
  shield.listeners.mousedown({ preventDefault() {} }); // a click on the page closes the pop-up
  assert.deepEqual(leaves, [pop], "the pop-up is handed to leave");
  assert.ok(!removed.includes(pop), "the pop-up is not removed synchronously");
  assert.ok(removed.includes(shield), "the shield is removed immediately");
  const again = await open();
  assert.notEqual(again, pop, "reopening builds a new pop-up at once");
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
        run_theme(scenario, LEGACY)


if __name__ == "__main__":
    unittest.main()
