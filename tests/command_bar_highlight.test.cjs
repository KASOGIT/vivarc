const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));

async function bar({ tabs = [] } = {}) {
  const env = setup();
  env.reply.templateUrls = [];
  env.context.chrome.tabs.query = async () => tabs;
  const input = await loadBar(env.context);
  await flush();
  const list = env.context.nodes.find(n => n.className === 'vm-cmd-list');
  const type = async (text) => {
    await input.events.keydown({ key: text[text.length - 1], preventDefault() {} });
    input.value = text;
    await input.events.input();
    await flush();
  };
  const titles = () => list.children.map(row => row.children.find(c => c.className === 'vm-cmd-title'));
  return { ...env, input, list, type, titles };
}
const highlight = async (label, query) => (await bar()).context.window.__vm.commandBar.highlight(label, query);
const seg = (text, match) => ({ text, match });

test('highlight marks a case-insensitive match and keeps the original casing', async () => {
  assert.deepEqual(await highlight('GitHub', 'git'), [seg('Git', true), seg('Hub', false)]);
});

test('highlight returns the whole label unmarked when nothing matches', async () => {
  assert.deepEqual(await highlight('GitHub', 'xyz'), [seg('GitHub', false)]);
});

test('highlight returns the whole label unmarked for an empty or blank query', async () => {
  assert.deepEqual(await highlight('GitHub', ''), [seg('GitHub', false)]);
  assert.deepEqual(await highlight('GitHub', '   '), [seg('GitHub', false)]);
});

test('highlight marks each word of the query wherever it occurs', async () => {
  assert.deepEqual(await highlight('Open GitHub issues', 'git iss'), [
    seg('Open ', false), seg('Git', true), seg('Hub ', false), seg('iss', true), seg('ues', false),
  ]);
});

test('highlight marks every occurrence of a repeated match', async () => {
  assert.deepEqual(await highlight('abcabc', 'b'), [
    seg('a', false), seg('b', true), seg('ca', false), seg('b', true), seg('c', false),
  ]);
});

test('highlight treats regex characters in the query as literal text', async () => {
  assert.deepEqual(await highlight('a.b (c)', '(c'), [seg('a.b ', false), seg('(c', true), seg(')', false)]);
});

test('a row title is built from text nodes and a vm-cmd-match element for the typed text', async () => {
  const b = await bar({ tabs: [{ id: 7, title: 'GitHub', url: 'https://github.com/' }] });
  await b.type('git');
  const title = b.titles().find(t => t.textContent === 'GitHub');
  assert.ok(title, 'no GitHub row');
  const marks = title.children.filter(c => c.className === 'vm-cmd-match');
  assert.deepEqual(marks.map(m => m.textContent), ['Git']);
  assert.equal(marks[0].tag, 'mark');
  assert.deepEqual(title.children.filter(c => c.className !== 'vm-cmd-match').map(c => c.textContent), ['Hub']);
});

test('a label containing markup stays literal text and creates no element', async () => {
  const b = await bar({ tabs: [{ id: 7, title: 'a <b>x</b> c', url: 'https://example.org/' }] });
  await b.type('b');
  const title = b.titles().find(t => t.textContent === 'a <b>x</b> c');
  assert.ok(title, 'literal label not preserved');
  assert.ok(title.children.some(c => c.className === 'vm-cmd-match'), 'typed text not marked');
  assert.equal(b.context.nodes.filter(n => n.tag === 'b').length, 0);
});

test('the search-for-what-you-typed row is not marked', async () => {
  const b = await bar({ tabs: [{ id: 7, title: 'GitHub', url: 'https://github.com/' }] });
  await b.type('git');
  const searchTitle = b.titles().find(t => t.textContent === 'git');
  assert.ok(searchTitle, 'no search row');
  assert.equal(searchTitle.children.filter(c => c.className === 'vm-cmd-match').length, 0);
});
