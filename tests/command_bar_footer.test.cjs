const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));

async function bar({ tabs = [], platform = 'mac' } = {}) {
  const env = setup();
  env.reply.templateUrls = [];
  env.context.chrome.tabs.query = async () => tabs;
  env.context.window.__vm.platform = platform;
  const input = await loadBar(env.context);
  await flush();
  const find = name => env.context.nodes.find(n => n.className === name);
  const box = find('vm-cmd-box');
  const list = find('vm-cmd-list');
  const press = async (key) => { await input.events.keydown({ key, preventDefault() {} }); await flush(); };
  const type = async (text) => {
    await press(text[text.length - 1]);
    input.value = text;
    await input.events.input();
    await flush();
  };
  // Each vm-cmd-key element in the footer, with the text node or element that follows it in its parent.
  const hints = () => {
    const foot = box.children.find(c => c.className === 'vm-cmd-foot');
    assert.ok(foot, 'no vm-cmd-foot in the box');
    const out = [];
    const walk = (node) => (node.children || []).forEach((child, i, siblings) => {
      if (child.className === 'vm-cmd-key') out.push({ keys: child.textContent, label: String(siblings[i + 1]?.textContent ?? '').trim() });
      else walk(child);
    });
    walk(foot);
    return out;
  };
  return { ...env, input, box, list, press, type, hints };
}
// The result comes from the vm context realm: copy it into this realm before deepEqual.
const footerHints = async (row, platform) => JSON.parse(JSON.stringify((await bar()).context.window.__vm.commandBar.footerHints(row, platform)));
const hint = (keys, label) => ({ keys, label });
const tabRow = [{ id: 7, title: 'GitHub', url: 'https://github.com/' }];

test('footerHints lists Enter, Select, Close with the mac keys', async () => {
  assert.deepEqual(await footerHints({ type: 'tab' }, 'mac'), [
    hint('↵', 'Switch to Tab'), hint('↑↓', 'Select'), hint('esc', 'Close'),
  ]);
});

test('footerHints uses the Windows key names on win', async () => {
  assert.deepEqual(await footerHints({ type: 'url' }, 'win'), [
    hint('Enter', 'Open'), hint('↑↓', 'Select'), hint('Esc', 'Close'),
  ]);
});

test('footerHints without a row has no Enter hint', async () => {
  assert.deepEqual(await footerHints(null, 'mac'), [hint('↑↓', 'Select'), hint('esc', 'Close')]);
});

test('footerHints gives a search row with an empty query no Enter hint', async () => {
  assert.deepEqual(await footerHints({ type: 'search', query: '' }, 'mac'), [hint('↑↓', 'Select'), hint('esc', 'Close')]);
});

test('footerHints keeps the Search hint for a search row with a query', async () => {
  assert.deepEqual((await footerHints({ type: 'search', query: 'git' }, 'mac'))[0], hint('↵', 'Search'));
});

test('footerHints names the Enter action after the row type', async () => {
  assert.deepEqual((await footerHints({ type: 'tab' }, 'mac'))[0], hint('↵', 'Switch to Tab'));
  assert.deepEqual((await footerHints({ type: 'action' }, 'mac'))[0], hint('↵', 'Run'));
  assert.deepEqual((await footerHints({ type: 'engine' }, 'mac'))[0], hint('↵', 'Search with'));
  assert.deepEqual((await footerHints({ type: 'search', query: 'x' }, 'mac'))[0], hint('↵', 'Search'));
  assert.deepEqual((await footerHints({ type: 'suggest', query: 'x' }, 'mac'))[0], hint('↵', 'Search'));
  assert.deepEqual((await footerHints({ type: 'bookmark' }, 'mac'))[0], hint('↵', 'Open'));
  assert.deepEqual((await footerHints({ type: 'history' }, 'mac'))[0], hint('↵', 'Open'));
  assert.deepEqual((await footerHints({ type: 'url' }, 'mac'))[0], hint('↵', 'Open'));
});

test('the box has a footer after the list with one vm-cmd-key per hint', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  const names = b.box.children.map(c => c.className);
  assert.ok(names.indexOf('vm-cmd-foot') > names.indexOf('vm-cmd-list'), `box children: ${names}`);
  assert.deepEqual(b.hints(), [
    hint('↵', 'Switch to Tab'), hint('↑↓', 'Select'), hint('esc', 'Close'),
  ]);
});

test('the footer uses the Windows key names when the platform is win', async () => {
  const b = await bar({ tabs: tabRow, platform: 'win' });
  await b.type('git');
  assert.deepEqual(b.hints().map(h => h.keys), ['Enter', '↑↓', 'Esc']);
});

test('the footer Enter hint follows the selected row', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  assert.equal(b.hints()[0].label, 'Switch to Tab');
  await b.press('ArrowDown');
  assert.equal(b.hints()[0].label, 'Search');
});

test('with nothing typed and no rows the list shows the empty state', async () => {
  const b = await bar();
  assert.deepEqual(b.list.children.map(c => c.className), ['vm-cmd-empty']);
  assert.equal(b.list.children[0].textContent, 'Type to search tabs, bookmarks and history, or enter an address.');
});

test('a whitespace-only input with no rows shows the empty state', async () => {
  const b = await bar();
  await b.type('   ');
  assert.deepEqual(b.list.children.map(c => c.className), ['vm-cmd-empty']);
});

test('hovering another row updates the footer Enter label', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  assert.equal(b.hints()[0].label, 'Switch to Tab');
  const searchRow = b.list.children.find(r => r.children.some(c => c.className === 'vm-cmd-title' && c.textContent === 'git'));
  assert.ok(searchRow, 'no search row');
  searchRow.events.mousemove();
  assert.equal(b.hints()[0].label, 'Search');
});

test('the empty state is gone once rows exist', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  assert.ok(b.list.children.length > 0, 'no rows');
  assert.equal(b.list.children.filter(c => c.className === 'vm-cmd-empty').length, 0);
});
