// Vivarc sidebar: favorites grid on top, then one scrollable panel (pinned folders, divider,
// open tabs). The data lives in a bookmarks folder that has a "Favorites" and a "Pinned" subfolder
// (created on first run, or produced by `vivarc import-arc`). Vivaldi's own tab strip is hidden.
(() => {
  const ARC_PREFIX = "Arc - ";
  const cfg = window.__vm.config;
  const BLANK = /^(chrome|vivaldi):\/\/(newtab|vivaldi-webui\/startpage)/;
  const BOTTOM_TOOLBAR = cfg.compactBottomBar ? 35 : 64;

  const store = window.__vm.store;
  const openFolders = new Set();
  const seedIcons = window.__vmIcons || {};
  let icons = {};
  const saveOpen = () => store.set("open", [...openFolders]);
  const state = { space: null, favs: null, pinned: null, trash: null, tabs: [], renameId: null };
  let panel = null;

  const ICON_CLOSED =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l2 2.5h7A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></svg>';
  const ICON_OPEN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3 17.5V7.5A2.5 2.5 0 0 1 5.5 5h4l2 2.5h7A2.5 2.5 0 0 1 21 10v1.5"/><path d="M3.3 18.6 5.2 12a2 2 0 0 1 1.9-1.5H21a1 1 0 0 1 1 1.3l-1.8 6.4A2 2 0 0 1 18.3 20H5.5a2.2 2.2 0 0 1-2.2-1.4z"/></svg>';

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  const sameSite = (tabUrl, url) => {
    try {
      const a = new URL(tabUrl), b = new URL(url);
      if (a.origin !== b.origin) return false;
      return b.pathname.length > 1 ? a.pathname.startsWith(b.pathname) : a.pathname === "/";
    } catch (_) { return false; }
  };

  const originOf = (url) => {
    try { return new URL(url).origin; } catch (_) { return ""; }
  };

  const letterIcon = (url) => {
    let host = "?";
    try { host = new URL(url).hostname.replace(/^www\./, "") || "?"; } catch (_) {}
    let hash = 0;
    for (const ch of host) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
    const span = el("span", "vm-letter", host[0].toUpperCase());
    span.style.backgroundColor = `hsl(${hash} 38% 40%)`;
    return span;
  };

  const iconEl = (url, live) => {
    const wrap = el("span", "vm-ico");
    const origin = originOf(url);
    const sources = [live, icons[origin], seedIcons[origin]].filter(Boolean);
    const next = () => {
      const src = sources.shift();
      if (!src) return wrap.replaceChildren(letterIcon(url));
      const img = el("img");
      img.addEventListener("error", next);
      img.src = src;
      wrap.replaceChildren(img);
    };
    next();
    return wrap;
  };

  const leaves = (node) =>
    node.children ? node.children.flatMap(leaves) : [node];

  const hasPinnedChild = (n) => n.children?.some((c) => c.children && c.title === "Pinned");
  const findSpace = (nodes) => {
    for (const n of nodes) {
      if (hasPinnedChild(n)) return n;
      const found = n.children && findSpace(n.children);
      if (found) return found;
    }
    return null;
  };
  const spaceLabel = (space) => space.title.startsWith(ARC_PREFIX) ? space.title.slice(ARC_PREFIX.length) : space.title;

  const tabFor = (url) => state.tabs.find((t) => sameSite(t.url, url));

  const focusOrOpen = (url) => {
    const hit = tabFor(url);
    if (hit) chrome.tabs.update(hit.id, { active: true });
    else chrome.tabs.create({ url });
  };

  const ensureFolder = async (name) => {
    const existing = state.space.children.find((c) => c.children && c.title === name);
    if (existing) return existing;
    return chrome.bookmarks.create({ parentId: state.space.id, title: name, index: 0 });
  };

  window.__vm.pinTab = async (tab, kind) => {
    if (!state.space) return false;
    const parent = kind === "Favorites" ? await ensureFolder("Favorites") : (state.pinned || await ensureFolder("Pinned"));
    await chrome.bookmarks.create({ parentId: parent.id, title: tab.title, url: tab.url });
    return true;
  };

  const copy = (text) => navigator.clipboard?.writeText(text).catch(() => {});

  // Removing goes to Vivaldi's bookmark trash, so it can be undone from there.
  const discard = (node) => {
    if (state.trash) chrome.bookmarks.move(node.id, { parentId: state.trash.id });
    else if (node.children) chrome.bookmarks.removeTree(node.id);
    else chrome.bookmarks.remove(node.id);
  };

  const cloneTree = async (node, parentId, suffix = "") => {
    const made = await chrome.bookmarks.create({
      parentId, title: `${node.title}${suffix}`, ...(node.children ? {} : { url: node.url }),
    });
    for (const child of node.children ?? []) await cloneTree(child, made.id);
  };

  const newFolder = async (parent) => {
    const target = parent ?? state.pinned ?? await ensureFolder("Pinned");
    openFolders.add(target.id);
    saveOpen();
    const made = await chrome.bookmarks.create({ parentId: target.id, title: "New Folder" });
    state.renameId = made.id;
  };

  // ---- context menu ----
  let menu = null;
  const closeMenu = () => { menu?.remove(); menu = null; };
  const showMenu = (event, items) => {
    event.preventDefault();
    event.stopPropagation();
    closeMenu();
    menu = el("div", "vm-menu");
    for (const [label, action, danger] of items) {
      if (!label) { menu.append(el("div", "vm-menu-sep")); continue; }
      const item = el("div", `vm-menu-item${danger ? " danger" : ""}`, label);
      item.addEventListener("click", () => { closeMenu(); action(); });
      menu.append(item);
    }
    (document.querySelector("#browser") || document.body).append(menu);
    const { width, height } = menu.getBoundingClientRect();
    menu.style.left = `${Math.min(event.clientX, window.innerWidth - width - 8)}px`;
    menu.style.top = `${Math.min(event.clientY, window.innerHeight - height - 8)}px`;
  };
  const outside = (e) => { if (menu && !menu.contains(e.target)) closeMenu(); };
  document.addEventListener("mousedown", outside, true);
  document.addEventListener("focusin", outside, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });
  window.addEventListener("blur", closeMenu);
  window.__vm?.onShortcut((key) => { if (key === "esc") closeMenu(); });

  // ---- drag and drop ----
  let drag = null;
  let refreshAfterDrag = false;
  const clearDrop = () => {
    for (const n of panel?.querySelectorAll(".drop-before, .drop-after, .drop-into") ?? []) {
      n.classList.remove("drop-before", "drop-after", "drop-into");
    }
  };

  const wireDrag = (node, payload) => {
    node.draggable = true;
    node.addEventListener("dragstart", (e) => {
      drag = payload;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", payload.url || "");
      closeMenu();
      // Changing the layout inside dragstart makes Chrome cancel the drag, so it waits a frame.
      requestAnimationFrame(() => {
        if (!drag) return;
        node.classList.add("dragging");
        document.querySelector("#browser")?.classList.add("vm-dragging");
      });
    });
    node.addEventListener("dragend", () => {
      drag = null;
      if (refreshAfterDrag) refresh(true);
      node.classList.remove("dragging");
      document.querySelector("#browser")?.classList.remove("vm-dragging");
      clearDrop();
    });
  };

  // zone: "before" | "after" | "into" depending on pointer position inside the target
  const wireDrop = (node, { horizontal = false, allowInto = false, accept, onDrop }) => {
    const zoneOf = (e) => {
      const r = node.getBoundingClientRect();
      const t = horizontal ? (e.clientX - r.left) / r.width : (e.clientY - r.top) / r.height;
      if (allowInto) return t < 0.28 ? "before" : t > 0.72 ? "after" : "into";
      return t < 0.5 ? "before" : "after";
    };
    node.addEventListener("dragover", (e) => {
      if (!drag || (accept && !accept(drag))) return;
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "move";
      clearDrop();
      node.classList.add(`drop-${zoneOf(e)}`);
    });
    node.addEventListener("drop", async (e) => {
      if (!drag || (accept && !accept(drag))) return;
      e.preventDefault();
      e.stopPropagation();
      const zone = zoneOf(e), payload = drag;
      drag = null;
      clearDrop();
      try { await onDrop(zone, payload); } catch (err) { console.warn("[vivarc] drop:", err); }
    });
  };

  const isBookmark = (d) => d.type === "bm";
  const insertPinned = async (data, parentId, index) => {
    if (data.type === "bm") {
      await chrome.bookmarks.move(data.node.id, { parentId, ...(index == null ? {} : { index }) });
    } else {
      const existing = [...(state.pinned ? leaves(state.pinned) : []), ...(state.favs ? leaves(state.favs) : [])]
        .find((n) => sameSite(data.tab.url, n.url) && n.url === data.tab.url);
      if (existing) await chrome.bookmarks.move(existing.id, { parentId, ...(index == null ? {} : { index }) });
      else await chrome.bookmarks.create({ parentId, title: data.tab.title, url: data.tab.url, ...(index == null ? {} : { index }) });
    }
  };
  const unpin = async (data) => {
    if (data.type !== "bm" || data.node.children) return;
    const { url } = data.node;
    discard(data.node);
    if (!tabFor(url)) await chrome.tabs.create({ url, active: false });
  };

  // ---- rows ----
  const actionButton = (symbol, title, onClick) => {
    const b = el("span", "vm-act", symbol);
    b.title = title;
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return b;
  };

  const startRename = (titleEl, node) => {
    const field = el("input", "vm-rename");
    field.value = node.title;
    titleEl.replaceWith(field);
    field.focus();
    field.select();
    let done = false;
    const finish = (commit) => {
      if (done) return;
      done = true;
      const title = field.value.trim();
      if (commit && title && title !== node.title) chrome.bookmarks.update(node.id, { title });
      else refresh(true);
    };
    field.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") finish(true);
      if (e.key === "Escape") finish(false);
    });
    field.addEventListener("blur", () => finish(true));
    field.addEventListener("click", (e) => e.stopPropagation());
  };

  const bookmarkMenu = (node, isFav) => (e) => {
    const tab = tabFor(node.url);
    showMenu(e, [
      ["Open in New Tab", () => chrome.tabs.create({ url: node.url })],
      ["Copy Link", () => copy(node.url)],
      [isFav ? "Move to Pinned" : "Move to Favorites", async () => {
        const target = isFav ? state.pinned : await ensureFolder("Favorites");
        if (target) chrome.bookmarks.move(node.id, { parentId: target.id });
      }],
      ...(tab ? [["Close Tab", () => chrome.tabs.remove(tab.id)]] : []),
      [],
      [isFav ? "Remove from Favorites" : "Remove from Pinned", () => discard(node), true],
    ]);
  };

  const pinnedLink = (node, depth) => {
    const row = el("div", "vm-row vm-link");
    row.style.paddingLeft = `${8 + depth * 20}px`;
    row.title = node.url;
    const tab = tabFor(node.url);
    if (tab?.active) row.classList.add("active");
    row.append(iconEl(node.url, tab?.favIconUrl), el("span", "vm-title", node.title || node.url));
    row.append(tab
      ? actionButton("–", "Close tab", () => chrome.tabs.remove(tab.id))
      : actionButton("×", "Remove from Pinned", () => discard(node)));
    row.addEventListener("click", () => focusOrOpen(node.url));
    row.addEventListener("contextmenu", bookmarkMenu(node, false));
    wireDrag(row, { type: "bm", node, url: node.url });
    wireDrop(row, {
      onDrop: async (zone, data) => {
        if (data.type === "bm" && data.node.id === node.id) return;
        await insertPinned(data, node.parentId, node.index + (zone === "after" ? 1 : 0));
      },
    });
    return row;
  };

  const folderMenu = (node) => (e) => showMenu(e, [
    ["New Nested Folder…", () => newFolder(node)],
    ["Rename…", () => { state.renameId = node.id; refresh(true); }],
    [],
    ["Copy All Links", () => copy(leaves(node).map((l) => l.url).join("\n"))],
    ["Open All in New Tabs", () => leaves(node).forEach((l) => chrome.tabs.create({ url: l.url, active: false }))],
    ["Duplicate", () => cloneTree(node, node.parentId, " copy")],
    [],
    ["Delete", () => discard(node), true],
  ]);

  const pinnedNode = (node, depth) => {
    if (!node.children) return pinnedLink(node, depth);
    const wrap = el("div", "vm-folder");
    const head = el("div", "vm-row vm-folder-head");
    head.style.paddingLeft = `${8 + depth * 20}px`;
    const glyph = el("span", "vm-glyph");
    const title = el("span", "vm-title", node.title || "Untitled");
    head.append(glyph, title);
    const body = el("div", "vm-folder-body");
    node.children.forEach((c) => body.append(pinnedNode(c, depth + 1)));
    const sync = () => {
      const open = openFolders.has(node.id);
      wrap.classList.toggle("open", open);
      glyph.innerHTML = open ? ICON_OPEN : ICON_CLOSED;
    };
    head.addEventListener("click", () => {
      openFolders.has(node.id) ? openFolders.delete(node.id) : openFolders.add(node.id);
      saveOpen();
      sync();
    });
    head.addEventListener("contextmenu", folderMenu(node));
    wireDrag(head, { type: "bm", node, url: "" });
    wireDrop(head, {
      allowInto: true,
      accept: (d) => !(d.type === "bm" && d.node.id === node.id),
      onDrop: async (zone, data) => {
        if (zone === "into") {
          openFolders.add(node.id);
          saveOpen();
          await insertPinned(data, node.id, null);
        } else {
          await insertPinned(data, node.parentId, node.index + (zone === "after" ? 1 : 0));
        }
      },
    });
    sync();
    wrap.append(head, body);
    if (state.renameId === node.id) {
      state.renameId = null;
      setTimeout(() => startRename(title, node), 0);
    }
    return wrap;
  };

  const favTile = (node) => {
    const tile = el("div", "vm-fav");
    tile.title = node.title || node.url;
    const tab = tabFor(node.url);
    if (tab?.active) tile.classList.add("active");
    tile.append(iconEl(node.url, tab?.favIconUrl));
    tile.addEventListener("click", () => focusOrOpen(node.url));
    tile.addEventListener("contextmenu", bookmarkMenu(node, true));
    wireDrag(tile, { type: "bm", node, url: node.url });
    wireDrop(tile, {
      horizontal: true,
      accept: (d) => !(d.type === "bm" && d.node.children),
      onDrop: async (zone, data) => {
        if (data.type === "bm" && data.node.id === node.id) return;
        await insertPinned(data, node.parentId, node.index + (zone === "after" ? 1 : 0));
      },
    });
    return tile;
  };

  const tabRow = (tab) => {
    const row = el("div", "vm-row vm-tab");
    row.style.paddingLeft = "8px";
    if (tab.active) row.classList.add("active");
    if (tab.discarded) row.classList.add("discarded");
    row.title = tab.url;
    row.append(iconEl(tab.url, tab.favIconUrl), el("span", "vm-title", tab.title || tab.url));
    row.append(actionButton("×", "Close tab", () => chrome.tabs.remove(tab.id)));
    row.addEventListener("click", () => chrome.tabs.update(tab.id, { active: true }));
    row.addEventListener("auxclick", (e) => { if (e.button === 1) chrome.tabs.remove(tab.id); });
    wireDrag(row, { type: "tab", tab, url: tab.url });
    wireDrop(row, {
      onDrop: async (zone, data) => {
        if (data.type === "bm") return unpin(data);
        if (data.tab.id === tab.id) return;
        // the list shows the highest tab index first, so "before" means a higher index
        const below = data.tab.index < tab.index;
        const index = zone === "before" ? (below ? tab.index : tab.index + 1) : (below ? tab.index - 1 : tab.index);
        await chrome.tabs.move(data.tab.id, { index });
      },
    });
    row.addEventListener("contextmenu", (e) => showMenu(e, [
      ...(state.space ? [
        ["Pin Tab", async () => chrome.bookmarks.create({
          parentId: (state.pinned || await ensureFolder("Pinned")).id, title: tab.title, url: tab.url })],
        ["Add to Favorites", async () => chrome.bookmarks.create({
          parentId: (await ensureFolder("Favorites")).id, title: tab.title, url: tab.url })],
        [],
      ] : []),
      ["Duplicate Tab", () => chrome.tabs.duplicate(tab.id)],
      ["Copy Link", () => copy(tab.url)],
      [],
      ["Close Tab", () => chrome.tabs.remove(tab.id)],
      ["Close Other Tabs", () => {
        const ids = state.tabs.filter((t) => t.id !== tab.id && !t.pinned).map((t) => t.id);
        if (ids.length) chrome.tabs.remove(ids);
      }],
    ]));
    return row;
  };

  // ---- render ----
  const fitHeight = () => {
    if (!panel?.isConnected) return;
    const top = panel.getBoundingClientRect().top;
    panel.style.maxHeight = `${Math.max(120, window.innerHeight - top - BOTTOM_TOOLBAR)}px`;
  };

  const render = () => {
    if (!panel) return;
    const scroll = panel.querySelector(".vm-scroll")?.scrollTop ?? 0;
    const body = el("div", "vm-scroll");
    const favLeaves = state.favs ? state.favs.children.filter((c) => !c.children) : [];
    let grid = null;
    if (state.space) {
      grid = el("div", "vm-favs");
      favLeaves.forEach((n) => grid.append(favTile(n)));
      wireDrop(grid, {
        horizontal: true,
        accept: (d) => !(d.type === "bm" && d.node.children),
        onDrop: async (_zone, data) => insertPinned(data, (await ensureFolder("Favorites")).id, null),
      });
    }
    if (state.space) {
      const label = el("div", "vm-space");
      label.append(el("span", "vm-space-name", spaceLabel(state.space)));
      label.append(actionButton("🎨", "Edit theme", () => window.dispatchEvent(new CustomEvent("vm-open-theme"))));
      wireDrop(label, {
        onDrop: async (_zone, data) => insertPinned(data, (state.pinned || await ensureFolder("Pinned")).id, 0),
      });
      body.append(label);
    }
    if (state.pinned) state.pinned.children.forEach((c) => body.append(pinnedNode(c, 0)));

    const covered = [...favLeaves, ...(state.pinned ? leaves(state.pinned) : [])].map((n) => n.url);
    const blank = state.tabs.filter((t) => BLANK.test(t.url || ""));
    const open = state.tabs.filter((t) => !BLANK.test(t.url || "") && !covered.some((u) => sameSite(t.url, u)));
    const divider = el("div", "vm-divider");
    const clear = el("span", "vm-clear", "Clear");
    clear.addEventListener("click", async () => {
      if (!open.length) return;
      if (open.length + blank.length === state.tabs.length) await chrome.tabs.create({});
      chrome.tabs.remove(open.map((t) => t.id));
    });
    divider.append(clear);
    wireDrop(divider, { accept: isBookmark, onDrop: (_zone, data) => unpin(data) });
    body.append(divider);
    const fresh = el("div", "vm-row vm-newtab");
    fresh.style.paddingLeft = "8px";
    fresh.append(el("span", "vm-plus", "+"), el("span", "vm-title", "New Tab"));
    fresh.addEventListener("click", () => window.dispatchEvent(new CustomEvent("vm-open-command-bar")));
    wireDrop(fresh, { accept: isBookmark, onDrop: (_zone, data) => unpin(data) });
    body.append(fresh);
    open.sort((a, b) => b.index - a.index).forEach((t) => body.append(tabRow(t)));

    panel.replaceChildren(...(grid ? [grid] : []), body);
    body.scrollTop = scroll;
    fitHeight();
  };

  const cacheIcons = async () => {
    for (const t of state.tabs) {
      const src = t.favIconUrl;
      const origin = originOf(t.url);
      if (!src || !/^https?:/.test(origin) || icons[origin] === src || icons[origin]?.startsWith("data:")) continue;
      let value = src;
      if (!src.startsWith("data:")) {
        try {
          const blob = await (await fetch(src)).blob();
          value = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
        } catch (_) {}
      }
      if (value.length < 20000) icons[origin] = value;
    }
    store.set("icons", icons);
  };

  let triedFirstRun = false;
  const createSpace = async (tree) => {
    const bar = tree[0]?.children?.[0];
    if (!bar) return;
    const space = await chrome.bookmarks.create({ parentId: bar.id, title: cfg.spaceFolderTitle });
    await chrome.bookmarks.create({ parentId: space.id, title: "Favorites" });
    await chrome.bookmarks.create({ parentId: space.id, title: "Pinned" });
  };

  const loadBookmarks = async () => {
    let tree = await chrome.bookmarks.getTree();
    if (!findSpace(tree) && !triedFirstRun) {
      triedFirstRun = true;
      await createSpace(tree);
      tree = await chrome.bookmarks.getTree();
    }
    const space = findSpace(tree);
    state.space = space;
    state.favs = space?.children.find((c) => c.children && c.title === "Favorites") ?? null;
    state.pinned = space?.children.find((c) => c.children && c.title === "Pinned") ?? null;
    state.trash = (tree[0]?.children ?? []).find((c) => c.trash === true || /^trash$/i.test(c.title)) ?? null;
  };
  const loadTabs = async () => {
    state.tabs = await chrome.tabs.query({ currentWindow: true });
    cacheIcons();
  };

  let timer = 0;
  function refresh(withBookmarks) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (drag) { refreshAfterDrag = true; return; } // re-rendering would detach the node being dragged
      refreshAfterDrag = false;
      try {
        if (withBookmarks) await loadBookmarks();
        await loadTabs();
        render();
      } catch (e) { console.warn("[vivarc] sidebar:", e); }
    }, 80);
  }

  // ---- placement ----
  const place = () => {
    const container = document.querySelector("#tabs-container.left, #tabs-container.right");
    const strip = container?.querySelector(".tab-strip");
    if (!strip) return;
    let anchor = strip;
    while (anchor.parentElement !== container) anchor = anchor.parentElement;
    if (!panel) {
      panel = el("div");
      panel.id = "vm-panel";
      panel.addEventListener("contextmenu", (e) => showMenu(e, [
        ["New Folder", async () => { await newFolder(null); }],
        ["Edit Theme…", () => window.dispatchEvent(new CustomEvent("vm-open-theme"))],
        ["New Tab", () => window.dispatchEvent(new CustomEvent("vm-open-command-bar"))],
        ["Reopen Closed Tab", () => chrome.sessions.restore()],
      ]));
      refresh(true);
    }
    anchor.classList.add("vm-strip-hidden");
    for (const row of container.children) {
      if (row === panel || row === anchor) continue;
      const bare = ![...row.querySelectorAll("button, a, [role=button], .button-toolbar")]
        .some((n) => !n.closest(".UrlBar-AddressField"));
      row.classList.toggle("vm-collapsed", bare && !!row.querySelector(".UrlBar-AddressField"));
    }
    fitHeight();
    if (panel.parentElement !== container || panel.nextElementSibling !== anchor) {
      container.insertBefore(panel, anchor);
    }
  };

  // Like Arc, opening the command bar scrolls the sidebar down to the new-tab area.
  window.addEventListener("vm-command-bar-opened", () => {
    const scroller = panel?.querySelector(".vm-scroll");
    scroller?.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
  });

  const start = () => {
    let queued = false;
    new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; place(); });
    }).observe(document.body, { childList: true, subtree: true });
    place();
    window.addEventListener("resize", fitHeight);
    for (const ev of ["onCreated", "onRemoved", "onChanged", "onMoved", "onImportEnded"]) {
      chrome.bookmarks[ev]?.addListener(() => refresh(true));
    }
    for (const ev of ["onCreated", "onRemoved", "onUpdated", "onMoved", "onActivated", "onAttached", "onDetached", "onReplaced"]) {
      chrome.tabs[ev]?.addListener(() => refresh(false));
    }
    console.log("[vivarc] sidebar started");
  };

  const init = async () => {
    if (!(await window.__vm.ready)) return;
    (await store.get("open", [])).forEach((id) => openFolders.add(id));
    icons = await store.get("icons", {});
    start();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
