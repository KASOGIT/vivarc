// Arc's auto-archive: a tab left unopened for the chosen number of hours is closed. And the archive itself (#121). Only unpinned tabs of this
// window; every window runs its own copy of the mod, so each looks after its own tabs.
(() => {
  const HOUR = 3600 * 1000;
  const EVERY = 60 * 1000;

  // keep(tab): extra tabs to spare (bound to a pin or favorite, in a split view). A tab with no last-access time is
  // spared rather than guessed at.
  const stale = (tabs, now, hours, keep) => tabs.filter((t) => !t.active && !t.pinned && !t.audible && !keep(t) &&
    t.lastAccessed != null && now - t.lastAccessed > hours * HOUR);

  // ---- The archive, like Arc's Archived Tabs (#121) ----
  // Archiving closes a tab but keeps it: "View Archived Tabs" in the command bar lists the pages, and Enter restores
  // one into the space it came from. The list lives in the profile's IndexedDB (key "archive"), newest first,
  // at most MAX entries and one per address and space (archiving it again moves it to the top).
  const KEY = "archive";
  const MAX = 1000;
  const entry = (tab, spaceName, now = Date.now()) => ({
    id: `${now.toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    url: tab.url,
    title: tab.title || tab.url,
    favicon: /^(https?:|data:)/.test(tab.favIconUrl || "") ? tab.favIconUrl : "",
    space: window.__vm.workspaces?.of(tab) ?? 0,
    spaceName: spaceName || "",
    at: now,
  });
  const add = (list, entries, max = MAX) => {
    const key = (e) => `${e.space}\n${e.url}`;
    const fresh = new Set(entries.map(key));
    return [...entries, ...list.filter((e) => !fresh.has(key(e)))].slice(0, max);
  };
  const remove = (list, id) => list.filter((e) => e.id !== id);
  const search = (list, text, limit = Infinity) => {
    const words = String(text || "").toLowerCase().split(/\s+/).filter(Boolean);
    return list.filter((e) => words.every((w) => `${e.title} ${e.url} ${e.spaceName}`.toLowerCase().includes(w))).slice(0, limit);
  };
  const ago = (at, now = Date.now()) => {
    const minutes = Math.max(0, Math.floor((now - at) / 60000));
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours} h ago`;
    const days = Math.round(hours / 24);
    return days === 1 ? "yesterday" : `${days} days ago`;
  };
  const describe = (e, now) => {
    let host = "";
    try { host = new URL(e.url).hostname.replace(/^www\./, ""); } catch (_) {}
    return [host, e.spaceName, ago(e.at, now)].filter(Boolean).join(" · ");
  };

  const api = { stale, MAX, entry, add, remove, search, ago, describe, busy: false };
  window.__vm.archive = api;
  if (!window.__vm.store) return;

  const store = window.__vm.store;
  const load = async () => (await store.get(KEY, [])) || [];
  const save = (list) => store.set(KEY, list);
  const toast = (message) => window.dispatchEvent(new CustomEvent("vm-toast", { detail: message }));
  const isPage = (tab) => /^https?:|^file:/.test(tab?.url || "");
  const BLANK = /^(chrome|vivaldi):\/\/(newtab|vivaldi-webui\/startpage)/;

  // Archive and close `tabs` (web pages only). A window never loses its last tab: a blank one opens first.
  const archiveTabs = async (tabs) => {
    const pages = tabs.filter(isPage);
    if (!pages.length) return 0;
    const now = Date.now();
    const nameOf = window.__vm.spaceNameOf || (() => "");
    await save(add(await load(), pages.map((t, i) => entry(t, nameOf(window.__vm.workspaces?.of(t) ?? 0), now - i))));
    const left = await chrome.tabs.query({ windowId: pages[0].windowId });
    if (left.every((t) => pages.some((p) => p.id === t.id))) await chrome.tabs.create({ windowId: pages[0].windowId });
    await chrome.tabs.remove(pages.map((t) => t.id));
    toast(pages.length === 1 ? "Archived Tab" : `Archived ${pages.length} Tabs`);
    return pages.length;
  };

  // Reopen an archived page in its own space (the current one if that space is gone) and drop it from the archive.
  // Vivaldi 8.3 ignores workspaceId in vivExtData: a tab changes space only through tabsPrivate.move (what its
  // "Move to Workspace" menu uses), and only into a workspace open in the window, so an empty space is switched to
  // first and the blank tab Vivaldi opens there is navigated. While this runs the sidebar does not stamp the new tab.
  const restore = async (e) => {
    const ws = window.__vm.workspaces;
    const windowId = window.vivaldiWindowId;
    const tabs = await chrome.tabs.query({ windowId });
    const current = ws.of(tabs.find((t) => t.active));
    const target = (window.__vm.spaceExists?.(e.space) ?? true) ? e.space : current;
    api.busy = true;
    try {
      if (target === current) {
        await chrome.tabs.create({ windowId, url: e.url, active: true });
      } else if (ws.tabsIn(tabs, target).length) {
        const tab = await chrome.tabs.create({ windowId, url: e.url, active: false });
        await vivaldi.tabsPrivate.move({ tabIds: [tab.id], target: "last", tweaks: ["do-not-reparent"], workspaceId: target || null });
        await chrome.tabs.update(tab.id, { active: true });
      } else {
        const activate = ws.findSwitcher(chrome.extension.getBackgroundPage?.()?.webpackChunkgapp_browser_react);
        window.__vm.switchingSpace = true;
        try { await activate?.(windowId, target); } finally { window.__vm.switchingSpace = false; }
        const [active] = await chrome.tabs.query({ active: true, windowId });
        if (active && ws.of(active) === target && BLANK.test(active.pendingUrl || active.url || "")) await chrome.tabs.update(active.id, { url: e.url });
        else await chrome.tabs.create({ windowId, url: e.url, active: true });
      }
    } finally {
      setTimeout(() => { api.busy = false; }, 300);
    }
    await save(remove(await load(), e.id));
  };
  const forget = async (id) => save(remove(await load(), id));
  Object.assign(api, { load, archiveTabs, restore, forget });

  const { settings, pins, tilingOf } = window.__vm;
  const keep = (tab) => pins.pinOf(tab) !== undefined || !!tilingOf(tab);

  const sweep = async () => {
    if (!settings.get("archive")) return;
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const ids = stale(tabs, Date.now(), settings.get("archiveHours"), keep).map((t) => t.id);
    if (ids.length) chrome.tabs.remove(ids);
  };

  window.__vm.ready.then((ok) => {
    if (!ok) return;
    setInterval(sweep, EVERY);
  });
})();
