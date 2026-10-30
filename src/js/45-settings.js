// Vivarc settings page: an overlay with one switch per setting (see 01-settings.js).
(() => {
  const { settings } = window.__vm;
  let overlay = null;
  settings.isOpen = () => !!overlay;
  let unsubs = [];

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  const close = () => { overlay?.remove(); overlay = null; unsubs.forEach((off) => off()); unsubs = []; };

  const rangeRow = (item) => {
    const line = el("div", "vm-set-row vm-set-range");
    const text = el("div", "vm-set-text");
    const value = el("span", "vm-set-value");
    const top = el("div", "vm-set-label", item.label + " ");
    top.append(value);
    const slider = el("input", "vm-set-slider");
    slider.type = "range";
    slider.min = String(item.min);
    slider.max = String(item.max);
    slider.step = String(item.step);
    const ends = el("div", "vm-set-ends");
    ends.append(el("span", null, item.low), el("span", null, item.high));
    const show = () => { value.textContent = `${slider.value}${item.unit || ""}`; };
    const sync = () => {
      slider.value = String(settings.get(item.key));
      slider.disabled = !!item.needs && !settings.get(item.needs);
      line.classList.toggle("dim", slider.disabled);
      show();
    };
    slider.addEventListener("input", () => { settings.set(item.key, Number(slider.value)); show(); });
    unsubs.push(settings.onChange(sync));
    text.append(top, el("div", "vm-set-hint", item.hint), slider, ends);
    line.append(text);
    sync();
    return line;
  };

  const row = (item) => {
    if (item.type === "range") return rangeRow(item);
    const line = el("label", "vm-set-row");
    const text = el("div", "vm-set-text");
    text.append(el("div", "vm-set-label", item.label), el("div", "vm-set-hint", item.hint));
    const box = el("input", "vm-set-switch");
    box.type = "checkbox";
    box.checked = !!settings.get(item.key);
    unsubs.push(settings.onChange(() => { box.checked = !!settings.get(item.key); }));
    box.addEventListener("change", () => settings.set(item.key, box.checked));
    line.append(text, box);
    return line;
  };

  const open = () => {
    if (!window.__vm.cssLoaded) return;
    if (overlay) return close();
    overlay = el("div", "vm-set-overlay");
    const card = el("div", "vm-set-card");
    const head = el("div", "vm-set-head");
    const x = el("button", "vm-set-close", "✕");
    x.addEventListener("click", close);
    head.append(el("div", "vm-set-title", "Vivarc Settings"), x);
    const reset = el("button", "vm-set-reset", "Reset to defaults");
    reset.addEventListener("click", () => { unsubs.forEach((off) => off()); unsubs = []; settings.reset(); card.replaceChildren(head, ...settings.SCHEMA.map(row), foot); });
    const foot = el("div", "vm-set-foot");
    foot.append(el("div", "vm-set-note", "Saved for this profile."), reset);
    card.append(head, ...settings.SCHEMA.map(row), foot);
    overlay.append(card);
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
    (document.querySelector("#browser") || document.body).append(overlay);
  };

  window.__vm.onShortcut((key) => { if (key === "esc") close(); });
  window.addEventListener("vm-open-settings", open);
})();
