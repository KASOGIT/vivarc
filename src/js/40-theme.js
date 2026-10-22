// Vivarc theme editor: tints the sidebar with a colour, shade and grain, saved per profile.
(() => {
  const { store } = window.__vm;
  const PRESETS = [
    ["#efe9e4", 30, 20, 90], ["#e89bbb", 335, 55, 75], ["#a0739f", 305, 25, 54], ["#e0626e", 355, 65, 62],
    ["#ef8c5f", 18, 80, 65], ["#f2d56b", 47, 85, 68], ["#6fe3a0", 143, 65, 65], ["#7db7dc", 203, 55, 67], ["#6d6a92", 245, 18, 48],
  ];
  const DEFAULT = { on: false, hue: 250, sat: 28, light: 20, grain: 30 };
  let theme = { ...DEFAULT };
  let pop = null;

  const fgFor = (light) => (light > 58 ? "#1b1b1f" : "#f2f2f5");
  const noise = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";

  const apply = () => {
    const browser = document.querySelector("#browser");
    if (!browser) return;
    browser.classList.toggle("vm-themed", theme.on);
    const style = browser.style;
    if (!theme.on) {
      for (const k of ["--vm-tint", "--vm-fg", "--vm-grain", "--vm-noise"]) style.removeProperty(k);
      return;
    }
    style.setProperty("--vm-tint", `hsl(${theme.hue} ${theme.sat}% ${theme.light}%)`);
    style.setProperty("--vm-fg", fgFor(theme.light));
    style.setProperty("--vm-grain", String(theme.grain / 100 * 0.35));
    style.setProperty("--vm-noise", noise);
  };

  const save = () => { apply(); store.set("theme", theme); };

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  const close = () => { pop?.remove(); pop = null; };

  const open = () => {
    if (!window.__vm.cssLoaded) return;
    if (pop) return close();
    if (!theme.on) { theme = { ...theme, on: true }; save(); }
    pop = el("div", "vm-theme-pop");

    const modes = el("div", "vm-theme-modes");
    for (const [label, light] of [["Dark", 18], ["Light", 88]]) {
      const b = el("button", "vm-theme-mode", label);
      b.addEventListener("click", () => { theme.light = light; save(); sync(); });
      modes.append(b);
    }

    const pad = el("div", "vm-theme-pad");
    const dot = el("div", "vm-theme-dot");
    pad.append(dot);
    const stops = [0, 60, 120, 180, 240, 300, 360].map((h) => `hsl(${h} 70% 50%)`).join(",");
    pad.style.background = `linear-gradient(to bottom, hsla(0,0%,100%,.75), transparent 45%, hsla(0,0%,0%,.8)), linear-gradient(to right, ${stops})`;
    const place = (e) => {
      const r = pad.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      theme.hue = Math.round(x * 360);
      theme.light = Math.round(90 - y * 80);
      save();
      sync();
    };
    pad.addEventListener("pointerdown", (e) => {
      pad.setPointerCapture(e.pointerId);
      place(e);
      const move = (ev) => place(ev);
      pad.addEventListener("pointermove", move);
      pad.addEventListener("pointerup", () => pad.removeEventListener("pointermove", move), { once: true });
    });

    const swatches = el("div", "vm-theme-swatches");
    for (const [color, hue, sat, light] of PRESETS) {
      const s = el("button", "vm-theme-swatch");
      s.style.backgroundColor = color;
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

    const reset = el("button", "vm-theme-reset", "Reset");
    reset.addEventListener("click", () => { theme = { ...DEFAULT }; save(); close(); });

    const sync = () => {
      dot.style.left = `${theme.hue / 360 * 100}%`;
      dot.style.top = `${(90 - theme.light) / 80 * 100}%`;
      intensity.input.value = String(theme.sat);
      grain.input.value = String(theme.grain);
    };
    sync();

    pop.append(modes, pad, swatches, intensity.row, grain.row, reset);
    (document.querySelector("#browser") || document.body).append(pop);
  };

  const outside = (e) => { if (pop && !pop.contains(e.target)) close(); };
  document.addEventListener("mousedown", outside, true);
  document.addEventListener("focusin", outside, true);
  window.__vm.onShortcut((key) => { if (key === "esc") close(); });
  window.addEventListener("vm-open-theme", open);

  window.__vm.onMark(apply);
  store.get("theme", null).then((saved) => {
    if (saved) theme = { ...DEFAULT, ...saved };
    apply();
  });
})();
