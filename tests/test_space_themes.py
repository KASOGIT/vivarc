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
}, contains: (name) => classes.has(name) };
global.document = { querySelector: () => browser, createElement: () => new Element(), addEventListener() {}, body: browser };
global.window = {
  __vm: { store: { get: async (key, fallback) => saved.get(key) ?? fallback, set: async (key, value) => saved.set(key, value) },
    cssLoaded: true, onShortcut() {}, onMark() {}, leave: (node) => node && node.remove() },
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
  window.__vm.leave = (node) => { if (node) leaves.push(node); };
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


GRAD_ROW = r"""
const button = (pop, text) => pop.children.find((c) => c.className === "vm-theme-grad").children.find((c) => c.textContent === text);
"""


def theme_with(stops=None, **fields):
    record = {"on": True, "hue": 250, "sat": 28, "light": 20, "grain": 30, **fields}
    if stops is not None:
        record["stops"] = stops
    return record


@unittest.skipUnless(shutil.which("node"), "node is needed to test the theme editor")
class SpaceGradientStops(unittest.TestCase):
    def assert_no_gradient_but_other_fields_load(self, record):
        """Switch to a space holding `record` after one with valid stops: the gradient goes, the tint stays."""
        saved = [["theme:space:0", theme_with([{"hue": 300, "light": 30}])], ["theme:space:1", record]]
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%))", "valid stops set the gradient first");
  assert.equal(props["--vm-grad-glass"], "linear-gradient(160deg, hsl(250 28% 20% / var(--vm-glass-opacity)), hsl(300 28% 30% / var(--vm-glass-opacity)))", "and the glass gradient");
  await switchTo(1);
  assert.equal(props["--vm-tint"], "hsl(77 28% 20%)", "the other fields still load");
  assert.ok(!("--vm-grad" in props), "invalid stops remove the gradient");
  assert.ok(!("--vm-grad-glass" in props), "and the glass gradient");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, saved)

    def test_one_stop_sets_the_gradient_from_the_space_colour(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%))");
  assert.equal(props["--vm-grad-glass"], "linear-gradient(160deg, hsl(250 28% 20% / var(--vm-glass-opacity)), hsl(300 28% 30% / var(--vm-glass-opacity)))");
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with([{"hue": 300, "light": 30}])]])

    def test_two_stops_use_the_theme_saturation_and_keep_their_range_edges(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(143 65% 40%), hsl(0 65% 10%), hsl(359 65% 58%))");
  assert.equal(props["--vm-grad-glass"], "linear-gradient(160deg, hsl(143 65% 40% / var(--vm-glass-opacity)), hsl(0 65% 10% / var(--vm-glass-opacity)), hsl(359 65% 58% / var(--vm-glass-opacity)))");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        record = theme_with([{"hue": 0, "light": 10}, {"hue": 359, "light": 90}], hue=143, sat=65, light=40)
        run_theme(scenario, [["theme:space:0", record]])

    def test_a_record_without_stops_has_no_gradient_and_loads_as_before(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  assert.ok(!("--vm-grad" in props));
  assert.ok(!("--vm-grad-glass" in props));
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, LEGACY)

    def test_invalid_stops_remove_the_gradient_but_keep_the_other_fields(self):
        invalid = {
            "empty array": [],
            "three entries": [{"hue": 10, "light": 30}] * 3,
            "hue above range": [{"hue": 400, "light": 30}],
            "hue 360": [{"hue": 360, "light": 30}],
            "negative hue": [{"hue": -1, "light": 30}],
            "string hue": [{"hue": "a", "light": 30}],
            "light below range": [{"hue": 10, "light": 9}],
            "light above range": [{"hue": 10, "light": 91}],
            "fractional light": [{"hue": 10, "light": 30.5}],
            "fractional hue": [{"hue": 10.5, "light": 30}],
            "numeric string light": [{"hue": 10, "light": "30"}],
            "missing light": [{"hue": 10}],
            "null entry": [None],
            "one valid and one invalid": [{"hue": 10, "light": 30}, {"hue": 400, "light": 30}],
            "not an array": {"hue": 10, "light": 30},
        }
        for name, stops in invalid.items():
            with self.subTest(name):
                self.assert_no_gradient_but_other_fields_load(theme_with(stops, hue=77))

    def test_a_theme_that_is_off_has_no_gradient(self):
        saved = [["theme:space:0", theme_with([{"hue": 300, "light": 30}])],
                 ["theme:space:1", theme_with([{"hue": 300, "light": 30}], on=False)]]
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.ok("--vm-grad" in props, "on with stops sets it");
  assert.ok("--vm-grad-glass" in props, "and the glass one");
  await switchTo(1);
  assert.ok(!("--vm-grad" in props), "off removes it");
  assert.ok(!("--vm-grad-glass" in props), "off removes the glass one");
  assert.ok(!("--vm-tint" in props), "off removes the tint too");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, saved)

    def test_switching_spaces_sets_then_removes_the_gradient(self):
        saved = [["theme:space:0", theme_with([{"hue": 300, "light": 30}, {"hue": 20, "light": 50}])],
                 ["theme:space:1", theme_with(hue=10)],
                 ["theme:space:2", theme_with([{"hue": 90, "light": 40}], hue=120)]]
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%), hsl(20 28% 50%))");
  assert.equal(props["--vm-grad-glass"], "linear-gradient(160deg, hsl(250 28% 20% / var(--vm-glass-opacity)), hsl(300 28% 30% / var(--vm-glass-opacity)), hsl(20 28% 50% / var(--vm-glass-opacity)))");
  await switchTo(1);
  assert.ok(!("--vm-grad" in props), "a space without stops removes it");
  assert.ok(!("--vm-grad-glass" in props), "and the glass one");
  assert.equal(props["--vm-tint"], "hsl(10 28% 20%)");
  await switchTo(2);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(120 28% 20%), hsl(90 28% 40%))");
  assert.equal(props["--vm-grad-glass"], "linear-gradient(160deg, hsl(120 28% 20% / var(--vm-glass-opacity)), hsl(90 28% 40% / var(--vm-glass-opacity)))");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, saved)

    def test_reset_clears_the_stops_from_the_saved_record_and_the_gradient(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%))");
  assert.ok("--vm-grad-glass" in props, "the glass gradient is set before the reset");
  const pop = await open();
  pop.children.at(-1).listeners.click(); // reset
  assert.equal(saved.get("theme:space:0").on, false);
  assert.equal(saved.get("theme:space:0").stops, undefined);
  assert.ok(!("--vm-grad" in props), "reset removes the gradient");
  assert.ok(!("--vm-grad-glass" in props), "reset removes the glass gradient");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with([{"hue": 300, "light": 30}])]])

    def test_a_stop_renders_on_the_same_side_of_the_text_colour_switch_as_the_main_colour(self):
        # (main light, stop light set by the user, stop light rendered)
        cases = [(88, 20, 59), (20, 90, 58), (58, 90, 58), (59, 10, 59), (20, 40, 40), (88, 70, 70), (59, 59, 59), (58, 58, 58)]
        for main, stop, rendered in cases:
            with self.subTest(main=main, stop=stop):
                expected = f"linear-gradient(160deg, hsl(250 28% {main}%), hsl(300 28% {rendered}%))"
                glass = f"linear-gradient(160deg, hsl(250 28% {main}% / var(--vm-glass-opacity)), hsl(300 28% {rendered}% / var(--vm-glass-opacity)))"
                scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], %s);
  assert.equal(props["--vm-grad-glass"], %s);
})().catch((error) => { console.error(error); process.exitCode = 1; });
""" % (json.dumps(expected).replace("%", "%%"), json.dumps(glass).replace("%", "%%"))
                run_theme(scenario.replace("%%", "%"), [["theme:space:0", theme_with([{"hue": 300, "light": stop}], light=main)]])

    def test_two_stops_are_each_clamped_to_the_side_of_the_main_colour(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 88%), hsl(300 28% 59%), hsl(10 28% 80%))");
  await switchTo(1);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%), hsl(10 28% 58%))");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        saved = [["theme:space:0", theme_with([{"hue": 300, "light": 20}, {"hue": 10, "light": 80}], light=88)],
                 ["theme:space:1", theme_with([{"hue": 300, "light": 30}, {"hue": 10, "light": 90}], light=20)]]
        run_theme(scenario, saved)

    def test_the_saved_record_keeps_the_stop_light_the_user_set(self):
        scenario = r"""
