// Arc's Spaces on top of Vivaldi Workspaces: which workspace a tab is in, the list of spaces for the space bar,
// where switching to a space goes, and which pinned-links folder belongs to which space.
// A workspace is not a login: all of them share the profile's cookies (profiles are the isolation boundary).
(() => {
  const ARC_PREFIX = "Arc - ";

  // Vivaldi keeps the workspace id in the tab's vivExtData JSON; no key means the default space (id 0).
  const of = (tab) => {
    try { return Number(JSON.parse(tab?.vivExtData || "{}").workspaceId) || 0; } catch (_) { return 0; }
  };
  const tabsIn = (tabs, id) => tabs.filter((t) => of(t) === id);
  const activeId = (tabs) => {
    const active = tabs.find((t) => t.active);
    return active ? of(active) : 0;
  };

  // What the sidebar lists: the active space's tabs. With no known workspace everything is one space, so a failed
  // read of the list never hides tabs.
  const scope = (tabs, list) => {
    if (!list?.length) return { active: 0, tabs };
    const active = activeId(tabs);
    return { active, tabs: tabsIn(tabs, active) };
  };

  // Without any workspace there is only one space, so no bar.
  const items = (list, defaultName) => {
    if (!list?.length) return [];
    return [{ id: 0, name: defaultName, emoji: "" }, ...list.map((w) => ({ id: w.id, name: w.name, emoji: w.emoji || "" }))];
  };

  // Where switching to a space lands: its most recently used tab (Vivaldi then switches the workspace by itself).
  const recentTab = (tabs, id) => {
    const own = tabsIn(tabs, id);
    if (!own.length) return null;
    return own.reduce((best, t) => ((t.lastAccessed ?? 0) > (best.lastAccessed ?? 0) ||
      ((t.lastAccessed ?? 0) === (best.lastAccessed ?? 0) && t.index > best.index) ? t : best));
  };

  const label = (folder) => folder.title.startsWith(ARC_PREFIX) ? folder.title.slice(ARC_PREFIX.length) : folder.title;
  const same = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase();

  // folders: every bookmark folder that holds a Pinned folder, in bookmark order. A workspace takes the folder with
  // its name; the default space is the first folder nobody claims (the only one, if all are claimed).
  const assign = (folders, list) => {
    const byId = {};
    const used = new Set();
    for (const w of list || []) {
      const found = folders.find((f) => !used.has(f.id) && same(label(f), w.name));
      if (found) { byId[w.id] = found; used.add(found.id); }
    }
    return { default: folders.find((f) => !used.has(f.id)) ?? folders[0] ?? null, byId };
  };

  // A tab opened while a space is active joins it. Vivaldi does not do this for tabs a mod or a command bar opens,
  // so they would land in the default space. Returns the new vivExtData, or null when nothing needs writing.
  // Every window runs its own copy of the mod and sees the tabs of all windows, so only this window's tabs are stamped.
  const stamp = (tab, activeSpace, windowId) => {
    if (!activeSpace || tab?.windowId !== windowId) return null;
    let data;
    try { data = JSON.parse(tab?.vivExtData || "{}") || {}; } catch (_) { data = {}; }
    if ("workspaceId" in data) return null;
    return JSON.stringify({ ...data, workspaceId: activeSpace });
  };

  // A mod can neither create a workspace (Vivaldi reads its list once) nor press a shortcut for the user: events a
  // mod dispatches never reach Vivaldi's shortcut handler. So the install binds "Create New Workspace" to this chord,
  // and the + tile and the command bar tell the user to press it.
  const CREATE_KEY = "ctrl+meta+n";
  const KEY_NAMES = { ctrl: "Ctrl", meta: "Cmd", alt: "Option", shift: "Shift" };
  const CREATE_HINT = `Press ${CREATE_KEY.split("+").map((k) => KEY_NAMES[k] || k.toUpperCase()).join("+")} to create a space`;

  // Vivaldi has no extension API to delete a workspace, only its own store. Its webpack runtime hands out the module
  // list through the chunk array's push; the module that defines removeWorkspace is found by its source and loaded
  // only if it already ran. Returns (windowId, id) => Promise, or null when Vivaldi no longer looks like this.
  const findRemover = (chunks) => {
    try {
      let load;
      chunks.push([[Symbol("vivarc")], {}, (require) => { load = require; }]);
      for (const [id, factory] of Object.entries(load?.m || {})) {
        if (!String(factory).includes("removeWorkspace(")) continue;
        let exported;
        try { exported = load(id); } catch (_) { continue; }
        for (const key of Object.keys(exported || {})) {
          const manager = exported[key];
          if (typeof manager?.removeWorkspace === "function") return (windowId, workspaceId) => manager.removeWorkspace(windowId, workspaceId);
        }
      }
    } catch (_) {}
    return null;
  };

  const removalQuestion = (name, tabCount) =>
    `Delete \u201c${name}\u201d${tabCount ? ` and close its ${tabCount} ${tabCount === 1 ? "tab" : "tabs"}` : ""}?`;

  window.__vm.workspaces = { of, tabsIn, activeId, scope, items, recentTab, label, assign, stamp, findRemover, removalQuestion, CREATE_HINT };
})();
