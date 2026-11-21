const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));
test('command bar opens on a normal focused window', async () => {
  const { context } = setup();
  assert.ok(await loadBar(context));
});
for (const win of [
  { type: 'popup', focused: true },
  { type: 'normal', focused: true, vivExtData: '{"windowType":"settings"}' },
  { type: 'normal', focused: false },
]) {
  test(`no command bar in ${JSON.stringify(win)}`, async () => {
    const { context } = setup();
    context.chrome.windows.getCurrent = async () => win;
    assert.equal(await loadBar(context), undefined);
  });
}
test('Vivarc settings overlay blocks the command bar', async () => {
  const { context } = setup();
  assert.equal(await loadBar(context, true), undefined);
});
test('Ctrl+T shortcut also respects window restrictions', async () => {
  const { context } = setup();
  context.chrome.windows.getCurrent = async () => ({ type: 'popup', focused: true });
  await loadBar(context, false, false);
  context.shortcut('ctrl+t');
  await flush();
  assert.equal(context.nodes.filter(n => n.tag === 'input').length, 0);
});
test('tab events from a different window cannot open this command bar', async () => {
  const { context, calls } = setup();
  await loadBar(context, false, false);
  context.Date = { now: () => Date.now() + 6000 };
  await calls.onCreated({ id: 20, windowId: 2, active: true, url: 'vivaldi://newtab' });
  assert.equal(context.nodes.filter(n => n.tag === 'input').length, 0);
});
