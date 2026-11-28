// Vivarc theme editor: each space has its own tint, shade and grain, saved in the profile.
(() => {
  const { store } = window.__vm;
  // Colours are picked in OKLCH, a light row at L 0.86 and a deep row at L 0.56, and saved as their HSL equivalent so stored themes keep their format.
  const PRESETS = [
    ["Paper", "oklch(0.86 0.008 80)", 37, 9, 81], ["Rose", "oklch(0.86 0.07 15)", 357, 90, 87],
    ["Amber", "oklch(0.86 0.08 70)", 32, 80, 77], ["Mint", "oklch(0.86 0.08 150)", 131, 46, 78],
    ["Sky", "oklch(0.86 0.07 235)", 203, 87, 81], ["Lilac", "oklch(0.86 0.07 305)", 266, 74, 87],
    ["Graphite", "oklch(0.56 0.02 270)", 224, 7, 47], ["Ruby", "oklch(0.56 0.13 15)", 353, 40, 51],
    ["Ochre", "oklch(0.56 0.12 65)", 34, 81, 35], ["Forest", "oklch(0.56 0.11 150)", 136, 37, 38],
    ["Ocean", "oklch(0.56 0.11 245)", 206, 55, 45], ["Violet", "oklch(0.56 0.12 305)", 269, 32, 53],
  ];
  const DEFAULT = { on: false, hue: 250, sat: 28, light: 20, grain: 30 };
  let theme = { ...DEFAULT };
  let pop = null;
  let activeSpace = null;
  let revision = 0;
  let pending = Promise.resolve();
  const keyFor = (id) => `theme:space:${id}`;
  const updates = typeof BroadcastChannel === "function" ? new BroadcastChannel("vivarc-space-themes") : null;

  const fgFor = (light) => (light > 58 ? "#1b1b1f" : "#f2f2f5");
  const noise = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";

  const validStops = (stops) => Array.isArray(stops) && stops.length >= 1 && stops.length <= 2
    && stops.every((s) => s && Number.isInteger(s.hue) && s.hue >= 0 && s.hue <= 359 && Number.isInteger(s.light) && s.light >= 10 && s.light <= 90)
    ? stops : null;

  const scheme = window.matchMedia("(prefers-color-scheme: dark)");
  // In auto mode a saved light is its dark side (10 to 41): a dark system renders it, a light system renders its complement.
  const darkSide = (light) => Math.min(41, Math.max(10, Math.min(light, 100 - light)));
  const renderedLight = (light) => {
    if (theme.mode !== "auto") return light;
    return scheme.matches ? darkSide(light) : 100 - darkSide(light);
  };
  const shownLight = (light, main = theme.light) => (main > 58 ? Math.max(light, 59) : Math.min(light, 58));

  let fadeTimer = null;

  const apply = (options) => {
    const browser = document.querySelector("#browser");
    if (!browser) return;
    clearTimeout(fadeTimer);
    if (options?.fade === true) {
      browser.classList.add("vm-tint-fade");
      fadeTimer = setTimeout(() => browser.classList.remove("vm-tint-fade"), 300);
    } else {
      browser.classList.remove("vm-tint-fade");
    }
    browser.classList.toggle("vm-themed", theme.on);
    browser.classList.toggle("vm-tint-neutral", theme.on && theme.sat < 10);
    const style = browser.style;
    if (!theme.on) {
      for (const k of ["--vm-tint", "--vm-fg", "--vm-grain", "--vm-noise", "--vm-grad", "--vm-grad-glass"]) style.removeProperty(k);
      return;
    }
    const light = renderedLight(theme.light);
    style.setProperty("--vm-tint", `hsl(${theme.hue} ${theme.sat}% ${light}%)`);
    const custom = validStops(theme.stops);
    if (custom) {
      const gradient = (alpha) => `linear-gradient(160deg, ${[theme, ...custom].map((c) => `hsl(${c.hue} ${theme.sat}% ${c === theme ? light : shownLight(renderedLight(c.light), light)}%${alpha})`).join(", ")})`;
      style.setProperty("--vm-grad", gradient(""));
      style.setProperty("--vm-grad-glass", gradient(" / var(--vm-glass-opacity)"));
    } else {
      style.removeProperty("--vm-grad");
      style.removeProperty("--vm-grad-glass");
    }
    style.setProperty("--vm-fg", fgFor(light));
    style.setProperty("--vm-grain", String(theme.grain / 100 * 0.35));
    style.setProperty("--vm-noise", noise);
  };

  const save = () => {
    apply();
    if (activeSpace === null) return;
    const saved = { ...theme };
    store.set(keyFor(activeSpace), saved);
    updates?.postMessage({ space: activeSpace, theme: saved });
  };

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  let shield = null; // catches a click on the page, which this document never sees (see the sidebar's menu)
  let refresh = null;
  const close = () => { window.__vm.leave(pop); pop = null; refresh = null; shield?.remove(); shield = null; };

  const open = async () => {
    if (!window.__vm.cssLoaded) return;
    if (pop) return close();
    const space = activeSpace;
    await pending;
    if (space !== activeSpace || activeSpace === null) return;
    if (!theme.on) { theme = { ...theme, on: true }; save(); }
    pop = el("div", "vm-theme-pop");
    const heading = el("div", "vm-theme-heading", "Theme for this space");

    const modes = el("div", "vm-theme-modes");
    const modeButtons = [];
    for (const [label, light] of [["Dark", 18], ["Light", 88]]) {
      const b = el("button", "vm-theme-mode", label);
      b.addEventListener("click", () => { theme.light = light; delete theme.mode; save(); sync(); });
      modeButtons.push(b);
    }
    const autoModeBtn = el("button", "vm-theme-mode", "Auto");
    autoModeBtn.addEventListener("click", () => {
      theme.mode = "auto";
      theme.light = darkSide(theme.light);
      if (validStops(theme.stops)) theme.stops = theme.stops.map((stop) => ({ ...stop, light: darkSide(stop.light) }));
      save();
      sync();
    });
    modes.append(...modeButtons, autoModeBtn);

    const grad = el("div", "vm-theme-grad");
    const autoBtn = el("button", "vm-theme-mode", "Auto");
    const customBtn = el("button", "vm-theme-mode", "Custom");
    const addBtn = el("button", "vm-theme-mode vm-theme-stop-btn", "+");
    addBtn.title = "Add a colour";
    const removeBtn = el("button", "vm-theme-mode vm-theme-stop-btn", "\u2212");
    removeBtn.title = "Remove a colour";
    autoBtn.addEventListener("click", () => { delete theme.stops; save(); sync(); });
    customBtn.addEventListener("click", () => {
      if (validStops(theme.stops)) return;
      theme.stops = [{ hue: (theme.hue + 40) % 360, light: theme.light }];
      save();
      sync();
    });
    addBtn.addEventListener("click", () => {
      const last = theme.stops[theme.stops.length - 1];
      theme.stops = [...theme.stops, { hue: (last.hue + 40) % 360, light: last.light }];
      save();
      sync();
    });
    removeBtn.addEventListener("click", () => { theme.stops = theme.stops.slice(0, -1); save(); sync(); });
    grad.append(el("span", "vm-theme-grad-label", "Gradient"), autoBtn, customBtn, addBtn, removeBtn);
    const gradientOn = !!document.querySelector("#browser")?.classList.contains("vm-gradient");

    const pad = el("div", "vm-theme-pad");
    const dot = el("div", "vm-theme-dot");
    const stopDots = [el("div", "vm-theme-dot vm-theme-dot-stop"), el("div", "vm-theme-dot vm-theme-dot-stop")];
    pad.append(dot, ...stopDots);
    const stops = [0, 60, 120, 180, 240, 300, 360].map((h) => `hsl(${h} 70% 50%)`).join(",");
    pad.style.background = `linear-gradient(to bottom, hsla(0,0%,100%,.75), transparent 45%, hsla(0,0%,0%,.8)), linear-gradient(to right, ${stops})`;
    const fraction = (e) => {
      const r = pad.getBoundingClientRect();
      return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
    };
    const nearest = (e) => {
      const [x, y] = fraction(e);
      const r = pad.getBoundingClientRect();
      const main = renderedLight(theme.light);
      const targets = [theme, ...(validStops(theme.stops) || [])];
      let best = 0;
      let bestDist = Infinity;
      targets.forEach((t, i) => {
        const d = Math.hypot((t.hue / 360 - x) * r.width, ((90 - (i ? shownLight(renderedLight(t.light), main) : main)) / 80 - y) * r.height);
        if (d < bestDist) { bestDist = d; best = i; }
      });
      return best;
    };
    const place = (e, index) => {
      if (!pop) return;
      const [x, y] = fraction(e);
      const target = index === 0 ? theme : theme.stops?.[index - 1];
      if (!target) return;
      target.hue = Math.min(359, Math.round(x * 360));
      const light = Math.round(90 - y * 80);
      if (theme.mode !== "auto") target.light = light;
      else if (scheme.matches) target.light = Math.min(41, Math.max(10, light));
      else target.light = 100 - Math.min(90, Math.max(59, light));
      save();
      sync();
    };
    pad.addEventListener("pointerdown", (e) => {
      pad.setPointerCapture(e.pointerId);
      const index = nearest(e);
      place(e, index);
      const move = (ev) => place(ev, index);
      const stop = () => {
        pad.removeEventListener("pointermove", move);
        pad.removeEventListener("pointerup", stop);
        pad.removeEventListener("pointercancel", stop);
      };
      pad.addEventListener("pointermove", move);
      pad.addEventListener("pointerup", stop);
      pad.addEventListener("pointercancel", stop);
    });

    const swatches = el("div", "vm-theme-swatches");
    for (const [name, color, hue, sat, light] of PRESETS) {
      const s = el("button", "vm-theme-swatch");
      s.style.backgroundColor = color;
      s.title = name;
      s.addEventListener("click", () => { Object.assign(theme, { hue, sat, light }); save(); sync(); });
      swatches.append(s);
    }

    const slider = (label, key) => {
      const row = el("label", "vm-theme-slider");
      row.append(el("span", null, label));
      const input = el("input");
      input.type = "range";
      input.min = "0";
      input.max = "100";
      input.addEventListener("input", () => { theme[key] = Number(input.value); save(); });
      row.append(input);
      return { row, input };
    };
    const intensity = slider("Intensity", "sat");
    const grain = slider("Grain", "grain");

    const reset = el("button", "vm-theme-reset", "Reset space theme");
    reset.addEventListener("click", () => { theme = { ...DEFAULT }; save(); close(); });

    const sync = () => {
      const custom = validStops(theme.stops) || [];
      const position = (d, c) => { d.style.left = `${c.hue / 360 * 100}%`; d.style.top = `${(90 - c.light) / 80 * 100}%`; };
      const main = renderedLight(theme.light);
      position(dot, { hue: theme.hue, light: main });
      const auto = theme.mode === "auto";
      modeButtons[0].ariaPressed = String(!auto && theme.light <= 58);
      modeButtons[1].ariaPressed = String(!auto && theme.light > 58);
      autoModeBtn.ariaPressed = String(auto);
      stopDots.forEach((d, i) => {
        d.hidden = !custom[i];
        if (custom[i]) position(d, { hue: custom[i].hue, light: shownLight(renderedLight(custom[i].light), main) });
      });
      autoBtn.ariaPressed = String(!custom.length);
      customBtn.ariaPressed = String(custom.length > 0);
      addBtn.hidden = custom.length !== 1;
      removeBtn.hidden = custom.length !== 2;
      intensity.input.value = String(theme.sat);
      grain.input.value = String(theme.grain);
    };
    sync();
    refresh = sync;

    pop.append(heading, modes, pad, swatches, ...(gradientOn ? [grad] : []), intensity.row, grain.row, reset);
    shield = el("div", "vm-menu-shield");
    shield.addEventListener?.("mousedown", (e) => { e.preventDefault(); close(); });
    (document.querySelector("#browser") || document.body).append(shield, pop);
  };

  const outside = (e) => { if (pop && !pop.contains(e.target)) close(); };
  document.addEventListener("mousedown", outside, true);
  document.addEventListener("focusin", outside, true);
  window.__vm.onShortcut((key) => { if (key === "esc") close(); });
  window.addEventListener("vm-open-theme", open);

  const selectSpace = (id) => {
    if (id === activeSpace) return;
    close();
    const fade = theme.on && activeSpace !== null && !validStops(theme.stops);
    activeSpace = id;
    const current = ++revision;
    pending = Promise.all([store.get(keyFor(id), null), store.get("theme", null)]).then(([saved, legacy]) => {
      if (current !== revision) return;
      theme = { ...DEFAULT, ...(saved || legacy || {}) };
      apply({ fade: fade && theme.on && !validStops(theme.stops) });
    });
  };
  window.addEventListener("vm-active-space-changed", (event) => selectSpace(event.detail));
  if (updates) updates.onmessage = ({ data }) => {
    if (data?.space !== activeSpace || !data.theme) return;
    revision++;
    theme = { ...DEFAULT, ...data.theme };
    close();
    apply();
  };

  scheme.addEventListener("change", () => { apply(); refresh?.(); });
  window.__vm.onMark(apply);
  if (window.__vm.activeSpace !== undefined) selectSpace(window.__vm.activeSpace);
})();
