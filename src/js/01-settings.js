// Vivarc settings: switches that apply live, saved per profile (like the theme) and shared by the profile's windows.
// Precedence: what the user saved, then the install config (~/.vivarc/config.json), then the default.
(() => {
  // onClass / offClass: a marker class on #browser while the setting is on / off (the stylesheet reacts to it).
  const SCHEMA = [
    { key: "glass", label: "Liquid glass", hint: "Translucent, blurred sidebar, menus, command bar and dialogs, after Apple's Liquid Glass. Follows Reduce Transparency and Increase Contrast.",
      default: false, onClass: "vm-glass" },
    { key: "glassOpacity", type: "range", min: 15, max: 95, step: 1, default: 55, unit: "%", needs: "glass", cssVar: "--vm-glass-opacity",
      label: "Glass opacity", hint: "From clear to frosted: how much of the surface colour shows through the glass.", low: "Clear", high: "Frosted" },
    { key: "spaceBar", label: "Space bar", hint: "The row of space tiles under the sidebar.", default: true, offClass: "vm-no-space-bar" },
    { key: "compactBottomBar", label: "Compact bottom bar", hint: "A tighter row for the profile avatars and downloads.", default: true,
      fromConfig: (c) => c.compactBottomBar, onClass: "vm-compact-bottom" },
    { key: "searchSuggestions", label: "Search suggestions", hint: "Show DuckDuckGo suggestions in the command bar while you type.", default: true,
      fromConfig: (c) => (c.suggestions === undefined ? undefined : c.suggestions === "ddg") },
  ];

  const resolve = (schema, config, saved) => Object.fromEntries(schema.map((s) => {
    const mine = saved?.[s.key];
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

  const api = { SCHEMA, resolve, classes, vars };
  window.__vm.settings = api;
  if (!window.__vm.store) return;

  const { store, config } = window.__vm;
  const listeners = new Set();
  const channel = new BroadcastChannel("vivarc-settings");
  let saved = {};
  let values = resolve(SCHEMA, config, saved);

  const apply = (browser) => {
    for (const [name, on] of Object.entries(classes(SCHEMA, values))) browser.classList.toggle(name, on);
    for (const [name, value] of Object.entries(vars(SCHEMA, values))) browser.style.setProperty(name, value);
  };
  const update = (next) => {
    saved = next || {};
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