(async () => {
  await switchTo(0);
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 88%), hsl(300 28% 59%))");
  const pop = await open();
  const input = pop.children.at(-2).children[1]; // grain slider
  input.value = "50";
  input.listeners.input();
  assert.deepEqual(saved.get("theme:space:0").stops, [{ hue: 300, light: 20 }]);
  assert.equal(saved.get("theme:space:0").grain, 50);
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with([{"hue": 300, "light": 20}], light=88)]])

    def test_the_gradient_row_walks_auto_custom_add_remove_auto(self):
        scenario = GRAD_ROW + r"""
(async () => {
  classes.add("vm-gradient");
  await switchTo(0);
  const pop = await open();
  assert.deepEqual(saved.get("theme:space:0").stops, undefined);
  button(pop, "Custom").listeners.click();
  assert.deepEqual(saved.get("theme:space:0").stops, [{ hue: 290, light: 20 }]);
  button(pop, "+").listeners.click();
  assert.deepEqual(saved.get("theme:space:0").stops, [{ hue: 290, light: 20 }, { hue: 330, light: 20 }]);
  button(pop, "−").listeners.click();
  assert.deepEqual(saved.get("theme:space:0").stops, [{ hue: 290, light: 20 }]);
  button(pop, "Auto").listeners.click();
  assert.equal(saved.get("theme:space:0").stops, undefined);
  assert.ok(!("--vm-grad" in props), "Auto drops the gradient");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with(hue=250, light=20)]])

    def test_the_first_custom_stop_hue_wraps_past_359(self):
        scenario = GRAD_ROW + r"""
(async () => {
  classes.add("vm-gradient");
  await switchTo(0);
  const pop = await open();
  button(pop, "Custom").listeners.click();
  assert.deepEqual(saved.get("theme:space:0").stops, [{ hue: 20, light: 20 }]);
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with(hue=340, light=20)]])

    def test_the_gradient_row_is_built_only_while_the_space_gradient_setting_is_on(self):
        scenario = r"""
(async () => {
  const rows = (pop) => pop.children.filter((c) => c.className === "vm-theme-grad").length;
  await switchTo(0);
  let pop = await open();
  assert.equal(pop.className, "vm-theme-pop");
  assert.equal(rows(pop), 0, "no row while vm-gradient is missing");
  pop.children.at(-1).listeners.click(); // reset closes it
  classes.add("vm-gradient");
  await switchTo(1);
  pop = await open();
  assert.equal(rows(pop), 1, "a row while vm-gradient is present");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, [["theme:space:0", theme_with()], ["theme:space:1", theme_with()]])


if __name__ == "__main__":
    unittest.main()
