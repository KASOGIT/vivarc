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

test('footerHints lists Enter, Select, Complete, Close with the mac keys', async () => {
  assert.deepEqual(await footerHints({ type: 'tab' }, 'mac'), [
    hint('↵', 'Switch to Tab'), hint('↑↓', 'Select'), hint('⇥', 'Complete'), hint('esc', 'Close'),
  ]);
});

test('footerHints uses the Windows key names on win', async () => {
  assert.deepEqual(await footerHints({ type: 'url' }, 'win'), [
    hint('Enter', 'Open'), hint('↑↓', 'Select'), hint('Tab', 'Complete'), hint('Esc', 'Close'),
  ]);
});

test('footerHints without a row has no Enter hint', async () => {
  assert.deepEqual(await footerHints(null, 'mac'), [hint('↑↓', 'Select'), hint('⇥', 'Complete'), hint('esc', 'Close')]);
});

test('footerHints names the Enter action after the row type', async () => {
  const expected = {
    tab: 'Switch to Tab', action: 'Run', engine: 'Search with', search: 'Search', suggest: 'Search',
    bookmark: 'Open', history: 'Open', url: 'Open',
  };
  for (const [type, label] of Object.entries(expected)) {
    assert.deepEqual((await footerHints({ type }, 'mac'))[0], hint('↵', label), type);
  }
});

test('the box has a footer after the list with one vm-cmd-key per hint', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  const names = b.box.children.map(c => c.className);
  assert.ok(names.indexOf('vm-cmd-foot') > names.indexOf('vm-cmd-list'), `box children: ${names}`);
  assert.deepEqual(b.hints(), [
    hint('↵', 'Switch to Tab'), hint('↑↓', 'Select'), hint('⇥', 'Complete'), hint('esc', 'Close'),
  ]);
});

test('the footer uses the Windows key names when the platform is win', async () => {
  const b = await bar({ tabs: tabRow, platform: 'win' });
  await b.type('git');
  assert.deepEqual(b.hints().map(h => h.keys), ['Enter', '↑↓', 'Tab', 'Esc']);
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

test('the empty state is gone once rows exist', async () => {
  const b = await bar({ tabs: tabRow });
  await b.type('git');
  assert.ok(b.list.children.length > 0, 'no rows');
  assert.equal(b.list.children.filter(c => c.className === 'vm-cmd-empty').length, 0);
});
