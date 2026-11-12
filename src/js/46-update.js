// Vivarc update check: asks GitHub for the latest release now and then, and tells the sidebar (vm-update) when it is newer than this install.
(() => {
  const CHECK_EVERY = 3600 * 1000;
  const LATEST = "https://api.github.com/repos/KASOGIT/vivarc/releases/latest";

  const parse = (version) => (/^\d+(\.\d+)*$/.test(version) ? version.split(".").map(Number) : null);
  const isNewer = (tag, current) => {
    const a = parse(String(tag ?? "").replace(/^v/, ""));
    const b = parse(String(current ?? ""));
    if (!a || !b) return false;
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const diff = (a[i] || 0) - (b[i] || 0);
      if (diff) return diff > 0;
    }
    return false;
  };
  const shouldCheck = (now, lastChecked) => !lastChecked || now - lastChecked >= CHECK_EVERY;
  const pillState = (release, current, dismissedTag) =>
    release && isNewer(release.tag, current) && release.tag !== dismissedTag ? { show: true, tag: release.tag, url: release.url } : { show: false };

  const api = { isNewer, shouldCheck, pillState };
  window.__vm.update = api;
  if (!window.__vm.store) return;

  const { store, config, settings } = window.__vm;
  const channel = new BroadcastChannel("vivarc-update");
  let cache = {};

  const changed = () => window.dispatchEvent(new CustomEvent("vm-update"));
  const save = (next) => { cache = next; store.set("update", cache); channel.postMessage(cache); changed(); };

  const check = async () => {
    if (!settings.get("updateCheck") || !config.version || !shouldCheck(Date.now(), cache.checkedAt)) return;
    try {
      const release = await (await fetch(LATEST)).json();
      if (release.tag_name) save({ ...cache, checkedAt: Date.now(), tag: release.tag_name, url: release.html_url });
    } catch (_) {}
  };

  api.state = () => (settings.get("updateCheck")
    ? pillState(cache.tag && { tag: cache.tag, url: cache.url }, config.version, cache.dismissedTag)
    : { show: false });
  api.dismiss = () => { if (cache.tag) save({ ...cache, dismissedTag: cache.tag }); };

  channel.onmessage = (e) => { cache = e.data || {}; changed(); };
  settings.onChange(() => { changed(); check(); });
  store.get("update", {}).then((saved) => {
    cache = saved;
    changed();
    setTimeout(check, 5000);
    setInterval(check, 5 * 60 * 1000);
  });
})();
