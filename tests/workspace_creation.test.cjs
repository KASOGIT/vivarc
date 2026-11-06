const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
test('first blank tab of a new workspace does not reactivate the old workspace', async () => {
  const { context, calls } = setup();
  await loadBar(context, false, false);
  calls.onActivated({ tabId: 10 });
  context.chrome.tabs.get = async () => ({ id: 10, vivExtData: '{"workspaceId":1}' });
  context.Date = { now: () => Date.now() + 6000 };
  const scheduled = [];
  context.setTimeout = fn => scheduled.push(fn);
  await calls.onCreated({ id: 20, windowId: 1, active: true, url: 'vivaldi://newtab', vivExtData: '{"workspaceId":2}' });
  assert.equal(scheduled.length, 0);
  assert.equal(context.nodes.filter(n => n.tag === 'input').length, 0);
  assert.equal(calls.navigation.length, 0);
});
