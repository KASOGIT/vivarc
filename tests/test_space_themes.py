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
  removeEventListener() {}
  setPointerCapture() {}
  getBoundingClientRect() { return { left: 0, top: 0, width: 360, height: 80 }; }
  contains() { return false; }
}
const props = {};
const browser = new Element();
browser.style = {
  setProperty: (k, v) => { props[k] = v; log.push(`set:${k}=${v}`); },
  removeProperty: (k) => { delete props[k]; log.push(`rm:${k}`); },
};
const media = {
  matches: process.argv[4] === "dark", listeners: [],
  addEventListener(name, fn) { if (name === "change") this.listeners.push(fn); },
  removeEventListener() {},
  flip(matches) { this.matches = matches; this.listeners.forEach((fn) => fn({ matches, media: "(prefers-color-scheme: dark)" })); },
};
const timers = [];
const fakeSetTimeout = (fn, delay) => { timers.push({ id: timers.length + 1, fn, delay, cleared: false, fired: false }); return timers.length; };
const fakeClearTimeout = (id) => { const t = timers.find((x) => x.id === id); if (t) t.cleared = true; };
global.setTimeout = fakeSetTimeout;
global.clearTimeout = fakeClearTimeout;
const pendingTimers = () => timers.filter((t) => !t.cleared && !t.fired);
const fire = (t) => { assert.ok(!t.cleared && !t.fired, "only a live timer can fire"); t.fired = true; t.fn(); };
const channels = [];
const marks = [];
const classes = new Set();
const log = [];
const setClass = (name, on) => {
  if (on) classes.add(name); else classes.delete(name);
  log.push((on ? "class+:" : "class-:") + name);
  return on;
};
browser.classList = {
  toggle: (name, force) => setClass(name, force === undefined ? !classes.has(name) : !!force),
  add: (...names) => names.forEach((name) => setClass(name, true)),
  remove: (...names) => names.forEach((name) => setClass(name, false)),
  contains: (name) => classes.has(name),
};
global.document = { querySelector: () => browser, createElement: () => new Element(), addEventListener() {}, body: browser };
global.window = {
  __vm: { store: { get: async (key, fallback) => saved.get(key) ?? fallback, set: async (key, value) => saved.set(key, value) },
    cssLoaded: true, onShortcut() {}, onMark: (fn) => marks.push(fn), leave: (node) => node && node.remove() },
  addEventListener: (name, fn) => events[name] = fn,
  setTimeout: fakeSetTimeout,
  clearTimeout: fakeClearTimeout,
  matchMedia: (query) => query === "(prefers-color-scheme: dark)" ? media : { matches: false, addEventListener() {}, removeEventListener() {} },
};
global.matchMedia = window.matchMedia;
global.BroadcastChannel = process.argv[3] === "channel" ? class { constructor() { channels.push(this); } postMessage() {} } : undefined;
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const tick = () => new Promise((resolve) => setImmediate(resolve));
const switchTo = async (space) => { events["vm-active-space-changed"]({ detail: space }); await tick(); };
const open = async () => { events["vm-open-theme"](); await tick(); return browser.children.at(-1); };
'''

LEGACY = [["theme", {"on": True, "hue": 250, "sat": 28, "light": 20, "grain": 30}]]


def run_theme(scenario, saved, channel=False, dark=False):
    path = os.path.join(os.path.dirname(__file__), "..", "src", "js", "40-theme.js")
    args = ["node", "-e", HARNESS + scenario, path, json.dumps(saved), "channel" if channel else "-", "dark" if dark else "light"]
    done = subprocess.run(args, capture_output=True, text=True)
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
  pop.children[3].children[3].listeners.click(); // mint preset
  assert.equal(saved.get("theme:space:0").hue, 131);
  await switchTo(42);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  pop = await open();
  pop.children[3].children[9].listeners.click(); // forest preset
  assert.equal(saved.get("theme:space:42").hue, 136);
  await switchTo(0);
  assert.equal(props["--vm-tint"], "hsl(131 46% 78%)");
  pop = await open();
  pop.children.at(-1).listeners.click();
  assert.equal(saved.get("theme:space:0").on, false);
  assert.equal(saved.get("theme:space:42").hue, 136);
  await switchTo(42);
  assert.equal(props["--vm-tint"], "hsl(136 37% 38%)");
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


FADE = r"""
const FADE = "vm-tint-fade";
const fades = (from = 0) => log.slice(from).filter((e) => e === "class+:" + FADE).length;
const expectCrossFade = async (to, label) => {
  const mark = log.length;
  await switchTo(to);
  assert.equal(fades(mark), 1, label + ": an on to on switch fades");
};
"""

PALETTE = [["theme:space:0", theme_with(hue=250)], ["theme:space:1", theme_with(hue=10)], ["theme:space:2", theme_with(hue=120)],
           ["theme:space:3", theme_with(hue=200)]]


@unittest.skipUnless(shutil.which("node"), "node is needed to test the theme editor")
class SpaceTintCrossFade(unittest.TestCase):
    def test_a_switch_between_two_themed_spaces_adds_the_class_before_the_new_tint_and_removes_it_after_300ms(self):
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  assert.equal(pendingTimers().length, 0, "no timer after the first selection");
  const mark = log.length;
  await switchTo(1);
  const since = log.slice(mark);
  const fadeAt = since.indexOf("class+:" + FADE);
  const tintAt = since.findIndex((e) => e === "set:--vm-tint=hsl(10 28% 20%)");
  assert.ok(fadeAt >= 0, "the fade class is added");
  assert.ok(tintAt >= 0, "the new tint is set");
  assert.ok(fadeAt < tintAt, "the class goes on before the tint changes");
  const live = pendingTimers();
  assert.equal(live.length, 1, "one removal is scheduled");
  assert.equal(live[0].delay, 300);
  assert.ok(classes.has(FADE), "the class stays while the timer is pending");
  fire(live[0]);
  assert.ok(!classes.has(FADE), "the timer removes the class");
  assert.equal(props["--vm-tint"], "hsl(10 28% 20%)");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, PALETTE)

    def test_a_second_switch_within_300ms_cancels_the_pending_removal_and_schedules_a_new_one(self):
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  await switchTo(1);
  const first = pendingTimers();
  assert.equal(first.length, 1);
  await switchTo(2);
  assert.equal(props["--vm-tint"], "hsl(120 28% 20%)");
  assert.ok(first[0].cleared, "the first removal is cancelled with clearTimeout");
  const live = pendingTimers();
  assert.equal(live.length, 1, "exactly one removal is left");
  assert.notEqual(live[0], first[0]);
  assert.equal(live[0].delay, 300);
  assert.ok(classes.has(FADE), "the class stays on while the last timer is pending");
  fire(live[0]);
  assert.ok(!classes.has(FADE), "the last timer removes it");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, PALETTE)

    def test_the_first_space_selection_does_not_fade(self):
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  assert.equal(fades(), 0, "no previous space");
  assert.equal(pendingTimers().length, 0);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  await expectCrossFade(1, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, PALETTE)

    def test_a_switch_from_a_space_whose_theme_is_off_does_not_fade(self):
        saved = [["theme:space:0", theme_with(on=False)], *PALETTE[1:]]
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  const mark = log.length;
  await switchTo(1);
  assert.equal(props["--vm-tint"], "hsl(10 28% 20%)");
  assert.equal(fades(mark), 0, "off to on does not fade");
  assert.equal(pendingTimers().length, 0);
  await expectCrossFade(2, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, saved)

    def test_a_switch_to_a_space_whose_theme_is_off_does_not_fade(self):
        saved = [PALETTE[0], ["theme:space:1", theme_with(on=False)], *PALETTE[2:]]
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  const mark = log.length;
  await switchTo(1);
  assert.ok(!("--vm-tint" in props), "the tint is removed");
  assert.equal(fades(mark), 0, "on to off does not fade");
  assert.equal(pendingTimers().length, 0);
  await switchTo(2);
  await expectCrossFade(3, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, saved)

    def test_an_edit_from_the_pop_up_does_not_fade(self):
        edits = {
            "preset swatch": "pop.children[3].children[3].listeners.click();",
            "Dark button": "pop.children[1].children[0].listeners.click();",
            "Light button": "pop.children[1].children[1].listeners.click();",
        }
        for name, edit in edits.items():
            with self.subTest(name):
                scenario = FADE + r"""
(async () => {
  await switchTo(0);
  const pop = await open();
  const mark = log.length;
  const before = props["--vm-tint"];
  EDIT
  assert.notEqual(props["--vm-tint"], before, "the edit changed the tint");
  assert.equal(fades(mark), 0, "an edit does not fade");
  assert.equal(pendingTimers().length, 0, "and schedules nothing");
  await expectCrossFade(1, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
""".replace("EDIT", edit)
                run_theme(scenario, PALETTE)

    def test_an_update_from_another_window_does_not_fade(self):
        scenario = FADE + r"""
(async () => {
  await switchTo(0);
  assert.equal(channels.length, 1, "the mod listens on a BroadcastChannel");
  const mark = log.length;
  channels[0].onmessage({ data: { space: 0, theme: { on: true, hue: 100, sat: 28, light: 20, grain: 30 } } });
  assert.equal(props["--vm-tint"], "hsl(100 28% 20%)", "the update is applied");
  assert.equal(fades(mark), 0, "a remote update does not fade");
  assert.equal(pendingTimers().length, 0);
  await expectCrossFade(1, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, PALETTE, channel=True)

    def test_an_edit_after_a_fade_has_started_removes_the_class_at_once(self):
        edits = {
            "preset swatch": "pop.children[3].children[3].listeners.click();",
            "Dark button": "pop.children[1].children[0].listeners.click();",
            "grain slider": 'const input = pop.children.at(-2).children[1]; input.value = "50"; input.listeners.input();',
        }
        for name, edit in edits.items():
            with self.subTest(name):
                scenario = FADE + r"""
(async () => {
  await switchTo(0);
  await switchTo(1);
  assert.ok(classes.has(FADE), "the fade has started");
  const pop = await open();
  EDIT
  assert.ok(!classes.has(FADE), "the edit removes the class before the timer fires");
})().catch((error) => { console.error(error); process.exitCode = 1; });
""".replace("EDIT", edit)
                run_theme(scenario, PALETTE)


    def test_custom_stops_on_either_side_of_a_switch_do_not_fade_but_invalid_stops_do(self):
        custom, other = [{"hue": 300, "light": 30}], [{"hue": 20, "light": 50}, {"hue": 90, "light": 40}]
        cases = {
            "custom to custom": (custom, other, 0),
            "custom to auto": (custom, None, 0),
            "auto to custom": (None, custom, 0),
            "auto to invalid stops": (None, [{"hue": 400, "light": 30}], 1),
        }
        for name, (first, second, expected) in cases.items():
            with self.subTest(name):
                saved = [["theme:space:0", theme_with(first, hue=250)], ["theme:space:1", theme_with(second, hue=10)],
                         ["theme:space:2", theme_with(hue=120)], ["theme:space:3", theme_with(hue=200)]]
                scenario = FADE + r"""
(async () => {
  await switchTo(0);
  const mark = log.length;
  await switchTo(1);
  assert.equal(props["--vm-tint"], "hsl(10 28% 20%)");
  assert.equal(fades(mark), EXPECTED, "the first switch");
  assert.equal(pendingTimers().length, EXPECTED, "timers after the first switch");
  await switchTo(2);
  await expectCrossFade(3, "control");
})().catch((error) => { console.error(error); process.exitCode = 1; });
""".replace("EXPECTED", str(expected))
                run_theme(scenario, saved)

    def test_an_apply_from_on_mark_removes_the_fade_class_at_once(self):
        scenario = FADE + r"""
(async () => {
  assert.equal(marks.length, 1, "the mod registers one onMark callback");
  await switchTo(0);
  await switchTo(1);
  assert.ok(classes.has(FADE), "the fade has started");
  marks[0](browser);
  assert.ok(!classes.has(FADE), "an apply from onMark never fades");
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        run_theme(scenario, PALETTE)


OKLCH_PRESETS = [
    ["Paper", "oklch(0.86 0.008 80)", 37, 9, 81], ["Rose", "oklch(0.86 0.07 15)", 357, 90, 87],
    ["Amber", "oklch(0.86 0.08 70)", 32, 80, 77], ["Mint", "oklch(0.86 0.08 150)", 131, 46, 78],
    ["Sky", "oklch(0.86 0.07 235)", 203, 87, 81], ["Lilac", "oklch(0.86 0.07 305)", 266, 74, 87],
    ["Graphite", "oklch(0.56 0.02 270)", 224, 7, 47], ["Ruby", "oklch(0.56 0.13 15)", 353, 40, 51],
    ["Ochre", "oklch(0.56 0.12 65)", 34, 81, 35], ["Forest", "oklch(0.56 0.11 150)", 136, 37, 38],
    ["Ocean", "oklch(0.56 0.11 245)", 206, 55, 45], ["Violet", "oklch(0.56 0.12 305)", 269, 32, 53],
]


@unittest.skipUnless(shutil.which("node"), "node is needed to test the theme editor")
class OklchPresets(unittest.TestCase):
    def run_presets(self, body):
        table = json.dumps(OKLCH_PRESETS)
        run_theme("const PRESETS = %s;\n(async () => {\n  await switchTo(0);\n  const pop = await open();\n"
                  "  const swatches = pop.children[3].children;\n%s\n})().catch((error) => { console.error(error); process.exitCode = 1; });"
                  % (table, body), LEGACY)

    def test_the_swatch_container_has_twelve_swatches(self):
        self.run_presets("  assert.equal(swatches.length, 12);")

    def test_each_swatch_shows_its_oklch_colour_as_background(self):
        self.run_presets(r'''
  assert.equal(swatches.length, 12);
  PRESETS.forEach(([, color], i) => assert.equal(swatches[i].style.backgroundColor, color, `swatch ${i}`));''')

    def test_each_swatch_has_a_title_naming_it(self):
        self.run_presets(r'''
  assert.equal(swatches.length, 12);
  PRESETS.forEach(([name], i) => assert.equal(swatches[i].title, name, `swatch ${i}`));''')

    def test_clicking_a_swatch_saves_its_hsl_equivalent_and_keeps_on_and_grain(self):
        self.run_presets(r'''
  for (const i of [0, 5, 6, 11]) {
    swatches[i].listeners.click();
    const [, , hue, sat, light] = PRESETS[i];
    const record = saved.get("theme:space:0");
    assert.deepEqual({ hue: record.hue, sat: record.sat, light: record.light }, { hue, sat, light }, `swatch ${i}`);
    assert.equal(record.on, true, `swatch ${i} on`);
    assert.equal(record.grain, 30, `swatch ${i} grain`);
  }''')

    def test_the_mint_swatch_sets_the_tint(self):
        self.run_presets(r'''
  swatches[3].listeners.click();
  assert.equal(props["--vm-tint"], "hsl(131 46% 78%)");''')

    def test_paper_and_graphite_mark_the_browser_neutral_and_rose_does_not(self):
        self.run_presets(r'''
  swatches[0].listeners.click();
  assert.ok(classes.has("vm-tint-neutral"), "paper is neutral");
  swatches[1].listeners.click();
  assert.ok(!classes.has("vm-tint-neutral"), "rose is not neutral");
  swatches[6].listeners.click();
  assert.ok(classes.has("vm-tint-neutral"), "graphite is neutral");''')

    def test_the_light_row_gets_dark_text_and_the_deep_row_light_text(self):
        self.run_presets(r'''
  for (const [i, fg] of [[0, "#1b1b1f"], [5, "#1b1b1f"], [6, "#f2f2f5"], [11, "#f2f2f5"]]) {
    swatches[i].listeners.click();
    assert.equal(props["--vm-fg"], fg, `swatch ${i}`);
  }''')



MODES_ROW = r"""
const modeButton = (pop, text) => {
  const row = pop.children.find((c) => c.className === "vm-theme-modes");
  const found = row.children.find((c) => c.textContent === text);
  assert.ok(found, `the modes row has a ${text} button`);
  return found;
};
const pressed = (pop) => ["Dark", "Light", "Auto"].map((t) => modeButton(pop, t).ariaPressed).join(",");
// The fake pad is 360 wide and 80 tall, so a point (x, y) is hue x and light 90 - y.
const pad = (pop) => pop.children.find((c) => c.className === "vm-theme-pad");
const drag = (pop, hue, light) => pad(pop).listeners.pointerdown({ clientX: hue, clientY: 90 - light, pointerId: 1 });
const top = (dot) => parseFloat(dot.style.top);
const near = (actual, expected, message) => assert.ok(Math.abs(actual - expected) < 1e-9, `${message}: ${actual} vs ${expected}`);
"""

DARK_TEXT, LIGHT_TEXT = "#f2f2f5", "#1b1b1f"


def auto(**fields):
    return theme_with(mode="auto", **fields)


@unittest.skipUnless(shutil.which("node"), "node is needed to test the theme editor")
class SpaceAutoMode(unittest.TestCase):
    def check(self, record, body, dark=False, channel=False):
        scenario = MODES_ROW + "(async () => {\n  await switchTo(0);\n" + body + "\n})().catch((error) => { console.error(error); process.exitCode = 1; });"
        run_theme(scenario, [["theme:space:0", record]], dark=dark, channel=channel)

    def test_auto_renders_the_dark_side_in_a_dark_system_and_its_complement_in_a_light_one(self):
        # (saved light, rendered when the system is dark, rendered when it is light)
        cases = [(20, 20, 80), (88, 12, 88), (45, 41, 59), (50, 41, 59), (41, 41, 59), (42, 41, 59), (59, 41, 59), (10, 10, 90), (90, 10, 90), (5, 10, 90), (95, 10, 90)]
        for saved_light, in_dark, in_light in cases:
            for dark, rendered in ((True, in_dark), (False, in_light)):
                with self.subTest(light=saved_light, dark=dark):
                    fg = DARK_TEXT if rendered <= 58 else LIGHT_TEXT
                    self.check(auto(light=saved_light), f"""
  assert.equal(props["--vm-tint"], "hsl(250 28% {rendered}%)");
  assert.equal(props["--vm-fg"], "{fg}");""", dark=dark)

    def test_auto_text_always_flips_with_the_system_appearance(self):
        for saved_light in (10, 20, 45, 50, 88):
            with self.subTest(light=saved_light):
                self.check(auto(light=saved_light), f'assert.equal(props["--vm-fg"], "{DARK_TEXT}");', dark=True)
                self.check(auto(light=saved_light), f'assert.equal(props["--vm-fg"], "{LIGHT_TEXT}");', dark=False)

    def test_auto_leaves_the_saved_record_unchanged_on_a_grain_edit(self):
        self.check(auto(light=88), r"""
  const pop = await open();
  const grain = pop.children.at(-2).children[1];
  grain.value = "50";
  grain.listeners.input();
  const record = saved.get("theme:space:0");
  assert.equal(record.light, 88);
  assert.equal(record.mode, "auto");
  assert.equal(record.grain, 50);
  assert.equal(props["--vm-tint"], "hsl(250 28% 12%)");""", dark=True)

    def test_auto_stops_render_their_dark_side_or_its_complement(self):
        # (main light, stop light, system dark, rendered main, rendered stop)
        cases = [(20, 30, False, 80, 70), (20, 30, True, 20, 30), (88, 20, False, 88, 80), (88, 20, True, 12, 20),
                 (45, 50, False, 59, 59), (45, 50, True, 41, 41), (20, 80, False, 80, 80), (20, 80, True, 20, 20),
                 (20, 90, False, 80, 90), (20, 90, True, 20, 10)]
        for main, stop, dark, tint, rendered in cases:
            with self.subTest(main=main, stop=stop, dark=dark):
                grad = f"linear-gradient(160deg, hsl(250 28% {tint}%), hsl(300 28% {rendered}%))"
                glass = f"linear-gradient(160deg, hsl(250 28% {tint}% / var(--vm-glass-opacity)), hsl(300 28% {rendered}% / var(--vm-glass-opacity)))"
                self.check(auto(stops=[{"hue": 300, "light": stop}], light=main),
                           f'  assert.equal(props["--vm-grad"], {json.dumps(grad)});\n  assert.equal(props["--vm-grad-glass"], {json.dumps(glass)});', dark=dark)

    def test_a_fixed_theme_ignores_the_system_appearance(self):
        for record in (theme_with(), theme_with(mode="fixed"), theme_with(mode="dark"), theme_with(mode=None)):
            for dark in (False, True):
                with self.subTest(mode=record.get("mode"), dark=dark):
                    self.check(record, r"""
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  assert.equal(props["--vm-fg"], "#f2f2f5");""", dark=dark)

    def test_a_system_appearance_change_reapplies_the_active_theme_without_a_fade(self):
        self.check(auto(stops=[{"hue": 300, "light": 30}]), r"""
  assert.equal(props["--vm-tint"], "hsl(250 28% 80%)");
  const mark = log.length;
  media.flip(true);
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  assert.equal(props["--vm-fg"], "#f2f2f5");
  assert.equal(props["--vm-grad"], "linear-gradient(160deg, hsl(250 28% 20%), hsl(300 28% 30%))");
  media.flip(false);
  assert.equal(props["--vm-tint"], "hsl(250 28% 80%)");
  assert.equal(props["--vm-fg"], "#1b1b1f");
  assert.ok(!log.slice(mark).includes("class+:vm-tint-fade"), "a scheme change never fades");
  assert.equal(pendingTimers().length, 0);""")

    def test_the_auto_button_saves_auto_and_normalises_light_and_stops_to_the_dark_side(self):
        for before, after in [(88, 12), (45, 41), (20, 20), (30, 30), (5, 10), (95, 10), (59, 41)]:
            with self.subTest(light=before):
                self.check(theme_with(stops=[{"hue": 300, "light": 80}, {"hue": 10, "light": 50}], light=before), f"""
  const pop = await open();
  modeButton(pop, "Auto").listeners.click();
  const record = saved.get("theme:space:0");
  assert.equal(record.mode, "auto");
  assert.equal(record.light, {after});
  assert.deepEqual(record.stops, [{{ hue: 300, light: 20 }}, {{ hue: 10, light: 41 }}]);""")

    def test_the_auto_button_normalises_a_record_without_stops(self):
        self.check(theme_with(light=88), r"""
  const pop = await open();
  modeButton(pop, "Auto").listeners.click();
  assert.equal(saved.get("theme:space:0").light, 12);
  assert.equal(saved.get("theme:space:0").stops, undefined);""")

    def test_dark_and_light_save_their_light_and_drop_the_mode(self):
        self.check(auto(), r"""
  const pop = await open();
  modeButton(pop, "Dark").listeners.click();
  assert.equal(saved.get("theme:space:0").light, 18);
  assert.equal(saved.get("theme:space:0").mode, undefined);
  modeButton(pop, "Auto").listeners.click();
  modeButton(pop, "Light").listeners.click();
  assert.equal(saved.get("theme:space:0").light, 88);
  assert.equal(saved.get("theme:space:0").mode, undefined);""")

    def test_the_active_mode_button_is_pressed(self):
        cases = [(theme_with(light=20), "true,false,false"), (theme_with(light=58), "true,false,false"),
                 (theme_with(light=59), "false,true,false"), (theme_with(light=88), "false,true,false"),
                 (auto(light=20), "false,false,true"), (auto(light=88), "false,false,true")]
        for record, expected in cases:
            with self.subTest(mode=record.get("mode"), light=record["light"]):
                self.check(record, f'  const pop = await open();\n  assert.equal(pressed(pop), "{expected}");')

    def test_pressed_follows_the_clicks(self):
        self.check(theme_with(light=20), r"""
  const pop = await open();
  modeButton(pop, "Auto").listeners.click();
  assert.equal(pressed(pop), "false,false,true");
  modeButton(pop, "Light").listeners.click();
  assert.equal(pressed(pop), "false,true,false");
  modeButton(pop, "Dark").listeners.click();
  assert.equal(pressed(pop), "true,false,false");""")

    def test_the_pad_dots_show_the_rendered_light_in_auto(self):
        # top is (90 - rendered light) / 80 of the pad height
        self.check(auto(stops=[{"hue": 300, "light": 30}], light=20), r"""
  const pop = await open();
  const [main, stop] = pad(pop).children;
  near(top(main), 12.5, "main dot, system light, rendered 80");
  near(top(stop), 25, "stop dot, system light, rendered 70");
  media.flip(true);
  near(top(main), 87.5, "main dot moves on a scheme change, rendered 20");
  near(top(stop), 75, "stop dot moves too, rendered 30");""")
        self.check(auto(light=88), r"""
  const pop = await open();
  near(top(pad(pop).children[0]), 87.5, "rendered 12 in a dark system");""", dark=True)

    def test_a_fixed_theme_pad_dot_does_not_move_on_a_scheme_change(self):
        self.check(theme_with(light=20), r"""
  const pop = await open();
  const main = pad(pop).children[0];
  near(top(main), 87.5, "light 20");
  media.flip(true);
  near(top(main), 87.5, "still light 20");""")

    def test_dragging_the_pad_in_auto_edits_the_dark_side_through_the_rendered_light(self):
        self.check(auto(light=20), r"""
  const pop = await open();
  drag(pop, 250, 70);
  assert.equal(saved.get("theme:space:0").light, 30, "rendered 70 in a light system saves 30");
  assert.equal(saved.get("theme:space:0").mode, "auto");
  assert.equal(props["--vm-tint"], "hsl(250 28% 70%)");
  near(top(pad(pop).children[0]), 25, "the dot sits on the rendered light");""")

    def test_dragging_the_pad_toward_dark_in_a_light_system_clamps_to_the_rendered_59(self):
        self.check(auto(light=20), r"""
  const pop = await open();
  drag(pop, 250, 20);
  assert.equal(saved.get("theme:space:0").light, 41);
  assert.equal(props["--vm-tint"], "hsl(250 28% 59%)");
  assert.equal(props["--vm-fg"], "#1b1b1f");""")

    def test_dragging_the_pad_in_a_dark_system_saves_the_rendered_light(self):
        self.check(auto(light=20), r"""
  const pop = await open();
  drag(pop, 250, 30);
  assert.equal(saved.get("theme:space:0").light, 30);
  assert.equal(props["--vm-tint"], "hsl(250 28% 30%)");""", dark=True)

    def test_reset_clears_the_mode(self):
        self.check(auto(light=88), r"""
  const pop = await open();
  pop.children.at(-1).listeners.click();
  const record = saved.get("theme:space:0");
  assert.equal(record.mode, undefined);
  assert.equal(record.on, false);
  assert.equal(record.light, 20);
  assert.ok(!("--vm-tint" in props));""")

    def test_an_update_from_another_window_carries_the_mode(self):
        self.check(theme_with(), r"""
  assert.equal(channels.length, 1, "the mod listens on a BroadcastChannel");
  assert.equal(props["--vm-tint"], "hsl(250 28% 20%)");
  channels[0].onmessage({ data: { space: 0, theme: { on: true, hue: 100, sat: 28, light: 20, grain: 30, mode: "auto" } } });
  assert.equal(props["--vm-tint"], "hsl(100 28% 80%)", "the received auto theme renders mirrored in a light system");
  media.flip(true);
  assert.equal(props["--vm-tint"], "hsl(100 28% 20%)");""", channel=True)

    def test_the_saved_mode_is_broadcast_to_other_windows(self):
        self.check(theme_with(light=88), r"""
  const sent = [];
  channels[0].postMessage = (message) => sent.push(message);
  const pop = await open();
  modeButton(pop, "Auto").listeners.click();
  assert.equal(sent.at(-1).theme.mode, "auto");
  assert.equal(sent.at(-1).theme.light, 12);""", channel=True)
