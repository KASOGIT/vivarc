const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));

// Opens the bar with only the built-in keywords (the harness engine keyword "c" would collide with typed text).
async function bar({ tabs = [], bookmarks = [], history = [], suggestions = null } = {}) {
  const env = setup();
  env.reply.templateUrls = [];
  env.context.chrome.tabs.query = async () => tabs;
  env.context.chrome.bookmarks.search = async () => bookmarks;
  env.context.chrome.history.search = async () => history;
  if (suggestions) {
    env.search.suggestUrl = () => 'https://chosen.test/suggest?q=x';
    env.search.parseSuggestions = () => suggestions;
    env.context.fetch = async () => ({ ok: true, text: async () => 'body' });
  }
  const input = await loadBar(env.context);
  await flush();
  const list = env.context.nodes.find(n => n.className === 'vm-cmd-list');
  const chips = env.context.nodes.find(n => n.className === 'vm-cmd-chips');
  const press = async (key) => {
    const e = { key, prevented: false, preventDefault() { this.prevented = true; } };
    await input.events.keydown(e);
    await flush();
    return e;
  };
  const type = async (text) => {
    await press(text[text.length - 1]);
    input.value = text;
    await input.events.input();
    await flush();
  };
  const highlighted = () => {
    const row = list.children.find(c => /\bsel\b/.test(c.className));
    return row && row.children.find(c => c.className === 'vm-cmd-title').textContent;
  };
  const arrowTo = async (label) => {
    for (let i = 0; i < 10 && highlighted() !== label; i++) await press('ArrowDown');
    assert.equal(highlighted(), label, 'could not arrow to the row');
  };
  const tab = async () => {
    const e = await press('Tab');
    assert.ok(e.prevented, 'Tab must not leave the input');
  };
  return { ...env, input, list, chips, press, type, highlighted, arrowTo, tab };
}
const atEnd = (input, value) => {
  assert.equal(input.value, value);
  assert.equal(input.selectionStart, value.length);
  assert.equal(input.selectionEnd, value.length);
};

test('Tab accepts the inline completion, keeps the rows, and Enter still switches to the completed tab', async () => {
  const b = await bar({ tabs: [{ id: 7, title: 'Claude', url: 'https://claude.ai/chats' }] });
  await b.type('c');
  assert.equal(b.input.value, 'claude.ai');
  assert.equal(b.input.selectionStart, 1);
  assert.equal(b.input.selectionEnd, 9);
  await b.tab();
  atEnd(b.input, 'claude.ai');
  await b.press('Enter');
  assert.deepEqual(b.calls.navigation, [{ id: 7, active: true }]);
});

test('Tab on an arrowed search suggestion fills it, puts the highlight back on row 0, and Enter searches it', async () => {
  const b = await bar({ suggestions: ['kladsko polsko', 'kladsko mapa'] });
  await b.type('kladsko');
  await b.arrowTo('kladsko polsko');
  await b.tab();
  atEnd(b.input, 'kladsko polsko');
  assert.equal(b.highlighted(), 'kladsko polsko');
  assert.equal(b.list.children.findIndex(c => /\bsel\b/.test(c.className)), 0);
  await b.press('Enter');
  assert.deepEqual(b.calls.navigation, [{ url: 'https://chosen.test/?q=kladsko%20polsko' }]);
});

test('Tab on an arrowed tab row fills its URL', async () => {
  const title = 'Stripe Login | Sign in to the Stripe Dashboard';
  const b = await bar({ tabs: [{ id: 7, title, url: 'https://dashboard.stripe.com/login' }] });
  await b.type('stripe');
  await b.arrowTo(title);
  await b.tab();
  atEnd(b.input, 'https://dashboard.stripe.com/login');
});

test('Tab on an arrowed bookmark row fills its URL', async () => {
  const b = await bar({ bookmarks: [{ title: 'Stripe Docs', url: 'https://docs.stripe.com/api' }] });
  await b.type('stripe');
  await b.arrowTo('Stripe Docs');
  await b.tab();
  atEnd(b.input, 'https://docs.stripe.com/api');
});

test('Tab on an arrowed history row fills its URL', async () => {
  const b = await bar({ history: [{ title: 'Stripe Status', url: 'https://status.stripe.com/' }] });
  await b.type('stripe');
  await b.arrowTo('Stripe Status');
  await b.tab();
  atEnd(b.input, 'https://status.stripe.com/');
});

test('Tab on an arrowed url row fills its label', async () => {
  const b = await bar({ suggestions: ['https://example.org/page', 'example mapa'] });
  await b.type('example');
  await b.arrowTo('https://example.org/page');
  await b.tab();
  atEnd(b.input, 'https://example.org/page');
});

test('Tab on a typed engine keyword with the highlight on row 0 enters engine mode', async () => {
  const b = await bar();
  await b.type('yt');
  await b.tab();
  assert.equal(b.input.value, '');
  assert.deepEqual(b.chips.children.map(c => c.textContent), ['YouTube']);
});

test('Tab with the highlight on row 0 and no completion leaves value and caret alone', async () => {
  const b = await bar();
  await b.type('plainword');
  b.input.setSelectionRange(3, 3);
  await b.tab();
  assert.equal(b.input.value, 'plainword');
  assert.equal(b.input.selectionStart, 3);
  assert.equal(b.input.selectionEnd, 3);
  assert.deepEqual(b.chips.children, []);
});

