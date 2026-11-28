const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/js/01-settings.js'), 'utf8');

const settle = () => new Promise(resolve => setImmediate(resolve));

async function load({ saved = {}, systemReduce = false } = {}) {
  const names = new Set();
  const browser = {
    classList: {
      toggle(name, on) { if (on) names.add(name); else names.delete(name); return !!on; },
      contains: name => names.has(name),
    },
    style: { setProperty() {} },
  };
  const media = {
    matches: systemReduce,
    listeners: [],
    addEventListener(type, fn) { if (type === 'change') this.listeners.push(fn); },
    fire() { this.listeners.forEach(fn => fn({ matches: this.matches })); },
  };
  const storage = {};
  const written = [];
  const context = vm.createContext({
    console: { log() {}, warn() {} },
    document: { querySelector: selector => (selector === '#browser' ? browser : null) },
    localStorage: { getItem: key => storage[key] ?? null, setItem(key, value) { storage[key] = String(value); } },
    BroadcastChannel: class { postMessage() {} },
    matchMedia: query => {
      assert.equal(query, '(prefers-reduced-motion: reduce)');
      return media;
    },
    window: {
      __vm: {
        config: {},
        onMark() {},
        store: { get: async () => saved, set(key, value) { written.push([key, value]); } },
      },
    },
  });
  context.window.matchMedia = context.matchMedia;
  vm.runInContext(source, context);
  await settle();
  return { browser, media, written, settings: context.window.__vm.settings };
}

test('nothing saved, system motion not reduced: full motion, reduce-motion off', async () => {
  const { browser } = await load();
  assert.equal(browser.classList.contains('vm-reduce-motion'), false);
  assert.equal(browser.classList.contains('vm-motion-full'), true);
});

test('nothing saved, system reduces motion: reduce-motion on', async () => {
  const { browser } = await load({ systemReduce: true });
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
});

test('saved reduced motion turns reduce-motion on without the system asking', async () => {
  const { browser } = await load({ saved: { motion: 'reduced' } });
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
  assert.equal(browser.classList.contains('vm-motion-reduced'), true);
  assert.equal(browser.classList.contains('vm-motion-full'), false);
});

test('saved motion off turns reduce-motion and motion-off on', async () => {
  const { browser } = await load({ saved: { motion: 'off' } });
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
  assert.equal(browser.classList.contains('vm-motion-off'), true);
});

test('the system preference changing re-applies reduce-motion both ways', async () => {
  const { browser, media } = await load();
  assert.equal(browser.classList.contains('vm-reduce-motion'), false);
  media.matches = true;
  media.fire();
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
  media.matches = false;
  media.fire();
  assert.equal(browser.classList.contains('vm-reduce-motion'), false);
});

test('the system preference stays on after a saved full motion', async () => {
  const { browser, media } = await load({ saved: { motion: 'full' } });
  media.matches = true;
  media.fire();
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
});

test('setting motion to reduced at runtime turns reduce-motion on and saves it', async () => {
  const { browser, settings, written } = await load();
  assert.equal(browser.classList.contains('vm-reduce-motion'), false);
  settings.set('motion', 'reduced');
  assert.equal(browser.classList.contains('vm-reduce-motion'), true);
  assert.equal(JSON.stringify(written), JSON.stringify([['settings', { motion: 'reduced' }]]));
});

test('saved density and corners add their classes', async () => {
  const { browser } = await load({ saved: { density: 'compact', corners: 'round' } });
  assert.equal(browser.classList.contains('vm-density-compact'), true);
  assert.equal(browser.classList.contains('vm-density-default'), false);
  assert.equal(browser.classList.contains('vm-corners-round'), true);
  assert.equal(browser.classList.contains('vm-corners-default'), false);
});
