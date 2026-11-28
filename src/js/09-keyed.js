(() => {
  // Longest increasing subsequence of `seq`, returned as a Set of indexes into `seq`. Of equally long ones it keeps
  // the one that reaches furthest left, so an earlier row stays put and a later one moves.
  const lis = (values) => {
    const seq = values.map((v) => -v).reverse();
    const tails = [];
    const prevOf = new Array(seq.length).fill(-1);
    seq.forEach((value, i) => {
      let lo = 0;
      let hi = tails.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (seq[tails[mid]] < value) lo = mid + 1;
        else hi = mid;
      }
      if (lo > 0) prevOf[i] = tails[lo - 1];
      tails[lo] = i;
    });
    const keep = new Set();
    for (let i = tails.length ? tails[tails.length - 1] : -1; i >= 0; i = prevOf[i]) keep.add(seq.length - 1 - i);
    return keep;
  };

  // Ops that turn the rows `prev` into `next` (both lists of {key, sig}): removes, then replaces, then inserts
  // and moves walking next. `before` is the key of the first following row that stays put, or null for the end. Kept rows on the
  // longest increasing run of their previous positions stay where they are.
  const plan = (prev, next) => {
    const prevAt = new Map(prev.map((row, i) => [row.key, i]));
    const nextKeys = new Set(next.map((row) => row.key));
    const ops = [];
    prev.forEach((row) => { if (!nextKeys.has(row.key)) ops.push({ op: "remove", key: row.key }); });
    next.forEach((row) => {
      if (prevAt.has(row.key) && prev[prevAt.get(row.key)].sig !== row.sig) ops.push({ op: "replace", key: row.key });
    });
    const kept = next.map((row, i) => i).filter((i) => prevAt.has(next[i].key));
    const stable = lis(kept.map((i) => prevAt.get(next[i].key)));
    const stableAt = new Set([...stable].map((j) => kept[j]));
    // Rows are anchored on a stable one only: a row that moves, or is still to come, is not in place when the op runs.
    const beforeOf = (i) => {
      let j = i + 1;
      while (j < next.length && !stableAt.has(j)) j++;
      return j < next.length ? next[j].key : null;
    };
    next.forEach((row, i) => {
      const before = beforeOf(i);
      if (!prevAt.has(row.key)) ops.push({ op: "insert", key: row.key, before });
      else if (!stableAt.has(i)) ops.push({ op: "move", key: row.key, before });
    });
    return ops;
  };

  window.__vm.keyed = { plan };
})();
