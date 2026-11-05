// Vivarc tab switcher, like Arc's: Ctrl+Tab opens a row of the recent tabs, Tab / Shift+Tab move through it and
// letting go of Ctrl switches to the selected one. It lists the five latest tabs. Holding Tab keeps moving, faster and faster. A quick Ctrl+Tab just goes to the previous tab: the row only
// shows once the keys are held for a moment.
(() => {
  const { recent, normalise, keys } = window.__vm;
  const NEXT = normalise(keys.tabNext);
  const PREV = normalise(keys.tabPrev);
  const SHOW_AFTER = 150;
  const FIRST_REPEAT = 260;
  const MIN_REPEAT = 45;
  const REPEAT_SPEEDUP = 30;
  const DOUBLE_STEP = 60; // a press can arrive both as Vivaldi's shortcut event and as a key event of the switcher

  let bar = null;
  let strip = null;
  let items = [];
  let selected = 0;
  let opening = false;
  let lastStep = 0;
  let showTimer = 0;
  let held = { n: 0, at: 0 }; // how many repeats of the held Tab so far, and when the last one moved
  let keysSeen = false; // the switcher gets the key events itself, so Vivaldi's shortcut events are not needed

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  // Vivaldi can only capture the tab on screen, so shots are taken while a tab is the active one and kept for later.
  const thumbs = new Map();
  const capture = async (id) => {
    try {
      const shot = await vivaldi.thumbnails.captureTab(id, { encodeFormat: "jpg", encodeQuality: 70, fullPage: false, width: 330, height: 270 });
      if (typeof shot === "string" && shot) thumbs.set(id, shot);
    } catch (_) {}
  };
  const captureSoon = (id, delay) => setTimeout(async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id === id && !bar) capture(id);
  }, delay);
  chrome.tabs.onActivated.addListener(({ tabId }) => captureSoon(tabId, 700));
  chrome.tabs.onUpdated.addListener((id, change, tab) => { if (change.status === "complete" && tab.active) captureSoon(id, 1500); });
  chrome.tabs.onRemoved.addListener((id) => thumbs.delete(id));

  const faviconOf = (tab, cls) => {
    const wrap = el("span", cls);
    if (tab.favIconUrl) {
      const img = el("img");
      img.src = tab.favIconUrl;
      img.addEventListener("error", () => img.remove());
      wrap.append(img);
    }
    return wrap;
  };

  const card = (tab, index) => {
    const c = el("div", `vm-sw-card${index === selected ? " sel" : ""}`);
    const thumb = el("div", "vm-sw-thumb");
    const shot = thumbs.get(tab.id);
    if (shot) {
      const img = el("img");
      img.src = shot;
      thumb.append(img);
    } else {
      thumb.append(faviconOf(tab, "vm-sw-big"));
    }
    const label = el("div", "vm-sw-label");
    label.append(faviconOf(tab, "vm-sw-ico"), el("span", "vm-sw-title", tab.title || tab.url || ""));
    c.append(thumb, label);
    c.addEventListener("mousemove", () => select(index));
    c.addEventListener("mousedown", (e) => { e.preventDefault(); select(index); commit(); });
    return c;
  };

  const select = (index) => {
    if (!bar || index === selected) return;
    selected = index;
    [...strip.children].forEach((c, i) => c.classList.toggle("sel", i === index));
  };

  const move = (dir) => select(recent.step(selected, dir, items.length));

  const advance = (dir) => {
    const now = Date.now();
    if (!bar || now - lastStep < DOUBLE_STEP) return;
    lastStep = now;
    move(dir);
  };

  // The operating system repeats a held key at a steady rate; the pace of the selection speeds up from one
  // step per 260ms to one per 45ms.
  const repeat = (dir) => {
    const now = Date.now();
    if (now - held.at < Math.max(MIN_REPEAT, FIRST_REPEAT - REPEAT_SPEEDUP * held.n)) return;
    held = { n: held.n + 1, at: now };
    move(dir);
  };

  const close = () => {
    clearTimeout(showTimer);
    window.removeEventListener("keydown", onKeyDown, true);
    window.removeEventListener("keyup", onKeyUp, true);
    window.removeEventListener("mousemove", onMouseMove, true);
    bar?.remove();
    bar = strip = null;
    items = [];
    keysSeen = false;
  };

  const commit = () => {
    const tab = items[selected];
    close();
    if (tab) chrome.tabs.update(tab.id, { active: true });
  };

  // The key events of this window only: Vivaldi's page has the focus until the switcher takes it, which is why the
  // switcher focuses itself and listens for Ctrl being released there.
  const onKeyDown = (e) => {
    if (!e.ctrlKey && e.key !== "Control") { commit(); return; }
    if (e.key === "Tab" || e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      e.stopPropagation();
      keysSeen = true;
      const dir = e.key === "ArrowLeft" || (e.key === "Tab" && e.shiftKey) ? -1 : 1;
      if (e.repeat) {
        repeat(dir);
      } else {
        held = { n: 0, at: Date.now() };
        advance(dir);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit();
    }
  };
  const onKeyUp = (e) => { if (e.key === "Control") commit(); };
  const onMouseMove = (e) => { if (!e.ctrlKey) commit(); };

  const open = async (dir) => {
    if (opening) return;
    opening = true;
    const tabs = recent.order(await chrome.tabs.query({ currentWindow: true }));
    opening = false;
    if (bar) return;
    const start = recent.first(dir, tabs.length);
    if (start == null) return;
    items = tabs;
    selected = start;
    lastStep = held.at = Date.now();
    held.n = 0;
    bar = el("div");
    bar.id = "vm-switch";
    bar.tabIndex = -1;
    strip = el("div", "vm-sw-strip");
    strip.append(...items.map(card));
    const panel = el("div", "vm-sw-panel");
    panel.append(strip);
    bar.append(panel);
    bar.addEventListener("mousedown", (e) => { if (e.target === bar) close(); });
    (document.querySelector("#browser") || document.body).append(bar);
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("keyup", onKeyUp, true);
    window.addEventListener("mousemove", onMouseMove, true);
    const focus = () => bar?.focus();
    focus();
    setTimeout(focus, 60);
    showTimer = setTimeout(() => bar?.classList.add("in"), SHOW_AFTER);
    const current = items[0];
    capture(current.id).then(() => {
      const img = thumbs.get(current.id);
      const thumb = strip?.children[0]?.querySelector(".vm-sw-thumb");
      if (img && thumb) thumb.replaceChildren(Object.assign(el("img"), { src: img }));
    });
  };

  window.__vm.onShortcut((key) => {
    if (key !== NEXT && key !== PREV) return;
    const dir = key === NEXT ? 1 : -1;
    if (!bar) open(dir);
    else if (!keysSeen) advance(dir);
  });
  console.log("[vivarc] tab switcher started");
})();
