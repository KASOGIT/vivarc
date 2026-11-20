// The sidebar's auto-hide (Cmd+S) is Vivaldi's own. Vivarc tunes it in two ways:
// - Its delays are hidden Vivaldi prefs (vivaldi.biscuit.*, read live): the "Auto-hide after" setting replaces the
//   800 ms close delay, and the closing slide is shortened from 300 ms.
// - Vivaldi hides the bar once, when its native hot spot reports the pointer away, and skips it while something in
//   the bar has focus (on macOS's default keyboard setting, any button counts). Nothing retries, so after a click
//   on back, reload, Downloads or a profile chip the bar stayed open. When the pointer has been out for the delay,
//   Vivarc drops that focus: the blur sends Vivaldi down its own hide path, which still keeps the bar for open
//   menus, resizing and typing. Text fields keep their focus, as Vivaldi intends.
(() => {
  const CLOSE_DELAY = "vivaldi.biscuit.auto_hide_close_delay";
  const CLOSING_SPEED = "vivaldi.biscuit.auto_hide_closing_animation_speed";
  const CLOSING_MS = 150;
  const MARGIN = 50; // lets Vivaldi's own timer go first when nothing blocks it

  const prefs = (delay) => ({ [CLOSE_DELAY]: delay, [CLOSING_SPEED]: Math.min(CLOSING_MS, delay) });

  // Focus that Vivarc may take away from the bar: not nothing, and not somewhere the user types.
  const releasable = (el) => {
    const tag = el?.tagName;
    if (!tag || tag === "BODY") return false;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable) return false;
    return true;
  };

  const api = { prefs, releasable, CLOSE_DELAY, CLOSING_SPEED };
  window.__vm.autohide = api;
  if (!window.__vm.settings?.get || typeof vivaldi === "undefined") return;

  const { settings } = window.__vm;
  const delay = () => settings.get("hideDelay");

  let written = null;
  let pending = null;
  const write = () => {
    const want = prefs(delay());
    const key = JSON.stringify(want);
    if (key === written) return;
    written = key;
    for (const [path, value] of Object.entries(want)) {
      Promise.resolve(vivaldi.prefs.set({ path, value })).catch((e) => console.warn("[vivarc] auto-hide delay:", e));
    }
  };
  settings.onChange(() => { clearTimeout(pending); pending = setTimeout(write, 250); }); // a slider drag writes once
  write();

  const wrapper = () => document.querySelector("#tabs-tabbar-container")?.closest(".auto-hide-wrapper");
  // Vivarc's own menus and fields sit outside the bar; the bar stays while one is open.
  const vivarcOpen = () => !!document.querySelector(".vm-menu, .vm-rename-float, .vm-theme-pop, #vm-cmd, .vm-set-overlay");

  let timer = null;
  const release = () => {
    timer = null;
    const bar = wrapper();
    const focused = document.activeElement;
    if (!bar?.classList.contains("show") || !bar.contains(focused) || bar.matches(":hover")) return;
    if (!releasable(focused) || vivarcOpen()) return;
    focused.blur();
  };
  document.addEventListener("mouseout", (e) => {
    const bar = wrapper();
    if (!bar || !bar.contains(e.target) || bar.contains(e.relatedTarget)) return;
    clearTimeout(timer);
    timer = setTimeout(release, delay() + MARGIN);
  }, true);
  document.addEventListener("mouseover", (e) => {
    if (timer && wrapper()?.contains(e.target)) { clearTimeout(timer); timer = null; }
  }, true);
})();