test('hovering a row is not arrowing: Tab on a typed keyword still enters engine mode', async () => {
  const b = await bar();
  await b.type('yt');
  b.list.children[1].events.mousemove();
  await b.tab();
  assert.deepEqual(b.chips.children.map(c => c.textContent), ['YouTube']);
  assert.equal(b.input.value, '');
});

test('Tab on a typed engine keyword enters engine mode even when a host is inline-completed', async () => {
  const b = await bar({ tabs: [{ id: 7, title: 'GitHub', url: 'https://github.com/x' }] });
  await b.type('g');
  assert.equal(b.input.value, 'github.com');
  assert.equal(b.input.selectionStart, 1);
  assert.equal(b.input.selectionEnd, 10);
  await b.tab();
  assert.deepEqual(b.chips.children.map(c => c.textContent), ['Google']);
  assert.equal(b.input.value, '');
});

test('Tab keeps the picked search row highlighted: Enter searches it instead of opening the first history row', async () => {
  const b = await bar({ history: [{ title: 'Stripe', url: 'https://stripe.com/' }] });
  await b.type('stripe');
  await b.arrowTo('stripe');
  await b.tab();
  await b.press('Enter');
  assert.deepEqual(b.calls.navigation, [{ url: 'https://chosen.test/?q=stripe' }]);
});

test('Tab then Enter on an arrowed open-tab row switches to that tab', async () => {
  const title = 'Stripe Login | Sign in to the Stripe Dashboard';
  const b = await bar({ tabs: [{ id: 7, title, url: 'https://dashboard.stripe.com/login' }] });
  await b.type('stripe');
  await b.arrowTo(title);
  await b.tab();
  assert.equal(b.input.value, 'https://dashboard.stripe.com/login');
  await b.press('Enter');
  assert.deepEqual(b.calls.navigation, [{ id: 7, active: true }]);
});

test('Tab accepts a completion whose tab is not row 0: Enter goes to the completed host, not a search for the typed text', async () => {
  const filler = n => ({ id: n, title: `Alpha ${n}`, url: `https://alpha${n}.test/c` });
  const b = await bar({ tabs: [filler(1), filler(2), filler(3), filler(4), { id: 5, title: 'Claude', url: 'https://claude.ai/chats' }] });
  await b.type('c');
  assert.equal(b.input.value, 'claude.ai');
  await b.tab();
  atEnd(b.input, 'claude.ai');
  await b.press('Enter');
  assert.equal(b.calls.navigation.length, 1);
  assert.ok(['[{"id":5,"active":true}]', '[{"url":"https://claude.ai"}]'].includes(JSON.stringify(b.calls.navigation)),
    `expected the tab 5 switch or a load of https://claude.ai, got ${JSON.stringify(b.calls.navigation)}`);
});

test('Tab leaves a select-all selection (edit mode, Cmd+L) alone', async () => {
  const { context } = setup();
  context.chrome.tabs.query = async () => [{ id: 3, title: 'Example', url: 'https://example.com/a' }];
  await loadBar(context, false, false);
  context.window.__vm.keys.editAddress = 'ctrl+l';
  await context.shortcut('ctrl+l');
  await flush();
  const input = context.nodes.find(n => n.tag === 'input');
  assert.equal(input.value, 'https://example.com/a');
  assert.equal(input.selectionStart, 0);
  assert.equal(input.selectionEnd, 21);
  const e = { key: 'Tab', prevented: false, preventDefault() { this.prevented = true; } };
  await input.events.keydown(e);
  await flush();
  assert.ok(e.prevented);
  assert.equal(input.value, 'https://example.com/a');
  assert.equal(input.selectionStart, 0);
  assert.equal(input.selectionEnd, 21);
});

test('Tab on an arrowed action row leaves value and caret alone', async () => {
  const b = await bar();
  await b.type('history');
  await b.arrowTo('View History');
  b.input.setSelectionRange(3, 3);
  await b.tab();
  assert.equal(b.input.value, 'history');
  assert.equal(b.input.selectionStart, 3);
  assert.equal(b.input.selectionEnd, 3);
});

test('Tab on an arrowed engine row enters that engine mode', async () => {
  const b = await bar();
  await b.type('gh');
  await b.press('ArrowDown');
  await b.press('ArrowUp');
  assert.equal(b.highlighted(), 'Search GitHub');
  await b.tab();
  assert.deepEqual(b.chips.children.map(c => c.textContent), ['GitHub']);
  assert.equal(b.input.value, '');
});

const unawaitedTabEnter = async (b) => {
  const key = k => ({ key: k, preventDefault() {} });
  const pending = [b.input.events.keydown(key('Tab')), b.input.events.keydown(key('Enter'))];
  await Promise.all(pending);
  await flush();
};

test('Tab then Enter without awaiting Tab on an arrowed open-tab row still switches to that tab', async () => {
  const title = 'Stripe Login | Sign in to the Stripe Dashboard';
  const b = await bar({ tabs: [{ id: 7, title, url: 'https://dashboard.stripe.com/login' }] });
  await b.type('stripe');
  await b.arrowTo(title);
  await unawaitedTabEnter(b);
  assert.deepEqual(b.calls.navigation, [{ id: 7, active: true }]);
});

test('Tab then Enter without awaiting Tab on an arrowed search row still searches it', async () => {
  const b = await bar({ history: [{ title: 'Stripe', url: 'https://stripe.com/' }] });
  await b.type('stripe');
  await b.arrowTo('stripe');
  await unawaitedTabEnter(b);
  assert.deepEqual(b.calls.navigation, [{ url: 'https://chosen.test/?q=stripe' }]);
});
