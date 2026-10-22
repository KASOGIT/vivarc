// Vivarc: "Copied Current URL" toast when Vivaldi's Cmd+Shift+C (copy page URL) runs.
(() => {
  const SHARE_SVG =
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M8 8l4-4 4 4"/><path d="M6 12H5a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-1"/></svg>';
  let toast = null;
  let timer = 0;

  const show = (message = "Copied Current URL") => {
    if (!window.__vm.cssLoaded) return;
    toast?.remove();
    clearTimeout(timer);
    toast = document.createElement("div");
    toast.id = "vm-copied";
    const text = document.createElement("span");
    text.textContent = message;
    const icon = document.createElement("span");
    icon.className = "vm-copied-icon";
    icon.innerHTML = SHARE_SVG;
    toast.append(text, icon);
    (document.querySelector("#browser") || document.body).append(toast);
    requestAnimationFrame(() => toast?.classList.add("in"));
    timer = setTimeout(() => {
      toast?.classList.remove("in");
      const gone = toast;
      setTimeout(() => gone?.remove(), 250);
    }, 2200);
  };

  window.addEventListener("vm-toast", (e) => show(e.detail || undefined));
  window.__vm.onShortcut((key) => { if (key === window.__vm.normalise("meta+shift+c")) show(); });
})();
