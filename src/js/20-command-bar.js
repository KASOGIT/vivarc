// Vivarc command bar. Opens whenever a blank new tab is created (Cmd+T bound to "New Tab",
// the sidebar "+ New Tab" row). The blank tab is navigated to the choice, or closed on Escape.
(() => {
  const BLANK = /^(chrome|vivaldi):\/\/(newtab|vivaldi-webui\/startpage)/;
  const isBlank = (tab) => BLANK.test(tab.pendingUrl || tab.url || "");
  const startedAt = Date.now();

  const DEFAULT = {
    name: "DuckDuckGo",
    url: "https://duckduckgo.com/?q={searchTerms}",
    suggest: "https://duckduckgo.com/ac/?q={searchTerms}&type=list",
  };
  // Built-in search shortcuts (keyword + Tab). Engines from the user's Vivaldi settings win on a clash.
  const SEED = [
    ["az", "Amazon", "https://www.amazon.com/s?k={searchTerms}"],
    ["b", "Bing", "https://www.bing.com/search?q={searchTerms}"],
    ["d", "DuckDuckGo", "https://duckduckgo.com/?q={searchTerms}"],
    ["g", "Google", "https://www.google.com/search?q={searchTerms}"],
    ["gc", "Calendar", "https://calendar.google.com/calendar/u/0/r/search?q={searchTerms}"],
    ["gd", "Drive", "https://drive.google.com/drive/search?q={searchTerms}"],
    ["gh", "GitHub", "https://github.com/search?q={searchTerms}"],
    ["gm", "Gmail", "https://mail.google.com/mail/u/0/#search/{searchTerms}"],
    ["li", "LinkedIn", "https://www.linkedin.com/search/results/all/?keywords={searchTerms}"],
    ["m", "Maps", "https://www.google.com/maps/search/{searchTerms}"],
    ["mdn", "MDN", "https://developer.mozilla.org/en-US/search?q={searchTerms}"],
    ["npm", "npm", "https://www.npmjs.com/search?q={searchTerms}"],
    ["r", "Reddit", "https://www.reddit.com/search/?q={searchTerms}"],
    ["so", "Stack Overflow", "https://stackoverflow.com/search?q={searchTerms}"],
    ["tr", "Translate", "https://translate.google.com/?sl=auto&text={searchTerms}&op=translate"],
    ["w", "Wikipedia", "https://en.wikipedia.org/wiki/Special:Search?search={searchTerms}"],
    ["x", "X", "https://x.com/search?q={searchTerms}"],
    ["yt", "YouTube", "https://www.youtube.com/results?search_query={searchTerms}"],
  ].map(([keyword, name, url]) => ({ keyword, name, url }));
  const CHIP_COLORS = {
    yt: "#ff0000", g: "#4285f4", d: "#de5833", r: "#ff4500", gh: "#24292f", m: "#188038", w: "#636466",
    gm: "#ea4335", gd: "#188038", gc: "#4285f4", li: "#0a66c2", x: "#111111", so: "#f48024", npm: "#cb3837", mdn: "#1b1b1b",
  };

  let engines = SEED;
  (async () => {
    try {
      const reply = await vivaldi.searchEngines.getTemplateUrls();
      const list = (reply.templateUrls || reply)
        .filter((t) => t.keyword && t.url && !t.keyword.startsWith("@"))
        .map((t) => ({ keyword: t.keyword, name: t.name, url: t.url.replace(/\{(?!searchTerms\})[^}]*\}/g, "") }));
      const taken = new Set(list.map((t) => t.keyword.toLowerCase()));
      engines = [...list, ...SEED.filter((e) => !taken.has(e.keyword))];
    } catch (_) {}
  })();

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };
  const SEARCH_SVG =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4-4"/></svg>';
  const ARROW_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';

  const hostOf = (url) => {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (_) { return ""; }
  };
  const looksLikeUrl = (text) =>
    /^(https?:\/\/|chrome:\/\/|vivaldi:\/\/)/i.test(text) || (/^[^\s]+\.[a-z]{2,}(\/\S*)?$/i.test(text) && !text.includes(" "));
  const toUrl = (text) => (/^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : `https://${text}`);
  const engineUrl = (engine, query) => engine.url.replace(/\{searchTerms\}|%s/, encodeURIComponent(query));

  const toast = (message) => window.dispatchEvent(new CustomEvent("vm-toast", { detail: message }));
  const openPage = (url) => chrome.tabs.create({ url });
  const press = (node) => {
    for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      const Ctor = type.startsWith("pointer") ? PointerEvent : MouseEvent;
      node.dispatchEvent(new Ctor(type, { bubbles: true, cancelable: true, view: window, button: 0 }));
    }
  };
  const findDownloadsButton = () => {
    const host = document.querySelector('[data-name="PanelDownloads"]');
    if (host) return host.querySelector("button") || host;
    return [...document.querySelectorAll("#browser button, #browser [role=button]")]
      .find((n) => /download|téléchar/i.test(`${n.title} ${n.getAttribute("aria-label") || ""} ${n.className}`));
  };
  const openDownloads = () => {
    const button = findDownloadsButton();
    if (button) press(button);
    else chrome.downloads?.showDefaultFolder?.();
  };
  const setExtData = async (tab, patch) => {
    const fresh = await chrome.tabs.get(tab.id);
    let ext = {};
    try { ext = JSON.parse(fresh.vivExtData || "{}"); } catch (_) {}
    await chrome.tabs.update(tab.id, { vivExtData: JSON.stringify({ ...ext, ...patch }) });
  };
  // Split view like Arc's: the page behind the bar and a new tab share a Vivaldi tile group. "row" puts them
  // side by side, "column" one above the other (measured from the rendered panes in Vivaldi 8.2). Vivaldi only honours the layout when every tile gets its data at
  // once, so both tabs are written together and once more shortly after. The new tab opens the command bar.
  const splitView = async (tab, layout) => {
    const fresh = await chrome.tabs.get(tab.id);
    const existing = window.__vm.tilingOf(fresh);
    const id = existing?.id ?? crypto.randomUUID();
    const kind = existing?.layout ?? layout;
    const peers = (await chrome.tabs.query({ currentWindow: true })).filter((t) => window.__vm.tilingOf(t)?.id === id);
    const created = await chrome.tabs.create({ active: true, index: fresh.index + 1 });
    const members = [...peers.length ? peers : [fresh], created];
    const write = () => Promise.all(members.map((t, index) =>
      setExtData(t, { tiling: { id, layout: kind, type: "selection", index } })));
    await write();
    setTimeout(() => write().catch(() => {}), 400);
    setTimeout(async () => {
      const rects = [...document.querySelectorAll("webview")].map((w) => w.getBoundingClientRect())
        .filter((r) => r.width > 80 && r.height > 80).map((r) => [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]);
      const log = await window.__vm.store.get("split-debug", []);
      log.push({ layout: kind, rects });
      window.__vm.store.set("split-debug", log.slice(-8));
    }, 1500);
  };
  const closeSplitView = async (tab) => {
    const id = window.__vm.tilingOf(tab)?.id;
    const peers = (await chrome.tabs.query({ currentWindow: true })).filter((t) => window.__vm.tilingOf(t)?.id === id);
    await Promise.all(peers.map((t) => setExtData(t, { tiling: undefined })));
  };

  // Quick actions, matched against what is typed. `tab` actions apply to the page behind the bar.
  const ACTIONS = [
    { label: "View History", words: "history visited", run: () => openPage("vivaldi://history") },
    { label: "View Downloads", words: "downloads files", run: openDownloads },
    { label: "View Bookmarks", words: "bookmarks saved", run: () => openPage("vivaldi://bookmarks") },
    { label: "Open Settings", words: "settings preferences options", run: () => openPage("vivaldi://settings") },
    { label: "Manage Extensions", words: "extensions addons", run: () => openPage("vivaldi://extensions") },
    { label: "Pin This Tab", words: "pin bookmark", tab: true, run: async (tab) => {
      if (await window.__vm.pinTab?.(tab, "Pinned")) toast("Pinned Tab");
    } },
    { label: "Add This Tab to Favorites", words: "favorite pin", tab: true, run: async (tab) => {
      if (await window.__vm.pinTab?.(tab, "Favorites")) toast("Added to Favorites");
    } },
    { label: "Copy Current URL", words: "copy link address share", tab: true, run: async (tab) => {
      await navigator.clipboard?.writeText(tab.url).catch(() => {});
      toast("Copied Current URL");
    } },
    { label: "Split View: Side by Side", words: "split tile vertical columns", tab: true, run: (tab) => splitView(tab, "row") },
    { label: "Split View: Top and Bottom", words: "split tile horizontal rows", tab: true, run: (tab) => splitView(tab, "column") },
    { label: "Close Split View", words: "unsplit untile split", tab: true, when: (tab) => !!window.__vm.tilingOf(tab), run: closeSplitView },
    { label: "Duplicate Tab", words: "clone copy", tab: true, run: (tab) => chrome.tabs.duplicate(tab.id) },
    { label: "Mute / Unmute Tab", words: "sound audio silence", tab: true, run: (tab) =>
      chrome.tabs.update(tab.id, { muted: !tab.mutedInfo?.muted }) },
    { label: "Close Tab", words: "quit remove", tab: true, run: (tab) => chrome.tabs.remove(tab.id) },
    { label: "Reopen Closed Tab", words: "restore undo", run: () => chrome.sessions.restore() },
    { label: "New Window", words: "open window", run: () => chrome.windows.create({}) },
    { label: "New Private Window", words: "incognito private", run: () => chrome.windows.create({ incognito: true }) },
    { label: "Vivarc Guide", words: "welcome help shortcuts tour start", run: () => {
      const url = window.__vm.config.startUrl;
      if (url) openPage(url);
    } },
    { label: "Edit Theme", words: "color appearance sidebar", run: () => window.dispatchEvent(new CustomEvent("vm-open-theme")) },
  ];
  const ACTION_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/></svg>';

  let bar = null;
  let input = null;
  let list = null;
  let chipHolder = null;
  let targetTab = null;
  let mode = null;
  let rows = [];
  let selected = 0;
  let seq = 0;
  let autoCompleted = false;

  const iconFor = (url, favicon) => {
    const wrap = el("span", "vm-cmd-ico");
    if (favicon) {
      const img = el("img");
      img.src = favicon;
      img.addEventListener("error", () => wrap.replaceChildren(letter(url)));
      wrap.append(img);
    } else {
      wrap.append(letter(url));
    }
    return wrap;
  };
  const letter = (url) => {
    const host = hostOf(url) || "?";
    let hash = 0;
    for (const ch of host) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
    const span = el("span", "vm-cmd-letter", host[0].toUpperCase());
    span.style.backgroundColor = `hsl(${hash} 38% 40%)`;
    return span;
  };

  const close = (removeBlank) => {
    const blank = targetTab;
    bar?.remove();
    bar = input = list = chipHolder = targetTab = mode = null;
    rows = [];
    seq++;
    if (removeBlank && blank != null) chrome.tabs.remove(blank).catch(() => {});
  };

  const go = (url) => {
    const id = targetTab;
    close(false);
    if (id != null) chrome.tabs.update(id, { url, active: true });
    else chrome.tabs.create({ url });
  };

  // Plain searches use the engine chosen in Vivaldi; DuckDuckGo is only the fallback.
  const defaultSearch = async (query) => {
    const id = targetTab;
    close(false);
    try {
      await chrome.search.query(id != null ? { text: query, tabId: id } : { text: query, disposition: "NEW_TAB" });
    } catch (_) {
      const url = engineUrl(DEFAULT, query);
      if (id != null) chrome.tabs.update(id, { url, active: true });
      else chrome.tabs.create({ url });
    }
  };

  const run = (row) => {
    if (!row || (row.type === "search" && !row.query)) return;
    if (row.type === "tab") {
      chrome.tabs.update(row.tab.id, { active: true });
      close(true);
    } else if (row.type === "search") {
      if (row.engine === DEFAULT) defaultSearch(row.query);
      else go(engineUrl(row.engine, row.query));
    } else if (row.type === "engine") {
      input.value = "";
      setMode(row.engine);
    } else if (row.type === "action") {
      close(true);
      Promise.resolve(row.action.run(row.tab)).catch((e) => console.warn("[vivarc] action:", e));
    } else {
      go(row.url);
    }
  };

  const render = () => {
    if (!list) return;
    list.replaceChildren(...rows.map((row, i) => {
      const item = el("div", `vm-cmd-row${i === selected ? " sel" : ""}`);
      if (row.type === "action" || row.type === "engine") {
        const glyph = el("span", "vm-cmd-ico vm-cmd-glyph");
        glyph.innerHTML = ACTION_SVG;
        item.append(glyph, el("span", "vm-cmd-title", row.label));
      } else if (row.type === "search" || row.type === "suggest") {
        const glyph = el("span", "vm-cmd-ico vm-cmd-glyph");
        glyph.innerHTML = SEARCH_SVG;
        item.append(glyph, el("span", "vm-cmd-title", row.label));
      } else {
        item.append(iconFor(row.url, row.favicon), el("span", "vm-cmd-title", row.label));
        if (row.sub) item.append(el("span", "vm-cmd-sub", `— ${row.sub}`));
      }
      if (row.type === "tab" || row.type === "action" || row.type === "engine") {
        const hint = el("span", "vm-cmd-hint");
        hint.append(el("span", null, { tab: "Switch to Tab", action: "Run Action", engine: "Tab" }[row.type]));
        const arrow = el("span", "vm-cmd-arrow");
        arrow.innerHTML = ARROW_SVG;
        hint.append(arrow);
        item.append(hint);
      }
      item.addEventListener("mousemove", () => {
        if (selected === i) return;
        selected = i;
        list.querySelector(".sel")?.classList.remove("sel");
        item.classList.add("sel");
      });
      item.addEventListener("click", () => run(row));
      return item;
    }));
    list.children[selected]?.scrollIntoView({ block: "nearest" });
  };

  const allTabs = async () =>
    (await chrome.tabs.query({ currentWindow: true })).filter((t) => !isBlank(t) && t.id !== targetTab);

  const pageBehindBar = async () => {
    const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (active && !isBlank(active) && active.id !== targetTab) return active;
    const last = activeHistory.filter((id) => id !== targetTab).pop();
    return last != null ? chrome.tabs.get(last).catch(() => null) : null;
  };

  const matchingActions = async (needle) => {
    const hits = ACTIONS.filter((a) => `${a.label} ${a.words}`.toLowerCase().split(/\s+/)
      .some((w) => w.startsWith(needle)) || a.label.toLowerCase().includes(needle));
    if (!hits.length) return [];
    const tab = hits.some((a) => a.tab) ? await pageBehindBar() : null;
    return hits.filter((a) => (!a.tab || tab) && (!a.when || a.when(tab))).slice(0, 3)
      .map((action) => ({ type: "action", action, tab, label: action.label }));
  };

  const compute = async () => {
    const id = ++seq;
    const text = input.value.trim();
    const out = [];
    if (mode) {
      out.push({ type: "search", engine: mode, query: text, label: text || "%s" });
    } else if (!text) {
      (await allTabs()).slice(0, 7).forEach((tab) =>
        out.push({ type: "tab", tab, url: tab.url, favicon: tab.favIconUrl, label: tab.title || tab.url }));
    } else {
      const needle = text.toLowerCase();
      const seen = new Set();
      const matches = [];
      const add = (row) => {
        const key = row.url.replace(/#.*$/, "");
        if (seen.has(key)) return;
        seen.add(key);
        matches.push(row);
      };
      (await allTabs())
        .filter((t) => `${t.title} ${t.url}`.toLowerCase().includes(needle))
        .slice(0, 4)
        .forEach((tab) => add({ type: "tab", tab, url: tab.url, favicon: tab.favIconUrl, label: tab.title || tab.url }));
      try {
        (await chrome.bookmarks.search(text)).filter((b) => b.url).slice(0, 3)
          .forEach((b) => add({ type: "bookmark", url: b.url, label: b.title || b.url, sub: hostOf(b.url) }));
      } catch (_) {}
      try {
        (await chrome.history.search({ text, maxResults: 4 }))
          .forEach((h) => add({ type: "history", url: h.url, favicon: null, label: h.title || h.url, sub: hostOf(h.url) }));
      } catch (_) {}
      if (id !== seq) return;
      const prefix = matches.find((m) => hostOf(m.url).startsWith(needle));
      const searchRow = { type: "search", engine: DEFAULT, query: text, label: text };
      if (looksLikeUrl(text)) out.push({ type: "url", url: toUrl(text), label: text, sub: "Open" });
      if (prefix) out.push(prefix);
      out.push(searchRow);
      if (needle.length > 1) out.push(...await matchingActions(needle));
      const keyword = !/\s/.test(text) && engines.find((en) => en.keyword.toLowerCase() === needle);
      if (keyword) out.unshift({ type: "engine", engine: keyword, label: `Search ${keyword.name}` });
      out.push(...matches.filter((m) => m !== prefix));
      if (window.__vm.config.suggestions === "ddg" && !looksLikeUrl(text) && text.length > 1) {
        try {
          const reply = await fetch(DEFAULT.suggest.replace("{searchTerms}", encodeURIComponent(text)));
          const data = await reply.json();
          const phrases = Array.isArray(data[1]) ? data[1] : data.map((d) => d.phrase);
          if (id !== seq) return;
          phrases.filter((p) => p && p.toLowerCase() !== needle).slice(0, 4)
            .forEach((p) => out.push({ type: "suggest", engine: DEFAULT, query: p, label: p }));
        } catch (_) {}
      }
    }
    if (id !== seq) return;
    rows = out.map((r) => (r.type === "suggest" ? { ...r, type: "search" } : r));
    selected = 0;
    render();
  };

  const setMode = (engine) => {
    mode = engine;
    chipHolder.replaceChildren();
    if (engine) {
      const chip = el("span", "vm-cmd-chip", engine.name);
      chip.style.backgroundColor = CHIP_COLORS[engine.keyword] || "#5b5670";
      chipHolder.append(chip);
    }
    input.placeholder = engine ? "Search…" : "Search or Enter URL…";
    input.value = "";
    compute();
  };

  const autocomplete = async () => {
    const text = input.value;
    if (mode || !text || /\s/.test(text) || !autoCompleted) return;
    const needle = text.toLowerCase();
    const hosts = [
      ...(await chrome.tabs.query({ currentWindow: true })).map((t) => hostOf(t.url)),
      ...((await chrome.bookmarks.search(text).catch(() => [])).map((b) => hostOf(b.url))),
    ];
    const host = hosts.find((h) => h && h.startsWith(needle) && h.length > needle.length);
    if (host && input.value === text) {
      input.value = host;
      input.setSelectionRange(text.length, host.length);
    }
  };

  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(true); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!rows.length) return;
      selected = (selected + (e.key === "ArrowDown" ? 1 : rows.length - 1)) % rows.length;
      render();
      return;
    }
    if (e.key === "Enter") { e.preventDefault(); run(rows[selected]); return; }
    if (e.key === "Tab") {
      e.preventDefault();
      const keyword = input.value.trim().toLowerCase();
      const engine = !mode && keyword && engines.find((en) => en.keyword.toLowerCase() === keyword);
      if (engine) setMode(engine);
      return;
    }
    if (e.key === "Backspace" && mode && !input.value) { e.preventDefault(); setMode(null); return; }
    autoCompleted = e.key.length === 1 && !e.metaKey && !e.ctrlKey;
  };

  const open = (tabId) => {
    if (!window.__vm.cssLoaded) return;
    if (bar) { targetTab = tabId; return; }
    targetTab = tabId;
    mode = null;
    bar = el("div");
    bar.id = "vm-cmd";
    const box = el("div", "vm-cmd-box");
    const head = el("div", "vm-cmd-head");
    const glyph = el("span", "vm-cmd-glyph");
    glyph.innerHTML = SEARCH_SVG;
    chipHolder = el("span", "vm-cmd-chips");
    input = el("input");
    input.placeholder = "Search or Enter URL…";
    input.spellcheck = false;
    input.autocomplete = "off";
    head.append(glyph, chipHolder, input);
    list = el("div", "vm-cmd-list");
    box.append(head, list);
    bar.append(box);
    bar.addEventListener("mousedown", (e) => { if (e.target === bar) close(true); });
    input.addEventListener("keydown", onKey);
    input.addEventListener("input", async () => { await compute(); autocomplete(); });
    (document.querySelector("#browser") || document.body).append(bar);
    const focus = () => input?.focus();
    focus();
    setTimeout(focus, 60);
    setTimeout(focus, 250);
    compute();
    window.dispatchEvent(new CustomEvent("vm-command-bar-opened"));
  };

  window.addEventListener("vm-open-command-bar", () => open(null));
  window.__vm.onShortcut((key) => { if (key === window.__vm.normalise("meta+t")) open(null); });

  const activeHistory = [];
  chrome.tabs.onActivated.addListener(({ tabId }) => {
    activeHistory.push(tabId);
    if (activeHistory.length > 6) activeHistory.shift();
  });

  chrome.tabs.onCreated.addListener((tab) => {
    if (Date.now() - startedAt < 5000 || !isBlank(tab) || tab.active === false) return;
    const previous = activeHistory.filter((id) => id !== tab.id).pop();
    open(tab.id);
    if (previous != null) {
      setTimeout(() => {
        if (bar && targetTab === tab.id) {
          chrome.tabs.update(previous, { active: true }).then(() => input?.focus(), () => {});
        }
      }, 120);
    }
  });
  console.log("[vivarc] command bar started");
})();
