// Puts the demo profile back to the storyboard's start state (run before every take): settings and theme at their
// defaults, no split view, the favorites and pin the take adds removed, the default space's tabs open, GitHub active.
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const vm = window.__vm;
  vm.settings.set("glass", false);
  vm.settings.set("urlBar", false);
  vm.settings.set("updateCheck", false);
  window.dispatchEvent(new CustomEvent("vm-open-theme"));
  await wait(300);
  document.querySelector(".vm-theme-reset")?.click();
  await wait(200);
  document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
  document.querySelector(".vm-set-close")?.click();

  const urlOf = (t) => t.pendingUrl || t.url;
  const inDefault = (t) => !JSON.parse(t.vivExtData || "{}").workspaceId;
  for (const t of await chrome.tabs.query({})) {
    if (vm.tilingOf(t)) await vm.commandBar.closeSplitView(t).catch(() => {});
  }
  await wait(400);
  for (const t of await chrome.tabs.query({})) {
    const scratch = /startpage|^about:blank|ycombinator|youtube\.com|apple\.com/.test(urlOf(t));
    if (scratch && (inDefault(t) || urlOf(t).includes("startpage"))) await chrome.tabs.remove(t.id).catch(() => {});
  }

  const vivarc = (await chrome.bookmarks.getTree())[0].children[0].children.find((n) => n.title === "Vivarc");
  for (const folder of vivarc.children) {
    for (const b of (await chrome.bookmarks.getSubTree(folder.id))[0].children || []) {
      if (b.url && /vivaldi\.com\/blog|excalidraw|drive\.google|google\.com\/maps|calendar\.google/.test(b.url)) await chrome.bookmarks.remove(b.id);
    }
  }

  const win = await chrome.windows.getCurrent();
  const tabs = await chrome.tabs.query({});
  for (const url of ["https://excalidraw.com/", "https://en.wikipedia.org/wiki/Web_browser", "https://github.com/KASOGIT/vivarc", "https://vivaldi.com/blog/"]) {
    if (!tabs.some((t) => urlOf(t).startsWith(url) && inDefault(t))) await chrome.tabs.create({ windowId: win.id, url, active: false });
  }
  await wait(500);
  const github = (await chrome.tabs.query({})).find((t) => urlOf(t).startsWith("https://github.com/KASOGIT/vivarc") && inDefault(t));
  await chrome.tabs.update(github.id, { active: true, ...(urlOf(github) === "https://github.com/KASOGIT/vivarc" ? {} : { url: "https://github.com/KASOGIT/vivarc" }) });
  await chrome.windows.update(win.id, { left: 100, top: 80, width: 1280, height: 800, focused: true });
  return "reset";
})()
