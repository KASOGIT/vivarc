// Vivarc settings: switches that apply live, saved per profile (like the theme) and shared by the profile's windows.
// Precedence: what the user saved, then the install config (~/.vivarc/config.json), then the default.
(() => {
  // onClass / offClass: a marker class on #browser while the setting is on / off (the stylesheet reacts to it).
  // needs: the row shows only while that other setting is on. requires: the row shows only when the install config
  // has that flag (Peek is optional, see 03-peek.js). section: the heading it sits under, in SECTIONS order.
  const SECTIONS = ["Appearance", "Sidebar", "Tabs", "Link preview", "General"];
  const SCHEMA = [
    { key: "glass", section: "Appearance", label: "Liquid glass", hint: "Translucent, blurred sidebar, menus and dialogs. Follows Reduce Transparency.",
      default: false, onClass: "vm-glass" },
    { key: "glassOpacity", section: "Appearance", type: "range", min: 15, max: 95, step: 1, default: 55, unit: "%", needs: "glass", cssVar: "--vm-glass-opacity",
      label: "Glass opacity", low: "Clear", high: "Frosted" },
    { key: "urlBar", section: "Sidebar", label: "URL bar", hint: "Always show the address bar. Off, it appears when you edit the address.",
      default: false, onClass: "vm-url-bar" },
    { key: "spaceBar", section: "Sidebar", label: "Space bar", hint: "The row of space tiles at the bottom.", default: true, offClass: "vm-no-space-bar" },
    { key: "compactBottomBar", section: "Sidebar", label: "Compact bottom bar", hint: "A tighter row for profiles and downloads.", default: true,
      fromConfig: (c) => c.compactBottomBar, onClass: "vm-compact-bottom" },
    { key: "archive", section: "Tabs", label: "Archive inactive tabs", hint: "Close tabs left unopened, like Arc. Pins, favorites and tabs playing sound stay.",
      default: false },
    { key: "archiveHours", section: "Tabs", type: "range", min: 1, max: 168, step: 1, default: 12, unit: " h", needs: "archive",
      label: "Archive after", low: "1 hour", high: "7 days" },
    { key: "peek", section: "Link preview", label: "Link preview (Peek)", hint: "Open some links in a floating window over the page. Esc closes it.",
      default: true, requires: "peekInstalled" },
    { key: "peekPinned", section: "Link preview", label: "From pinned tabs", hint: "A link to another site opens in the preview, like Arc.",
      default: true, needs: "peek", requires: "peekInstalled" },
    { key: "peekShortcut", section: "Link preview", type: "choice", default: "alt", needs: "peek", requires: "peekInstalled",
      options: [["alt", null], ["shift", null], ["none", "Off"]],
      label: "Shortcut", hint: "Click a link with this key held. Cmd+click still opens a new tab." },
    { key: "peekDim", section: "Link preview", label: "Dim the page behind", default: true, needs: "peek", requires: "peekInstalled" },
    { key: "searchSuggestions", section: "General", label: "Search suggestions", hint: "From your default search engine, in the command bar.",
      default: true, fromConfig: (c) => (c.suggestions === undefined ? undefined : c.suggestions !== "off" && c.suggestions !== false) },
    { key: "updateCheck", section: "General", label: "Check for updates", hint: "Ask GitHub now and then for a new Vivarc release. Off, nothing is requested.",
      default: true },
  ];

  const resolve = (schema, config, saved) => Object.fromEntries(schema.map((s) => {
    const mine = saved?.[s.key];
    if (s.type === "choice") return [s.key, s.options.some(([value]) => value === mine) ? mine : s.default];
    if (s.type === "range") {
      return [s.key, typeof mine === "number" && Number.isFinite(mine) ? Math.min(s.max, Math.max(s.min, Math.round(mine))) : s.default];
    }
    const fromConfig = s.fromConfig?.(config || {});
    const base = typeof fromConfig === "boolean" ? fromConfig : s.default;
    return [s.key, typeof mine === "boolean" ? mine : base];
  }));

  // CSS custom properties for the range settings, set on #browser.
  const vars = (schema, values) => Object.fromEntries(schema.filter((s) => s.cssVar).map((s) => [s.cssVar, `${values[s.key]}${s.unit || ""}`]));

  const classes = (schema, values) => Object.fromEntries(schema.flatMap((s) => [
    ...(s.onClass ? [[s.onClass, !!values[s.key]]] : []),
    ...(s.offClass ? [[s.offClass, !values[s.key]]] : []),
  ]));

  const visible = (schema, config) => schema.filter((s) => !s.requires || !!config?.[s.requires]);

  const sections = (schema, config) => SECTIONS
    .map((title) => ({ title, items: visible(schema, config).filter((s) => s.section === title) }))
    .filter((section) => section.items.length);

  const shownRows = (schema, values) => schema.filter((s) => !s.needs || !!values[s.needs]);

  const api = { SCHEMA, resolve, classes, vars, visible, sections, shownRows };
  window.__vm.settings = api;
  if (!window.__vm.store) return;

  const { store, config } = window.__vm;
  const listeners = new Set();
  const channel = new BroadcastChannel("vivarc-settings");
  // A copy of the saved values in localStorage is read synchronously, so the first modules to start (Peek injects
  // into the restored pages right away) see the user's settings rather than the defaults until IndexedDB answers.
  const CACHE = "vivarc-settings";
  const cached = () => { try { return JSON.parse(localStorage.getItem(CACHE) || "{}") || {}; } catch (_) { return {}; } };
  let saved = cached();
  let values = resolve(SCHEMA, config, saved);

  const apply = (browser) => {
    for (const [name, on] of Object.entries(classes(SCHEMA, values))) browser.classList.toggle(name, on);
    for (const [name, value] of Object.entries(vars(SCHEMA, values))) browser.style.setProperty(name, value);
  };
  const update = (next) => {
    saved = next || {};
    try { localStorage.setItem(CACHE, JSON.stringify(saved)); } catch (_) {}
    values = resolve(SCHEMA, config, saved);
    const browser = document.querySelector("#browser");
    if (browser) apply(browser);
    listeners.forEach((fn) => fn(values));
  };
  const persist = () => { store.set("settings", saved); channel.postMessage(saved); };

  Object.assign(api, {
    get: (key) => values[key],
    all: () => ({ ...values }),
    onChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    set: (key, value) => { update({ ...saved, [key]: value }); persist(); },
    reset: () => { update({}); persist(); },
  });

  channel.onmessage = (e) => update(e.data);
  window.__vm.onMark(apply);
  store.get("settings", {}).then(update);
})();
