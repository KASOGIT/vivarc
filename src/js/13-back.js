// Arc's Back on an opened tab: when a link opened the tab (target=_blank, window.open, Cmd+click) and the tab has
// no page to go back to, Back closes it and returns to the tab the link was on. Vivaldi does nothing there.
// Back reaches Vivarc three ways: the toolbar button (disabled, so its click falls through to the toolbar, see
// vivarc.css), Vivaldi's Back shortcut, and its mouse and rocker gestures. A trackpad swipe is not covered: Chromium
// handles it without asking Vivaldi, and with no page to go back to it reports nothing.
(() => {
  // The decision, kept pure for the tests. source: the tab the link was on, if it is still open. noHistory: the tab
  // cannot go back, read before Vivaldi acts on the same Back. kept: a pin, favorite, split view or Peek tab.
  const shouldClose = ({ tab, source, noHistory, kept }) => !!tab && !!source && noHistory === true && !kept &&
    !tab.pinned && source.id !== tab.id && source.windowId === tab.windowId;

  // Vivaldi's shortcut text ("Meta+Left", "Alt+ArrowLeft") in the order normalise() gives.
  const comboKey = (combo) => String(combo).toLowerCase().replace(/\s+/g, "").split("+")
    .map((k) => k.replace(/^arrow|arrow$/, "")).filter(Boolean).sort().join("+");

  // Only chords: Backspace and Z are Back too when Vivaldi's single-key shortcuts are on, but they are also typing.
  const DEFAULT_KEYS = { mac: ["meta+left", "meta+["], win: ["alt+left", "ctrl+left"] };
  const backKeys = (shortcuts, platform) => [...new Set([...(Array.isArray(shortcuts) ? shortcuts : DEFAULT_KEYS[platform] || []),
    ...(platform === "mac" ? ["meta+["] : [])].filter((s) => String(s).includes("+")).map(comboKey))];

  // Asked in the page when a shortcut comes in: a key that is Back for Vivaldi also moves the caret in a text field.
  const EDITING = `(() => { const a = document.activeElement;
    return !!a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT|IFRAME)$/.test(a.tagName)); })()`;

  window.__vm.back = { shouldClose, comboKey, backKeys };
  if (!window.__vm.store) return;

  const { settings, pins, peek, tilingOf, platform } = window.__vm;
  const opened = new Map(); // tab id -> id of the tab whose link opened it

  const webviewOf = (id) => document.querySelector(`webview[tab_id="${id}"]`);
  const backButtonDisabled = () => [...document.querySelectorAll('[data-name="Back"]')]
    .some((el) => el.matches(":disabled") || !!el.querySelector("button:disabled"));
  // Read synchronously, in the same event Vivaldi handles: the webview only updates it once a navigation commits.
  // Without canGoBack on the webview, the active tab's greyed-out Back button says the same.
  const noHistory = (id, active) => {
    const webview = webviewOf(id);
    if (typeof webview?.canGoBack === "function") return !webview.canGoBack();
    return active ? backButtonDisabled() : false;
  };
  const kept = (tab) => pins.pinOf(tab) !== undefined || !!tilingOf(tab) || !!peek?.isPeekTab?.(tab, peek.tabIds());

  const get = (id) => new Promise((resolve) => chrome.tabs.get(id, (t) => resolve(chrome.runtime.lastError ? null : t)));
  let myWindow = null;
  chrome.windows.getCurrent((w) => { myWindow = w?.id ?? null; });
  const closing = new Set();

  // check(tab): a last look before closing (the keyboard path asks the page about focus first).
  const tryClose = async (tabId, history, check) => {
    if (!settings.get("backCloses") || closing.has(tabId) || !opened.has(tabId)) return;
    const [tab, source] = await Promise.all([get(tabId), get(opened.get(tabId))]);
    if (!tab || tab.windowId !== myWindow) return;
    if (!shouldClose({ tab, source, noHistory: history, kept: kept(tab) })) return;
    if (check && !(await check(tab))) return;
    closing.add(tabId);
    chrome.tabs.update(source.id, { active: true }, () => {
      void chrome.runtime.lastError;
      chrome.tabs.remove(tabId, () => { void chrome.runtime.lastError; closing.delete(tabId); });
    });
  };
  const activeTab = () => new Promise((resolve) => chrome.tabs.query({ active: true, currentWindow: true }, ([t]) => resolve(t)));
  // Every opened tab's history is read before the first await, for the reason given at noHistory.
  const onBack = (check) => {
    const before = new Map([...opened.keys()].map((id) => [id, noHistory(id, false)]));
    const button = backButtonDisabled();
    activeTab().then((tab) => {
      if (tab && opened.has(tab.id)) tryClose(tab.id, before.has(tab.id) && webviewOf(tab.id) ? before.get(tab.id) : button, check);
    });
  };

  chrome.webNavigation.onCreatedNavigationTarget.addListener(({ sourceTabId, tabId }) => {
    if (sourceTabId != null && tabId != null && sourceTabId !== tabId) opened.set(tabId, sourceTabId);
  });
  chrome.tabs.onRemoved.addListener((id) => opened.delete(id));
  chrome.tabs.onReplaced?.addListener((added, removed) => {
    if (opened.has(removed)) { opened.set(added, opened.get(removed)); opened.delete(removed); }
  });

  // Vivaldi's own Back shortcuts and mouse gestures, as set in its settings.
  let keys = backKeys(null, platform);
  let gestures = ["4"];
  Promise.resolve(vivaldi.prefs.get("vivaldi.actions")).then((pref) => {
    const back = pref?.value?.[0]?.COMMAND_PAGE_BACK;
    keys = backKeys(back?.shortcuts, platform);
    if (Array.isArray(back?.gestures)) gestures = back.gestures.map(String);
  }).catch(() => {});
  const notEditing = (tab) => new Promise((resolve) => {
    const ui = document.activeElement;
    if (ui && ui.tagName !== "WEBVIEW" && (ui.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ui.tagName))) return resolve(false);
    const webview = webviewOf(tab.id);
    if (!webview?.executeScript) return resolve(true);
    webview.executeScript({ code: EDITING }, (result) => resolve(!chrome.runtime.lastError && result?.[0] === false));
  });
  try {
    vivaldi.tabsPrivate.onKeyboardShortcut.addListener((windowId, combo, autoRepeat, fromDevtools) => {
      if (windowId !== window.vivaldiWindowId || autoRepeat || fromDevtools) return;
      if (keys.includes(comboKey(combo))) onBack(notEditing);
    });
  } catch (_) {}

  // Mouse gestures and the rocker gesture (hold right, click left), when they are on in Vivaldi.
  try {
    vivaldi.tabsPrivate.onMouseGesture.addListener((windowId, _x, _y, directions) => {
      if (windowId === window.vivaldiWindowId && gestures.includes(String(directions))) onBack();
    });
    vivaldi.tabsPrivate.onRockerGesture.addListener((windowId, isLeft) => {
      if (windowId === window.vivaldiWindowId && isLeft) onBack();
    });
  } catch (_) {}

  // A click on the disabled Back button lands on the toolbar behind it; find the button by position.
  document.addEventListener("click", (e) => {
    if (e.button !== 0 || !settings.get("backCloses")) return;
    const hit = [...document.querySelectorAll('[data-name="Back"]')].find((el) => {
      const r = el.getBoundingClientRect();
      return r.width && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    });
    if (!hit || !(hit.matches(":disabled") || hit.querySelector("button:disabled"))) return;
    activeTab().then((tab) => tab && tryClose(tab.id, true));
  }, true);
})();
