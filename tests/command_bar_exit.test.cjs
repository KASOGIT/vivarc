const { test } = require('node:test');
const assert = require('node:assert/strict');
const { setup, loadBar } = require('./command_bar_harness.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));

test('closing the bar hands the old element to leave instead of removing it, and the bar reopens at once', async () => {
  const env = setup();
  env.reply.templateUrls = [];
  const input = await loadBar(env.context, false, false);
  const leaves = [];
  env.context.window.__vm.leave = node => leaves.push(node);
  await env.context.openBar();
  await flush();
  const bars = () => env.context.nodes.filter(n => n.id === 'vm-cmd');
  assert.equal(bars().length, 1);
  const first = bars()[0];
  let removed = 0;
  first.remove = () => { removed++; };

  const field = env.context.nodes.find(n => n.tag === 'input');
  await field.events.keydown({ key: 'Escape', preventDefault() {} });
  await flush();
  assert.deepEqual(leaves, [first], 'leave called once with the old bar');
  assert.equal(removed, 0, 'the bar is not removed synchronously');

  await env.context.openBar();
  await flush();
  assert.equal(bars().length, 2, 'a new bar is built right away');
  assert.notEqual(bars()[1], first);
});
