// Arc's auto-archive: a tab left unopened for the chosen number of hours is closed. Only unpinned tabs of this
// window; every window runs its own copy of the mod, so each looks after its own tabs.
(() => {
  const HOUR = 3600 * 1000;
  const EVERY = 60 * 1000;

  // keep(tab): extra tabs to spare (bound to a pin or favorite, in a split view). A tab with no last-access time is
  // spared rather than guessed at.
  const stale = (tabs, now, hours, keep) => tabs.filter((t) => !t.active && !t.pinned && !t.audible && !keep(t) &&
    t.lastAccessed != null && now - t.lastAccessed > hours * HOUR);

  window.__vm.archive = { stale };
  if (!window.__vm.store) return;

  const { settings, pins, tilingOf } = window.__vm;
  const keep = (tab) => pins.pinOf(tab) !== undefined || !!tilingOf(tab);

  const sweep = async () => {
    if (!settings.get("archive")) return;
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const ids = stale(tabs, Date.now(), settings.get("archiveHours"), keep).map((t) => t.id);
    if (ids.length) chrome.tabs.remove(ids);
  };

  window.__vm.ready.then((ok) => {
    if (!ok) return;
    setInterval(sweep, EVERY);
  });
})();
