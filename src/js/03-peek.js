// Vivarc and Peek (the optional link preview, community code we never patch). Peek reads its triggers from the
// "vivaldi-mod-config-updated" event and exposes its instance as window.ArcPeekDebug: Vivarc drives it through both.
(() => {
  const readExt = (tab) => {
    try { return JSON.parse(tab?.vivExtData || "{}") || {}; } catch (_) { return {}; }
  };

  // Upstream also opens Peek on a plain click anywhere on google.com; Arc only does it from pinned tabs.
  // Cmd/Ctrl+click is never listed: it must keep opening a new tab.
  const triggers = (values) => {
    const on = !!values.peek;
    return {
      clickOpenModifiers: on && values.peekShortcut !== "none" ? [values.peekShortcut] : [],
      longPressButtons: on ? ["middle"] : [],
      autoOpenList: on && values.peekPinned ? ["pin"] : [],
      scaleBackgroundPage: !!values.peekDim,
    };
  };

  // The tabs Peek opens behind a preview: a background copy it preloads (often stashed in another workspace, which
  // Vivarc shows as a space) and the tab that backs the floating window. Neither belongs in the sidebar.
  const isPeekTab = (tab, ids) => ids.has(tab.id) || !!readExt(tab).arcPeekRuntime;

  const api = { triggers, isPeekTab, tabIds: () => new Set() };
  api.withoutPeekTabs = (tabs) => { const ids = api.tabIds(); return tabs.filter((t) => !isPeekTab(t, ids)); };
  window.__vm.peek = api;
  const { config, settings, store } = window.__vm;
  if (!store || !config?.peekInstalled) return;

  // Peek sets window.ArcPeekDebug in its constructor, after its config listener exists and before it injects into
  // the open pages, which then keep the triggers they got. Catching that assignment is the only moment the
  // config reaches the first pages (with a timer, restored tabs kept upstream's google.com auto-open).
  let instance = null;
  Object.defineProperty(window, "ArcPeekDebug", {
    configurable: true,
    get: () => instance,
    set: (peek) => { const first = !instance; instance = peek; if (first && peek) attach(peek); },
  });

  const attach = (peek) => {
    api.tabIds = () => {
      const ids = new Set();
      for (const data of peek.webviews?.values?.() || []) {
        if (data?.parallelTabId) ids.add(data.parallelTabId);
        if (data?.relatedTabId) ids.add(data.relatedTabId);
      }
      try { (JSON.parse(localStorage.getItem("arcpeek_parallel_tabs") || "[]") || []).forEach((id) => ids.add(id)); } catch (_) {}
      return ids;
    };

    const push = () => window.dispatchEvent(new CustomEvent("vivaldi-mod-config-updated",
      { detail: { mods: { arcPeek: triggers(settings.all()) } } }));
    push();

    // A page keeps the triggers it was loaded with, so with Peek just turned off a click on an already open page
    // still asks for a preview: open the link in that tab instead, which is what turning Peek off means.
    const openPeek = peek.openPeek.bind(peek);
    // Peek's message handler passes no source tab, so the link opens in the active tab.
    peek.openPeek = (url, fromPanel, rect, meta) => {
      if (settings.get("peek")) {
        firstPreviewHint();
        return openPeek(url, fromPanel, rect, meta);
      }
      chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => tab && chrome.tabs.update(tab.id, { url }));
    };

    let wasOn = settings.get("peek");
    settings.onChange((values) => {
      push();
      if (wasOn && !values.peek) for (const id of [...(peek.webviews?.keys?.() || [])]) peek.disposePeek(id);
      wasOn = values.peek;
    });

    // Peek's "pin" rule asks Vivaldi's tab strip whether a tab is pinned; Vivarc pins live in vivExtData instead.
    // Peek resets the page flag on every navigation, so it is made read-only (true) in pinned pages.
    const PINNED = 'Object.defineProperty(window, "__arcpeekCurrentTabIsPinned", { get: () => true, set: () => {}, configurable: true });';
    const markPinned = ({ tabId, frameId }) => {
      if (frameId !== 0) return;
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError || !readExt(tab).vivarcPin) return;
        const webview = document.querySelector(`webview[tab_id="${tabId}"]`);
        webview?.executeScript?.({ code: PINNED, runAt: "document_start" }, () => void chrome.runtime.lastError);
      });
    };
    for (const ev of ["onCommitted", "onDOMContentLoaded", "onCompleted"]) chrome.webNavigation[ev].addListener(markPinned);
    setTimeout(() => chrome.tabs.query({ currentWindow: true }, (tabs) => tabs.forEach((t) => markPinned({ tabId: t.id, frameId: 0 }))), 1000);
  };

  const firstPreviewHint = () => store.get("peekHintShown", false).then((shown) => {
    if (shown) return;
    store.set("peekHintShown", true);
    window.dispatchEvent(new CustomEvent("vm-toast", { detail: "Link preview: Esc closes it. Turn it off in Vivarc Settings." }));
  });
})();
