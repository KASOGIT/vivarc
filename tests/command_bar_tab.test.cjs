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

test('Tab on an arrowed engine row enters that engine mode', async () => {
  const b = await bar();
  await b.type('gh');
  await b.press('ArrowDown');
  await b.press('ArrowUp');
  assert.equal(b.highlighted(), 'Search GitHub');
  await b.tab();
  assert.equal(b.input.value, '');
  assert.deepEqual(b.chips.children.map(c => c.textContent), ['GitHub']);
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
