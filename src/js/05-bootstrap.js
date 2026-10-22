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
  const VERSION = 4;
  const TOGGLE = "meta+s";

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
      ["tabbar_before", ["Spacer", "WorkspaceButton"], {}],
      ["tabbar_after", [], { VPNButton: "PanelDownloads" }],
    ];
    let whole = null;
    for (const [name, remove, swap] of edits) {
      let list = await get(`vivaldi.toolbars.${name}`);
      if (!Array.isArray(list)) {
        whole ||= (await get("vivaldi.toolbars")) || {};
        list = whole[name];
      }
      if (!Array.isArray(list)) continue;
      const next = tidyToolbar(list, remove, swap);
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
    await set("vivaldi.actions", actions);
  };

  // A brand-new profile opens Vivaldi's own welcome tab; Vivarc's guide takes its place.
  const replaceWelcome = async () => {
    if (!cfg.startUrl) return;
    await set("vivaldi.startup.has_seen_welcome_page", true);
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const welcome = tabs.find((t) => /^(vivaldi|chrome):\/\/(vivaldi-webui\/)?welcome/.test(t.pendingUrl || t.url || "") || t.title === "Welcome to Vivaldi");
    if (welcome) await chrome.tabs.update(welcome.id, { url: cfg.startUrl });
  };

  const configure = async () => {
    if ((await window.__vm.store.get("bootstrap", 0)) >= VERSION) return;
    await bindShortcuts();
    await set("vivaldi.tabs.bar.position", 1);
    await tidyToolbars();
    await replaceWelcome();
    await window.__vm.store.set("bootstrap", VERSION);
  };

  configure().catch((e) => console.warn("[vivarc] profile setup:", e));
})();
