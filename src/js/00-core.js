// Vivarc core: config, the "vm-on" marker class (all CSS is scoped to it), a small IndexedDB store,
// and a hook on Vivaldi's keyboard-shortcut event, shared by the other modules through window.__vm.
(() => {
  const defaults = {
    hideWorkspaceButton: true,
    compactBottomBar: true,
    suggestions: "ddg",
    spaceFolderTitle: "Vivarc",
  };
  const config = { ...defaults, ...(window.__vmConfig || {}) };

  const subscribers = new Set();
  const dbReady = new Promise((resolve, reject) => {
    const req = indexedDB.open("vivarc", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("kv");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  const store = {
    get: (key, fallback) => dbReady.then((db) => new Promise((resolve) => {
      const q = db.transaction("kv").objectStore("kv").get(key);
      q.onsuccess = () => resolve(q.result ?? fallback);
      q.onerror = () => resolve(fallback);
    })).catch(() => fallback),
    set: (key, value) => dbReady.then((db) => new Promise((resolve) => {
      const t = db.transaction("kv", "readwrite");
      t.objectStore("kv").put(value, key);
      t.oncomplete = () => resolve();
      t.onerror = () => resolve();
    })).catch(() => {}),
  };

  const normalise = (combo) => String(combo).toLowerCase().split("+").map((s) => s.trim()).sort().join("+");
  let last = { key: "", at: 0 };
  const handler = (...args) => {
    const combo = args.find((a) => typeof a === "string");
    if (!combo) return;
    const key = normalise(combo);
    const now = Date.now();
    if (key === last.key && now - last.at < 250) return;
    last = { key, at: now };
    subscribers.forEach((fn) => fn(key, combo));
  };
  try {
    vivaldi.tabsPrivate.onKeyboardShortcut.addListener(handler);
  } catch (e) {
    console.warn("[vivarc] shortcut hook unavailable:", e);
  }

  // Vivaldi keeps a tab's tile ("split view") membership in its vivExtData JSON: {tiling: {id, layout, type, index}}.
  const tilingOf = (tab) => {
    try { return JSON.parse(tab?.vivExtData || "{}").tiling; } catch (_) { return undefined; }
  };

  window.__vm = { config, store, normalise, tilingOf, onShortcut: (fn) => subscribers.add(fn) };

  // Vivaldi re-renders #browser's class list, so the marker classes are re-applied whenever they go missing.
  const markListeners = new Set();
  let watched = null;
  const mark = () => {
    const browser = document.querySelector("#browser");
    if (!browser) return false;
    browser.classList.add("vm-on");
    browser.classList.toggle("vm-compact-bottom", !!config.compactBottomBar);
    browser.classList.toggle("vm-hide-workspaces", !!config.hideWorkspaceButton);
    markListeners.forEach((fn) => fn(browser));
    if (watched !== browser) {
      watched = browser;
      new MutationObserver(() => { if (!browser.classList.contains("vm-on")) mark(); })
        .observe(browser, { attributes: true, attributeFilter: ["class"] });
    }
    return true;
  };
  window.__vm.onMark = (fn) => { markListeners.add(fn); if (watched) fn(watched); };
  if (!mark()) {
    const observer = new MutationObserver(() => { if (mark()) observer.disconnect(); });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
  // The UI modules stay dormant unless the stylesheet is loaded too (e.g. a profile not set up yet).
  let cssResolve;
  window.__vm.cssLoaded = false;
  window.__vm.ready = new Promise((resolve) => { cssResolve = resolve; });
  const checkCss = (tries = 0) => {
    const browser = document.querySelector("#browser");
    if (browser && getComputedStyle(browser).getPropertyValue("--vm-css").trim() === "1") {
      window.__vm.cssLoaded = true;
      cssResolve(true);
    } else if (tries < 20) {
      setTimeout(() => checkCss(tries + 1), 250);
    } else {
      cssResolve(false);
    }
  };
  checkCss();
  console.log("[vivarc] core started");
})();
