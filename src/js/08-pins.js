// Which tab belongs to which pin or favorite. Like Arc, a tab stays on its pin when it navigates elsewhere.
// The link is kept in the tab's vivExtData JSON (Vivaldi saves it with the session), next to Vivaldi's own keys:
// vivarcPin = the bookmark id, vivarcHome = where the pin landed after its redirects (so a site that
// redirects off its root is not shown as "away" the moment it opens).
(() => {
  const PIN = "vivarcPin";
  const HOME = "vivarcHome";

  const read = (tab) => {
    try { return JSON.parse(tab?.vivExtData || "{}") || {}; } catch (_) { return {}; }
  };
  const pinOf = (tab) => read(tab)[PIN];
  const homeOf = (tab) => read(tab)[HOME];

  // A patch value of undefined removes the key.
  const patched = (tab, patch) => JSON.stringify({ ...read(tab), ...patch });
  const needsWrite = (tab, patch) => {
    const current = read(tab);
    return Object.keys(patch).some((k) => (current[k] === undefined ? undefined : current[k]) !== patch[k]);
  };

  const sameSite = (tabUrl, url) => {
    try {
      const a = new URL(tabUrl), b = new URL(url);
      if (a.origin !== b.origin) return false;
      return b.pathname.length > 1 ? a.pathname.startsWith(b.pathname) : a.pathname === "/";
    } catch (_) { return false; }
  };

  const pathLength = (url) => {
    try { return new URL(url).pathname.length; } catch (_) { return 0; }
  };

  const norm = (url) => {
    try {
      const u = new URL(url);
      return u.origin + u.pathname.replace(/\/+$/, "") + u.search;
    } catch (_) { return url || ""; }
  };

  const away = (tab, pinUrl) => {
    const here = norm(tab.url);
    return here !== norm(pinUrl) && here !== homeOf(tab);
  };

  // pins: [{ id, url }]. Returns which tab each pin owns, and the vivExtData patches that make it so.
  const plan = (tabs, pins) => {
    const bound = new Map();
    const writes = [];
    if (!pins.length) return { bound, writes };
    const known = new Set(pins.map((p) => p.id));
    const claimed = new Set();

    for (const tab of [...tabs].sort((a, b) => a.index - b.index)) {
      const id = pinOf(tab);
      if (id === undefined) continue;
      if (known.has(id) && !bound.has(id)) {
        bound.set(id, tab);
        claimed.add(tab.id);
      } else {
        writes.push({ tabId: tab.id, patch: { [PIN]: undefined, [HOME]: undefined } });
      }
    }

    for (const tab of [...tabs].sort((a, b) => (b.active - a.active) || (a.index - b.index))) {
      if (claimed.has(tab.id) || pinOf(tab) !== undefined) continue;
      let best = null;
      for (const pin of pins) {
        if (bound.has(pin.id) || !sameSite(tab.url, pin.url)) continue;
        if (!best || pathLength(pin.url) > pathLength(best.url)) best = pin;
      }
      if (!best) continue;
      bound.set(best.id, tab);
      writes.push({ tabId: tab.id, patch: { [PIN]: best.id, ...(tab.status === "complete" ? { [HOME]: norm(tab.url) } : {}) } });
    }
    return { bound, writes };
  };

  window.__vm.pins = { PIN, HOME, pinOf, homeOf, patched, needsWrite, sameSite, norm, away, plan };
})();
