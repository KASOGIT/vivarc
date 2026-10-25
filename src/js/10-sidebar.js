// Vivarc sidebar: favorites grid on top, then one scrollable panel (pinned folders, divider,
// open tabs). The data lives in a bookmarks folder that has a "Favorites" and a "Pinned" subfolder
// (created on first run, or produced by `vivarc import-arc`). Vivaldi's own tab strip is hidden.
(() => {
  const cfg = window.__vm.config;
  const BLANK = /^(chrome|vivaldi):\/\/(newtab|vivaldi-webui\/startpage)/;
  const BOTTOM_TOOLBAR = cfg.compactBottomBar ? 35 : 64;

  const store = window.__vm.store;
  const openFolders = new Set();
  const seedIcons = window.__vmIcons || {};
  let icons = {};
  const saveOpen = () => store.set("open", [...openFolders]);
  const state = { space: null, defaultSpace: null, folders: [], favs: null, pinned: null, trash: null, tabs: [], allTabs: [], bound: new Map(),
    profiles: [], renameId: null, workspaces: [], active: 0 };
  const spacesOf = window.__vm.workspaces;
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

  const pinLinks = window.__vm.pins;
  const { sameSite } = pinLinks;

  const originOf = (url) => {
    try { return new URL(url).origin; } catch (_) { return ""; }
  };

  const letterIcon = (url) => {
    let host = "?";
    try { host = new URL(url).hostname.replace(/^www\./, "") || (url.startsWith("file:") ? "vivarc" : "?"); } catch (_) {}
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
  const findSpaces = (nodes) => nodes.flatMap((n) => hasPinnedChild(n) ? [n] : n.children ? findSpaces(n.children) : []);

  // The tab that belongs to a pin or favorite stays bound to it wherever it navigates (see 08-pins.js).
  const boundTab = (node) => state.bound.get(node.id);
  const isAway = (tab, node) => !!tab && pinLinks.away(tab, node.url);

  // Re-read the tab right before writing: Vivaldi keeps its own keys in the same field.
  const writeExt = async (tabId, patch) => {
    const local = state.tabs.find((t) => t.id === tabId);
    if (local) local.vivExtData = pinLinks.patched(local, patch);
    try {
      const fresh = await chrome.tabs.get(tabId);
      if (pinLinks.needsWrite(fresh, patch)) await chrome.tabs.update(tabId, { vivExtData: pinLinks.patched(fresh, patch) });
    } catch (_) {}
  };

  // A pin opened from the sidebar remembers where it landed after the site's redirects.
  const recordHome = (tabId, pinId) => {
    const done = () => chrome.tabs.onUpdated.removeListener(onUpdated);
    const onUpdated = async (id, change) => {
      if (id !== tabId || change.status !== "complete") return;
      done();
      try {
        const fresh = await chrome.tabs.get(tabId);
        if (pinLinks.pinOf(fresh) === pinId && pinLinks.homeOf(fresh) === undefined) {
          writeExt(tabId, { [pinLinks.HOME]: pinLinks.norm(fresh.url) });
        }
      } catch (_) {}
    };
    chrome.tabs.onUpdated.addListener(onUpdated);
    setTimeout(done, 60000);
  };

  const openPin = async (node) => {
    const tab = await chrome.tabs.create({ url: node.url });
    await writeExt(tab.id, { [pinLinks.PIN]: node.id });
    recordHome(tab.id, node.id);
  };

  const focusOrOpen = (node) => {
    const tab = boundTab(node);
    if (tab) chrome.tabs.update(tab.id, { active: true });
    else openPin(node);
  };

  const backToPin = (tab, node) => chrome.tabs.update(tab.id, { url: node.url });

  // The page you are on moves to a regular tab and the pinned tab goes back to its pinned page.
  const separate = async (tab, node) => {
    await chrome.tabs.create({ url: tab.url, index: tab.index + 1 });
    await chrome.tabs.update(tab.id, { url: node.url });
  };

  const bindTabs = () => {
    if (!state.space) { state.bound = new Map(); return; }
    const pins = [...(state.favs ? leaves(state.favs) : []), ...(state.pinned ? leaves(state.pinned) : [])]
      .map((n) => ({ id: n.id, url: n.url }));
    const allIds = state.folders.flatMap((f) => leaves(f)).map((n) => n.id);
    const { bound, writes } = pinLinks.plan(state.tabs, pins, allIds);
    state.bound = bound;
    for (const { tabId, patch } of writes) writeExt(tabId, patch);
  };

  // Favorites are shared by every space (like Arc's); Pinned belongs to the space on screen.
  const ensureFolder = async (name) => {
    const owner = name === "Favorites" ? state.defaultSpace : state.space;
    const existing = owner.children.find((c) => c.children && c.title === name);
    if (existing) return existing;
    return chrome.bookmarks.create({ parentId: owner.id, title: name, index: 0 });
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
    const hadTab = boundTab(data.node);
    discard(data.node);
    if (!hadTab) await chrome.tabs.create({ url, active: false });
  };

  // ---- rows ----
  const actionButton = (symbol, title, onClick) => {
    const b = el("span", "vm-act", symbol);
    b.title = title;
    b.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return b;
  };

  const editTitle = (field, node, cleanup = () => {}) => {
    field.value = node.title;
    field.focus();
    field.select();
    let done = false;
    const finish = (commit) => {
      if (done) return;
      done = true;
      cleanup();
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
  const startRename = (titleEl, node) => {
    const field = el("input", "vm-rename");
    titleEl.replaceWith(field);
    editTitle(field, node);
  };
  // A favorite tile only shows its icon, so its name is edited in a field floating under its row of the grid.
  const renameFavorite = (tile, node) => {
    const grid = tile.closest(".vm-favs");
    if (!grid) return;
    const box = grid.getBoundingClientRect();
    const field = el("input", "vm-rename-float");
    field.style.left = `${box.left}px`;
    field.style.top = `${tile.getBoundingClientRect().bottom + 6}px`;
    field.style.width = `${box.width}px`;
    (document.querySelector("#browser") || document.body).append(field);
    editTitle(field, node, () => field.remove());
  };

  const bookmarkMenu = (node, isFav) => (e) => {
    const tab = boundTab(node);
    showMenu(e, [
      ["Open in New Tab", () => chrome.tabs.create({ url: node.url })],
      ["Copy Link", () => copy(node.url)],
      ["Rename…", () => { state.renameId = node.id; refresh(true); }],
      ...(isAway(tab, node) ? [
        [isFav ? "Back to Favorite Page" : "Back to Pinned Page", () => backToPin(tab, node)],
        ["Separate From Pinned Tab", () => separate(tab, node)],
      ] : []),
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
    const tab = boundTab(node);
    const away = isAway(tab, node);
    row.title = away ? `${node.title || node.url}\n${tab.url}` : node.url;
    if (tab?.active) row.classList.add("active");
    if (away) row.classList.add("away");
    row.append(iconEl(node.url, away ? undefined : tab?.favIconUrl));
    if (away) row.append(el("span", "vm-away-mark", "/"));
    const title = el("span", "vm-title", away ? (tab.title || tab.url) : (node.title || node.url));
    row.append(title);
    if (away) row.append(actionButton("↩", "Back to pinned page", () => backToPin(tab, node)));
    if (!tab) row.append(actionButton("×", "Remove from Pinned", () => discard(node)));
    else if (away) row.append(actionButton("–", "Separate From Pinned Tab", () => separate(tab, node)));
    else row.append(actionButton("–", "Close tab", () => chrome.tabs.remove(tab.id)));
    row.addEventListener("click", () => focusOrOpen(node));
    row.addEventListener("contextmenu", bookmarkMenu(node, false));
    wireDrag(row, { type: "bm", node, url: node.url });
    wireDrop(row, {
      onDrop: async (zone, data) => {
        if (data.type === "bm" && data.node.id === node.id) return;
        await insertPinned(data, node.parentId, node.index + (zone === "after" ? 1 : 0));
      },
    });
    if (state.renameId === node.id) {
      state.renameId = null;
      setTimeout(() => startRename(title, node), 0);
    }
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
    const tab = boundTab(node);
    const away = isAway(tab, node);
    if (tab?.active) tile.classList.add("active");
    if (away) tile.classList.add("away");
    tile.append(iconEl(node.url, away ? undefined : tab?.favIconUrl));
    tile.addEventListener("click", () => focusOrOpen(node));
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
    if (state.renameId === node.id) {
      state.renameId = null;
      setTimeout(() => renameFavorite(tile, node), 0);
    }
    return tile;
  };

  const tabRow = (tab) => {
    const row = el("div", "vm-row vm-tab");
    row.style.paddingLeft = "8px";
    if (tab.active) row.classList.add("active");
    if (tab.discarded) row.classList.add("discarded");
    row.title = tab.url;
    row.append(iconEl(tab.url, tab.favIconUrl), el("span", "vm-title", tab.title || tab.url));
    if (window.__vm.tilingOf(tab)) row.append(el("span", "vm-split-mark", "◫"));
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

  // ---- profile switcher ----
  const openProfile = (path) => vivaldi.runtimePrivate.openNamedProfile(path, (ok) => {
    if (!ok) console.warn("[vivarc] could not open profile", path);
  });

  const profileChip = (chip, index) => {
    const node = el("div", `vm-space-chip${chip.active ? " active" : ""}`);
    node.title = chip.active ? chip.name : `${chip.name}${index < 9 ? ` (⌃⌘${index + 1})` : ""}`;
    const letter = () => {
      const span = el("span", "vm-space-letter", chip.letter);
      span.style.backgroundColor = `hsl(${chip.hue} 38% 40%)`;
      return span;
    };
    if (chip.avatar) {
      const img = el("img");
      img.addEventListener("error", () => img.replaceWith(letter()));
      img.src = chip.avatar;
      node.append(img);
    } else {
      node.append(letter());
    }
    if (chip.active) {
      node.addEventListener("contextmenu", (e) => showMenu(e, [
        ["Manage Profiles…", () => vivaldi.runtimePrivate.openProfileSelectionWindow()],
      ]));
    } else {
      node.addEventListener("click", () => openProfile(chip.path));
    }
    return node;
  };

  const promptProfileName = (bar, plus) => {
    const field = el("input", "vm-space-input");
    field.placeholder = "New profile";
    try { vivaldi.runtimePrivate.getProfileDefaults((name) => { if (!field.value) field.value = name || ""; field.select(); }); } catch (_) {}
    plus.replaceWith(field);
    field.focus();
    let done = false;
    const finish = async (commit) => {
      if (done) return;
      done = true;
      const name = field.value.trim();
      if (commit && name) {
        const images = await new Promise((resolve) => vivaldi.runtimePrivate.getUserProfileImages(resolve));
        const index = Math.floor(Math.random() * (images?.length || 1));
        vivaldi.runtimePrivate.createProfile(name, index, false, (ok) => { if (!ok) console.warn("[vivarc] could not create the profile"); });
      }
      renderProfileBar();
    };
    field.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") finish(true);
      if (e.key === "Escape") finish(false);
    });
    field.addEventListener("blur", () => finish(false));
  };

  let profileBarEl = null;
  const renderProfileBar = () => {
    const chips = window.__vm.spaces.profileChips(state.profiles);
    if (!chips.length) { profileBarEl?.remove(); return; }
    profileBarEl ||= el("div", "vm-spaces");
    const plus = el("div", "vm-space-chip vm-space-plus", "+");
    plus.title = "New profile";
    plus.addEventListener("click", () => promptProfileName(profileBarEl, plus));
    profileBarEl.replaceChildren(...chips.map(profileChip), plus);
  };

  const placeProfileBar = () => {
    if (!profileBarEl?.isConnected && profileBarEl) {
      const toolbar = document.querySelector("#tabs-tabbar-container .toolbar-tabbar-after");
      toolbar?.prepend(profileBarEl);
    }
  };

  const loadProfiles = () => {
    try {
      vivaldi.runtimePrivate.getUserProfiles((list) => {
        state.profiles = list || [];
        renderProfileBar();
        placeProfileBar();
        window.__vm.spaces.syncBottomBar(window.__vm.spaces.wantsAccountButton(state.profiles)).catch((e) => console.warn("[vivarc] bottom bar:", e));
      });
    } catch (e) {
      console.warn("[vivarc] profile list unavailable:", e);
    }
  };

  // ---- space bar: Vivaldi workspaces as Arc-style spaces ----
  const switchSpace = async (item) => {
    if (item.id === state.active) return;
    const tab = spacesOf.recentTab(state.allTabs, item.id);
    if (tab) await chrome.tabs.update(tab.id, { active: true });
    else await chrome.tabs.create({ active: true, vivExtData: JSON.stringify({ workspaceId: item.id }) });
  };

  const spacePill = (item) => {
    const pill = el("div", `vm-space-pill${item.id === state.active ? " active" : ""}`, item.emoji || item.name.trim().charAt(0).toUpperCase() || "?");
    pill.title = item.name;
    pill.addEventListener("click", () => switchSpace(item));
    return pill;
  };

  const spaceBar = () => {
    const items = spacesOf.items(state.workspaces, state.defaultSpace ? spacesOf.label(state.defaultSpace) : "Home");
    if (!items.length) return null;
    const bar = el("div", "vm-space-bar");
    const plus = el("div", "vm-space-pill vm-space-plus", "+");
    plus.title = "New space";
    plus.addEventListener("click", () => window.dispatchEvent(new CustomEvent("vm-toast", { detail: spacesOf.CREATE_HINT })));
    bar.append(...items.map(spacePill), plus);
    return bar;
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
    if (state.defaultSpace) {
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
      label.append(el("span", "vm-space-name", spacesOf.label(state.space)));
      label.append(actionButton("🎨", "Edit theme", () => window.dispatchEvent(new CustomEvent("vm-open-theme"))));
      wireDrop(label, {
        onDrop: async (_zone, data) => insertPinned(data, (state.pinned || await ensureFolder("Pinned")).id, 0),
      });
      body.append(label);
    }
    if (state.pinned) state.pinned.children.forEach((c) => body.append(pinnedNode(c, 0)));

    const taken = new Set([...state.bound.values()].map((t) => t.id));
    const blank = state.tabs.filter((t) => BLANK.test(t.url || ""));
    const open = state.tabs.filter((t) => !BLANK.test(t.url || "") && !taken.has(t.id));
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

    const bar = spaceBar();
    panel.replaceChildren(...(grid ? [grid] : []), body, ...(bar ? [bar] : []));
    body.scrollTop = scroll;
    fitHeight();
  };

  const ICON_MAX = 20000;
  const dataUrl = (blob) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
  // Some favicons are multi-size .ico files (Gmail's is 26 KB): too big to keep as is, so they are
  // redrawn at 64px, enough for the 24px tiles on a Retina screen.
  const shrinkIcon = async (blob) => {
    const bitmap = await createImageBitmap(blob, { resizeWidth: 64, resizeHeight: 64, resizeQuality: "high" });
    const canvas = new OffscreenCanvas(64, 64);
    canvas.getContext("2d").drawImage(bitmap, 0, 0);
    return dataUrl(await canvas.convertToBlob({ type: "image/png" }));
  };
  const cacheIcons = async () => {
    for (const t of state.allTabs) {
      const src = t.favIconUrl;
      const origin = originOf(t.url);
      if (!src || !/^https?:/.test(origin) || icons[origin] === src || icons[origin]?.startsWith("data:")) continue;
      let value = src;
      try {
        const blob = await (await fetch(src)).blob();
        value = await dataUrl(blob);
        if (value.length >= ICON_MAX) value = await shrinkIcon(blob);
      } catch (_) {}
      if (value.length < ICON_MAX) icons[origin] = value;
    }
    store.set("icons", icons);
  };

  const STARTER_FAVORITES = [
    ["Gmail", "https://mail.google.com/"],
    ["Calendar", "https://calendar.google.com/"],
    ["Drive", "https://drive.google.com/"],
    ["YouTube", "https://www.youtube.com/"],
    ["GitHub", "https://github.com/"],
    ["Maps", "https://www.google.com/maps"],
  ];

  // A pinned link, a folder with two links, and a folder nested inside it, so the layout is visible on day one.
  const addStarterPins = async (pinnedId) => {
    if (cfg.startUrl) await chrome.bookmarks.create({ parentId: pinnedId, title: "Vivarc Guide", url: cfg.startUrl });
    const reading = await chrome.bookmarks.create({ parentId: pinnedId, title: "Reading" });
    await chrome.bookmarks.create({ parentId: reading.id, title: "Hacker News", url: "https://news.ycombinator.com/" });
    await chrome.bookmarks.create({ parentId: reading.id, title: "Wikipedia", url: "https://www.wikipedia.org/" });
    const dev = await chrome.bookmarks.create({ parentId: reading.id, title: "Dev" });
    await chrome.bookmarks.create({ parentId: dev.id, title: "MDN Web Docs", url: "https://developer.mozilla.org/" });
    await chrome.bookmarks.create({ parentId: dev.id, title: "Stack Overflow", url: "https://stackoverflow.com/" });
    openFolders.add(reading.id);
    openFolders.add(dev.id);
    saveOpen();
  };

  let triedFirstRun = false;
  const createSpace = async (tree) => {
    const bar = tree[0]?.children?.[0];
    if (!bar) return;
    const space = await chrome.bookmarks.create({ parentId: bar.id, title: cfg.spaceFolderTitle });
    const favs = await chrome.bookmarks.create({ parentId: space.id, title: "Favorites" });
    for (const [title, url] of STARTER_FAVORITES) await chrome.bookmarks.create({ parentId: favs.id, title, url });
    const pinned = await chrome.bookmarks.create({ parentId: space.id, title: "Pinned" });
    await addStarterPins(pinned.id);
  };

  const loadBookmarks = async () => {
    let tree = await chrome.bookmarks.getTree();
    if (!findSpaces(tree).length && !triedFirstRun) {
      triedFirstRun = true;
      await createSpace(tree);
      tree = await chrome.bookmarks.getTree();
    }
    state.folders = findSpaces(tree);
    state.trash = (tree[0]?.children ?? []).find((c) => c.trash === true || /^trash$/i.test(c.title)) ?? null;
  };

  // The folder of the space on screen. A workspace Vivarc meets for the first time gets its own empty Pinned folder.
  const madeFolderFor = new Set();
  const applySpace = async () => {
    const pick = () => {
      const { default: base, byId } = spacesOf.assign(state.folders, state.workspaces);
      return { base, space: state.active ? byId[state.active] ?? null : base };
    };
    let picked = pick();
    const workspace = state.workspaces.find((w) => w.id === state.active);
    if (!picked.space && workspace && picked.base && !madeFolderFor.has(workspace.id)) {
      madeFolderFor.add(workspace.id);
      const folder = await chrome.bookmarks.create({ parentId: picked.base.parentId, title: workspace.name });
      await chrome.bookmarks.create({ parentId: folder.id, title: "Pinned" });
      await loadBookmarks();
      picked = pick();
    }
    state.defaultSpace = picked.base;
    state.space = picked.space;
    state.favs = picked.base?.children.find((c) => c.children && c.title === "Favorites") ?? null;
    state.pinned = picked.space?.children.find((c) => c.children && c.title === "Pinned") ?? null;
  };

  const readWorkspaces = async () => {
    try { return (await vivaldi.prefs.get("vivaldi.workspaces.list"))?.value || []; } catch (_) { return []; }
  };
  const loadTabs = async () => {
    state.allTabs = await chrome.tabs.query({ currentWindow: true });
    state.workspaces = await readWorkspaces();
    ({ active: state.active, tabs: state.tabs } = spacesOf.scope(state.allTabs, state.workspaces));
  };

  // Calls inside the debounce window are merged, and a request to reload bookmarks is never lost to a later
  // tab-only refresh (at start-up the tab events used to cancel the first bookmark load, leaving the sidebar empty).
  let timer = 0;
  let wantBookmarks = false;
  let failures = 0;
  function refresh(withBookmarks) {
    wantBookmarks ||= !!withBookmarks;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (drag) { refreshAfterDrag = true; return; } // re-rendering would detach the node being dragged
      refreshAfterDrag = false;
      const bookmarks = wantBookmarks || !state.defaultSpace;
      wantBookmarks = false;
      try {
        await loadTabs();
        if (bookmarks) await loadBookmarks();
        await applySpace();
        bindTabs();
        cacheIcons();
        render();
        failures = 0;
      } catch (e) {
        console.warn("[vivarc] sidebar:", e);
        if (++failures <= 5) { wantBookmarks = bookmarks; setTimeout(() => refresh(false), 1500); }
      }
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
    placeProfileBar();
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
    chrome.tabs.onCreated.addListener((tab) => {
      const active = state.active;
      chrome.windows.getCurrent().then((win) => {
        const data = spacesOf.stamp(tab, active, win.id);
        if (data) chrome.tabs.update(tab.id, { vivExtData: data });
      }).catch(() => {});
    });
    for (const ev of ["onCreated", "onRemoved", "onUpdated", "onMoved", "onActivated", "onAttached", "onDetached", "onReplaced"]) {
      chrome.tabs[ev]?.addListener(() => refresh(false));
    }
    setInterval(async () => {
      const brief = (list) => JSON.stringify(list.map((w) => [w.id, w.name, w.emoji]));
      if (brief(await readWorkspaces()) !== brief(state.workspaces)) refresh(false);
    }, 3000);
    try {
      vivaldi.runtimePrivate.onProfilesUpdated.addListener(loadProfiles);
      window.__vm.onShortcut((key) => {
        const path = window.__vm.spaces.pathForShortcut(state.profiles, key);
        if (path) openProfile(path);
      });
    } catch (e) {
      console.warn("[vivarc] profile switching unavailable:", e);
    }
    loadProfiles();
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
