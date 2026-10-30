// The space bar's data: the other Vivaldi profiles as switchable chips. A profile is Arc's "Profile": its own
// logins, cookies and extensions, in its own window.
(() => {
  const hueOf = (name) => {
    let hash = 0;
    for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
    return hash;
  };

  // A single profile needs no switcher. Chips are sorted by name so Cmd+Ctrl+N stays predictable.
  const profileChips = (profiles) => {
    const real = (profiles || []).filter((p) => !p.guest);
    if (real.length < 2) return [];
    return real
      .map((p) => ({
        path: p.path,
        name: p.name,
        active: !!p.active,
        avatar: p.customAvatar || p.image,
        letter: (p.name || "?").trim().charAt(0).toUpperCase() || "?",
        hue: hueOf(p.name || ""),
      }))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
  };

  // Cmd+Ctrl+Left/Right goes to the previous/next profile (wrapping).
  // Cmd+Ctrl+1..9 opens the nth chip, unless it is the profile already open.
  const pathForShortcut = (profiles, combo) => {
    const keys = String(combo).toLowerCase().split("+").map((s) => s.trim()).sort();
    const chips = profileChips(profiles);
    if (keys.length !== 3 || !keys.includes("ctrl") || !keys.includes(window.__vm.windows ? "shift" : "meta")) return null;
    const digit = keys.find((k) => /^[1-9]$/.test(k));
    if (digit) {
      const chip = chips[Number(digit) - 1];
      return chip && !chip.active ? chip.path : null;
    }
    const step = keys.includes("right") ? 1 : keys.includes("left") ? -1 : 0;
    const at = chips.findIndex((c) => c.active);
    if (!step || chips.length < 2 || at === -1) return null;
    return chips[(at + step + chips.length) % chips.length].path;
  };

  const wantsAccountButton = (profiles) => profileChips(profiles).length === 0;

  // With a profile switcher in the bottom bar, Vivaldi's own account button is redundant.
  const withAccountButton = (list, wanted) => {
    if (list.includes("AccountButton") === wanted) return list;
    if (!wanted) return list.filter((item) => item !== "AccountButton");
    const spacer = list.indexOf("FlexibleSpacer");
    return [...list.slice(0, spacer + 1), "AccountButton", ...list.slice(spacer + 1)];
  };

  const withDownloads = (list) => {
    if (list.includes("PanelDownloads")) return list;
    const update = list.indexOf("UpdateButton");
    return update === -1 ? [...list, "PanelDownloads"] : [...list.slice(0, update), "PanelDownloads", ...list.slice(update)];
  };

  // Every profile gets the Downloads button; the account button gives way to the profile chips.
  const syncBottomBar = async (wantAccount) => {
    const read = async (path) => (await vivaldi.prefs.get(path))?.value;
    const path = "vivaldi.toolbars.tabbar_after";
    const list = await read(path);
    if (Array.isArray(list)) {
      const next = withDownloads(withAccountButton(list, wantAccount));
      if (next.join() !== list.join()) await vivaldi.prefs.set({ path, value: next });
      return;
    }
    const whole = await read("vivaldi.toolbars");
    if (!Array.isArray(whole?.tabbar_after)) return;
    const next = withDownloads(withAccountButton(whole.tabbar_after, wantAccount));
    if (next.join() !== whole.tabbar_after.join()) await vivaldi.prefs.set({ path: "vivaldi.toolbars", value: { ...whole, tabbar_after: next } });
  };

  window.__vm.spaces = { profileChips, pathForShortcut, wantsAccountButton, withAccountButton, withDownloads, syncBottomBar };
})();
