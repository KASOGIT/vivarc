// Vivarc settings page: an overlay with the settings of 01-settings.js grouped in sections. The body scrolls between a
// fixed header and footer, and a setting that depends on another shows only while that one is on.
(() => {
  const { settings } = window.__vm;
  let overlay = null;
  let unsubs = [];

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  const forget = () => { unsubs.forEach((off) => off()); unsubs = []; };
  const close = () => { overlay?.remove(); overlay = null; forget(); };

  const textOf = (item) => {
    const text = el("div", "vm-set-text");
    text.append(el("div", "vm-set-label", item.label));
    if (item.hint) text.append(el("div", "vm-set-hint", item.hint));
    return text;
  };

  const rangeRow = (item) => {
    const line = el("div", "vm-set-row vm-set-range");
    const top = el("div", "vm-set-range-top");
    const value = el("span", "vm-set-value");
    top.append(el("div", "vm-set-label", item.label), value);
    const slider = el("input", "vm-set-slider");
    Object.assign(slider, { type: "range", min: String(item.min), max: String(item.max), step: String(item.step) });
    const ends = el("div", "vm-set-ends");
    ends.append(el("span", null, item.low), el("span", null, item.high));
    const show = () => { value.textContent = `${slider.value}${item.unit || ""}`; };
    slider.value = String(settings.get(item.key));
    slider.addEventListener("input", () => { settings.set(item.key, Number(slider.value)); show(); });
    line.append(top, slider, ends);
    show();
    return line;
  };

  const choiceRow = (item) => {
    const line = el("label", "vm-set-row");
    const select = el("select", "vm-set-select");
    for (const [value, name] of item.options) {
      const option = el("option", null, name ?? `${window.__vm.keyLabel(value)}+click`);
      option.value = value;
      select.append(option);
    }
    select.value = settings.get(item.key);
    select.addEventListener("change", () => settings.set(item.key, select.value));
    line.append(textOf(item), select);
    return line;
  };

  const switchRow = (item) => {
    const line = el("label", "vm-set-row");
    const box = el("input", "vm-set-switch");
    box.type = "checkbox";
    box.checked = !!settings.get(item.key);
    box.addEventListener("change", () => settings.set(item.key, box.checked));
    line.append(textOf(item), box);
    return line;
  };

  const row = (item) => {
    const line = item.type === "range" ? rangeRow(item) : item.type === "choice" ? choiceRow(item) : switchRow(item);
    if (item.needs) {
      line.classList.add("vm-set-sub");
      const sync = () => { line.hidden = !settings.get(item.needs); };
      unsubs.push(settings.onChange(sync));
      sync();
    }
    return line;
  };

  const sections = () => settings.sections(settings.SCHEMA, window.__vm.config).map(({ title, items }) => {
    const section = el("section", "vm-set-section");
    const group = el("div", "vm-set-group");
    group.append(...items.map(row));
    section.append(el("div", "vm-set-section-title", title), group);
    return section;
  });

  const open = () => {
    if (!window.__vm.cssLoaded) return;
    if (overlay) return close();
    overlay = el("div", "vm-set-overlay");
    const card = el("div", "vm-set-card");
    const head = el("div", "vm-set-head");
    const x = el("button", "vm-set-close", "✕");
    x.addEventListener("click", close);
    head.append(el("div", "vm-set-title", "Vivarc Settings"), x);
    const body = el("div", "vm-set-body");
    body.append(...sections());
    const reset = el("button", "vm-set-reset", "Reset to defaults");
    reset.addEventListener("click", () => { settings.reset(); forget(); body.replaceChildren(...sections()); });
    const foot = el("div", "vm-set-foot");
    foot.append(el("div", "vm-set-note", "Saved for this profile."), reset);
    card.append(head, body, foot);
    overlay.append(card);
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
    (document.querySelector("#browser") || document.body).append(overlay);
  };

  window.__vm.onShortcut((key) => { if (key === "esc") close(); });
  window.addEventListener("vm-open-settings", open);
})();
