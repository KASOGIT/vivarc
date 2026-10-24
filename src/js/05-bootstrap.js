// Sets up a Vivaldi profile that the installer has not configured (for example one created later): tabs on
// the left, Cmd+T freed for the command bar, Cmd+S for the sidebar, toolbar tidy-up. All of it applies live.
(() => {
  const cfg = window.__vm.config;
  if (cfg.autoConfigureProfiles === false) return;

  const get = async (path) => (await vivaldi.prefs.get(path))?.value;
  const set = (path, value) => vivaldi.prefs.set({ path, value });
  const FREED = "meta+t";
  const COPY_URL = "shift+meta+c";

  // Bump when the steps change: profiles already set up then run the (idempotent) steps once more.
  const VERSION = 9;
  const TOGGLE = "meta+s";
  const PROFILE_KEYS = ["ctrl+meta+left", "ctrl+meta+right"]; // the profile switcher's previous/next, handled in 06-spaces.js
  const SPACE_KEYS = { COMMAND_WORKSPACE_SWITCH_BACK_ORDER: "alt+meta+left", COMMAND_WORKSPACE_SWITCH_FORWARD_ORDER: "alt+meta+right" }; // like Arc's spaces

  // The address bar and navigation buttons live inside the sidebar; the top bar is hidden.
  const SIDEBAR_TOOLBAR = ["TabButton", "Extensions", "FlexibleSpacer", "Back", "Reload", "Forward", "AddressField"];

  const SIDEBAR_BOTTOM = ["NewTab", "FlexibleSpacer", "AccountButton", "FlexibleSpacer", "PanelDownloads", "UpdateButton"];

  const tidyToolbar = (list, remove, swap) => {
    const out = [];
    for (const item of list) {
      const next = swap[item] || item;
      if (remove.includes(next)) continue;
      if (!out.includes(next) || next === "FlexibleSpacer") out.push(next);
    }
    return out;
  };

  const tidyToolbars = async () => {
    const edits = [
      ["tabbar_before", ["Spacer", "WorkspaceButton"], {}, "AddressField", SIDEBAR_TOOLBAR],
      ["tabbar_after", [], { VPNButton: "PanelDownloads" }, "AccountButton", SIDEBAR_BOTTOM],
    ];
    let whole = null;
    for (const [name, remove, swap, marker, fallback] of edits) {
      let list = await get(`vivaldi.toolbars.${name}`);
      if (!Array.isArray(list)) {
        whole ||= (await get("vivaldi.toolbars")) || {};
        list = whole[name];
      }
      if (!Array.isArray(list)) continue;
      let next = tidyToolbar(list, remove, swap);
      if (!next.includes(marker)) next = [...fallback];
      if (next.join() === list.join()) continue;
      if (whole && whole[name] === list) whole[name] = next;
      else await set(`vivaldi.toolbars.${name}`, next);
    }
    if (whole) await set("vivaldi.toolbars", whole);
  };

  const bindShortcuts = async () => {
    const actions = await get("vivaldi.actions");
    if (!Array.isArray(actions) || !actions[0]) return;
    const table = actions[0];
    const command = (name) => {
      const cmd = (table[name] ||= { shortcuts: [] });
      cmd.shortcuts ||= [];
      return cmd;
    };
    for (const name of ["COMMAND_NEW_TAB", "COMMAND_SHOW_QUICK_COMMANDS"]) {
      const cmd = command(name);
      cmd.shortcuts = cmd.shortcuts.filter((s) => s !== FREED);
    }
    const copy = command("COMMAND_PAGE_COPY_URL");
    if (!copy.shortcuts.includes(COPY_URL)) copy.shortcuts.push(COPY_URL);
    command("COMMAND_SAVE_PAGE").shortcuts = command("COMMAND_SAVE_PAGE").shortcuts.filter((s) => s !== TOGGLE);
    command("COMMAND_TOGGLE_AUTO_HIDE_TAB_BAR").shortcuts = [TOGGLE];
    const taken = [...PROFILE_KEYS, ...Object.values(SPACE_KEYS)];
    for (const cmd of Object.values(table)) {
      if (Array.isArray(cmd?.shortcuts)) cmd.shortcuts = cmd.shortcuts.filter((s) => !taken.includes(s));
    }
    for (const [name, key] of Object.entries(SPACE_KEYS)) command(name).shortcuts.push(key);
    await set("vivaldi.actions", actions);
  };

  // A brand-new profile opens Vivaldi's own welcome tab, possibly after this code has run:
  // watch for it for a while and swap in Vivarc's guide.
  const isWelcome = (t) => /^(vivaldi|chrome):\/\/(vivaldi-webui\/)?welcome|\/components\/welcome\/welcome\.html/.test(t.pendingUrl || t.url || "");
  const replaceWelcome = async () => {
    if (!cfg.startUrl) return;
    await set("vivaldi.startup.has_seen_welcome_page", true);
    let done = false;
    const swap = (tab) => {
      if (done || !isWelcome(tab)) return;
      done = true;
      chrome.tabs.update(tab.id, { url: cfg.startUrl }).catch((e) => console.warn("[vivarc] guide page:", e));
    };
    (await chrome.tabs.query({ currentWindow: true })).forEach(swap);
    chrome.tabs.onCreated.addListener(swap);
    chrome.tabs.onUpdated.addListener((_id, _change, tab) => swap(tab));
    setTimeout(() => { done = true; }, 20000);
  };

  // The sidebar needs the tab bar on a side. A new profile's welcome flow can reset the position after
  // the first set, so it is checked again at every start and a few times early on.
  const ensureSideTabs = async () => {
    const position = await get("vivaldi.tabs.bar.position");
    if (position === 1 || position === 2 || position === "left" || position === "right") return;
    await set("vivaldi.tabs.bar.position", "left"); // the UI compares the enum by name, so a number would not take effect live
  };

  const configure = async () => {
    await ensureSideTabs();
    for (const delay of [4000, 12000, 30000]) setTimeout(() => ensureSideTabs().catch(() => {}), delay);
    if ((await window.__vm.store.get("bootstrap", 0)) >= VERSION) return;
    await bindShortcuts();
    await tidyToolbars();
    await set("vivaldi.address_bar.visible", false);
    await set("vivaldi.panels.position", "right");
    await set("vivaldi.auto_hide.enabled", true);
    for (const [key, value] of [["panel", true], ["tab_bar", false], ["address_bar", false], ["status_bar", false],
      ["bookmarks_bar", false], ["show_introduction", false]]) await set(`vivaldi.auto_hide.${key}`, value);
    await set("vivaldi.status_bar.display", "overlay");
    if (!(await window.__vm.store.get("bootstrap", 0))) await set("vivaldi.tabs.bar.width", 323);
    await replaceWelcome();
    await window.__vm.store.set("bootstrap", VERSION);
  };

  configure().catch((e) => console.warn("[vivarc] profile setup:", e));
})();
