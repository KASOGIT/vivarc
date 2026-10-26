// Vivarc settings page: an overlay with one switch per setting (see 01-settings.js).
(() => {
  const { settings } = window.__vm;
  let overlay = null;

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  };

  const close = () => { overlay?.remove(); overlay = null; };

  const row = (item) => {
    const line = el("label", "vm-set-row");
    const text = el("div", "vm-set-text");
    text.append(el("div", "vm-set-label", item.label), el("div", "vm-set-hint", item.hint));
    const box = el("input", "vm-set-switch");
    box.type = "checkbox";
    box.checked = !!settings.get(item.key);
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
    reset.addEventListener("click", () => { settings.reset(); card.replaceChildren(head, ...settings.SCHEMA.map(row), foot); });
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
