// One-time content for a fresh demo profile: spaces with pins and tabs. Run in window.html after `demo.sh setup`
// relaunched Vivaldi. Learned on Vivaldi 8.3:
// - workspaces written into Preferences, or a workspaceId put in a tab's vivExtData (create or update), are ignored;
//   tabsPrivate.move({workspaceId}) to a hand-made id also does nothing. Spaces come from Vivaldi's own workspace
//   manager (webpack module with addWorkspace) and tabs land in a space by being created while it is active.
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const chunks = chrome.extension.getBackgroundPage().webpackChunkgapp_browser_react;
  let load;
  chunks.push([[Symbol("vivarc-demo")], {}, (require) => { load = require; }]);
  let manager;
  for (const [id, factory] of Object.entries(load.m)) {
    if (manager || !String(factory).includes("removeWorkspace(")) continue;
    try { manager = Object.values(load(id) || {}).find((m) => typeof m?.addWorkspace === "function"); } catch (_) {}
  }
  const switchTo = window.__vm.workspaces.findSwitcher(chunks);

  const SPACES = [
    ["Work", "💼", [], []],
    ["Design", "🎨", [["Dribbble", "https://dribbble.com/"], ["Figma Community", "https://www.figma.com/community"], ["Coolors", "https://coolors.co/"]],
      ["https://dribbble.com/shots/popular", "https://unsplash.com/"]],
    ["Weekend", "🌴", [["OpenStreetMap", "https://www.openstreetmap.org/"], ["Wikivoyage", "https://en.wikivoyage.org/"]],
      ["https://en.wikivoyage.org/wiki/Lisbon"]],
  ];
  const listed = async () => (await vivaldi.prefs.get("vivaldi.workspaces.list")).value || [];
  for (const [name, emoji] of SPACES) {
    if (!(await listed()).some((w) => w.name === name)) await manager.addWorkspace(name, "", emoji, undefined, true);
    await wait(100);
  }
  const ids = Object.fromEntries((await listed()).map((w) => [w.name, w.id]));

  const root = (await chrome.bookmarks.getTree())[0].children[0];
  for (const [name, , pins] of SPACES) {
    if (!pins.length) continue;
    const folder = root.children.find((n) => n.title === name) || await chrome.bookmarks.create({ parentId: root.id, title: name });
    const kids = await chrome.bookmarks.getChildren(folder.id);
    const pinned = kids.find((n) => n.title === "Pinned") || await chrome.bookmarks.create({ parentId: folder.id, title: "Pinned" });
    if ((await chrome.bookmarks.getChildren(pinned.id)).length) continue;
    for (const [title, url] of pins) await chrome.bookmarks.create({ parentId: pinned.id, title, url });
  }

  const win = await chrome.windows.getCurrent();
  const open = await chrome.tabs.query({});
  for (const [name, , , tabs] of SPACES) {
    if (!tabs.length || open.some((t) => window.__vm.workspaces.of(t) === ids[name])) continue;
    await switchTo(window.vivaldiWindowId, ids[name]);
    await wait(1500);
    for (const url of tabs) { await chrome.tabs.create({ windowId: win.id, url }); await wait(800); }
  }
  await switchTo(window.vivaldiWindowId, 0);
  await wait(1500);
  // Switching to an empty space opens a start page there; the reset closes them.
  window.__vm.settings.set("updateCheck", false);
  return "seeded: " + JSON.stringify(ids);
})()
