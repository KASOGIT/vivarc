// Tab stacks (#122): Vivaldi's own tab stacks, which the sidebar shows as a group. Pure helpers, tested.
(() => {
  // The stack a tab belongs to: Vivaldi keeps it in the tab's vivExtData ("group"); "" for a loose tab.
  const groupOf = (tab) => {
    try { return JSON.parse(tab?.vivExtData || "{}").group || ""; } catch (_) { return ""; }
  };
  // A stack's name: Vivaldi's own stack title ("fixedGroupTitle" on its tabs), or "" when it has none.
  const nameOf = (tabs) => {
    for (const t of tabs) { try { const n = JSON.parse(t.vivExtData || "{}").fixedGroupTitle; if (n) return n; } catch (_) {} }
    return "";
  };
  // What the sidebar lists, newest first as for loose tabs: a tab, or a stack where its newest tab would be. A
  // stack's tabs keep their order (oldest first). A "stack" of one tab is shown as a plain tab.
  const layout = (tabs) => {
    const stacks = new Map();
    for (const t of tabs) {
      const id = groupOf(t);
      if (id) stacks.set(id, [...(stacks.get(id) || []), t]);
    }
    const entries = [];
    for (const t of tabs) {
      const id = groupOf(t);
      if (!id || stacks.get(id).length < 2) entries.push({ type: "tab", tab: t, index: t.index });
    }
    for (const [id, members] of stacks) {
      if (members.length < 2) continue;
      const ordered = members.slice().sort((a, b) => a.index - b.index);
      entries.push({ type: "stack", id, tabs: ordered, index: ordered.at(-1).index });
    }
    return entries.sort((a, b) => b.index - a.index);
  };
  // Shift+click: every visible tab between the anchor and the clicked one, both included.
  const range = (order, from, to) => {
    const [a, b] = [order.indexOf(from), order.indexOf(to)].sort((x, y) => x - y);
    return a < 0 || b < 0 ? [to] : order.slice(a, b + 1);
  };
  window.__vm.stacks = { groupOf, nameOf, layout, range };
})();
