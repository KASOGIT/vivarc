// Order and stepping for the Ctrl+Tab switcher (25-tab-switcher.js): the current tab first, then the others from
// most to least recently used, like Arc. Only the latest few are listed: a tab that is opened or focused takes the
// first place and the oldest drops out.
(() => {
  const SHOWN = 5;

  const order = (tabs) => [...tabs].sort((a, b) => (b.active ? 1 : 0) - (a.active ? 1 : 0) || (b.lastAccessed ?? 0) - (a.lastAccessed ?? 0)).slice(0, SHOWN);

  const step = (index, dir, count) => (index + dir + count) % count;

  // Where the selection lands on the first press: the previous tab going forward, the least recent going back.
  // Null when there is no other tab.
  const first = (dir, count) => (count < 2 ? null : step(0, dir, count));

  window.__vm.recent = { order, step, first };
})();
