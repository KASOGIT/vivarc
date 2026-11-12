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
  // Only the open previews count: Peek's own list of preloaded tabs keeps an id after "Open in New Tab" turns that
  // tab into a real one, which would then stay hidden.
  const isPeekTab = (tab, ids) => ids.has(tab.id) || !!readExt(tab).arcPeekRuntime;
  const previewTabIds = (webviews) => new Set([...webviews].flatMap((d) => [d?.parallelTabId, d?.relatedTabId]).filter(Boolean));

  // Injected in every page. Peek's "pin" rule reads window.__arcpeekCurrentTabIsPinned, which Peek fills from
  // Vivaldi's tab strip; Vivarc pins live in vivExtData, so the flag becomes a read-only getter Vivarc sets. Peek
  // listens on document in the capture phase and never looks at Cmd/Ctrl: a listener on window runs first and
  // makes a Cmd/Ctrl+click not count as a pinned click, so it keeps opening a new tab.
  const pinnedScript = (pinned) => `(() => {
    window.__vmPeekPinned = ${pinned ? "true" : "false"};
    if (window.__vmPeekWatch) return;
    window.__vmPeekWatch = true;
    let command = false;
    window.addEventListener("pointerdown", (e) => { command = !!(e.metaKey || e.ctrlKey); }, true);
    Object.defineProperty(window, "__arcpeekCurrentTabIsPinned",
      { get: () => window.__vmPeekPinned && !command, set: () => {}, configurable: true });
  })();`;

  const api = { triggers, isPeekTab, previewTabIds, pinnedScript, tabIds: () => new Set(), creatingTab: () => false };
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
    api.tabIds = () => previewTabIds(peek.webviews?.values?.() || []);
    // Peek raises this flag around the creation of its preloaded tab, whose id it only learns afterwards.
    let creating = false;
    window.addEventListener("vmod-suppress-tab-toast", (e) => { creating = !!e.detail?.suppress; });
    api.creatingTab = () => creating;

    const push = () => window.dispatchEvent(new CustomEvent("vivaldi-mod-config-updated",
      { detail: { mods: { arcPeek: triggers(settings.all()) } } }));
    push();

    // A page keeps the triggers it was loaded with, so with Peek just turned off a click on an already open page
    // still asks for a preview: open the link in that tab instead, which is what turning Peek off means.
    const openPeek = peek.openPeek.bind(peek);
    // Peek's message handler passes no source tab: the link opens in the active tab, or a new one from a web panel.
    peek.openPeek = (url, fromPanel, rect, meta) => {
      if (settings.get("peek")) {
        firstPreviewHint();
        return openPeek(url, fromPanel, rect, meta);
      }
      if (fromPanel) return chrome.tabs.create({ url });
      chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => tab && chrome.tabs.update(tab.id, { url }));
    };

    let wasOn = settings.get("peek");
    settings.onChange((values) => {
      push();
      if (wasOn && !values.peek) for (const id of [...(peek.webviews?.keys?.() || [])]) peek.disposePeek(id);
      wasOn = values.peek;
    });

    const mark = (tab) => {
      const webview = document.querySelector(`webview[tab_id="${tab.id}"]`);
      webview?.executeScript?.({ code: pinnedScript(!!readExt(tab).vivarcPin), runAt: "document_start" }, () => void chrome.runtime.lastError);
    };
    const markTab = ({ tabId, frameId }) => {
      if (frameId !== 0) return;
      chrome.tabs.get(tabId, (tab) => { if (!chrome.runtime.lastError && tab) mark(tab); });
    };
    // onCommitted reaches the new document; onCompleted covers a page whose first injection came too early.
    chrome.webNavigation.onCommitted.addListener(markTab);
    chrome.webNavigation.onCompleted.addListener(markTab);
    chrome.tabs.onUpdated.addListener((_id, change, tab) => { if (change.vivExtData !== undefined) mark(tab); }); // pinned or unpinned
    setTimeout(() => chrome.tabs.query({ currentWindow: true }, (tabs) => tabs.forEach(mark)), 1000);
  };

  // One read per window: two previews opened at once must not both show the hint.
  let hintChecked = false;
  const firstPreviewHint = () => {
    if (hintChecked) return;
    hintChecked = true;
    store.get("peekHintShown", false).then((shown) => {
      if (shown) return;
      store.set("peekHintShown", true);
      window.dispatchEvent(new CustomEvent("vm-toast", { detail: "Link preview: Esc closes it. Turn it off in Vivarc Settings." }));
    });
  };
})();
