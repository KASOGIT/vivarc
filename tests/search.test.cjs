const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = name => fs.readFileSync(path.join(__dirname, '../src/js', name), 'utf8');
function setup({ incognito = false, missing = false, suggestUrl = 'https://chosen.test/suggest?q={searchTerms}' } = {}) {
  const calls = { fetch: [], request: [], navigation: [] };
  const normal = { guid: 'chosen', keyword: 'c', name: 'Chosen', url: 'https://chosen.test/?q={searchTerms}', suggestUrl };
  const privateEngine = { ...normal, guid: 'private', suggestUrl: 'https://private.test/suggest?q=%s' };
  const reply = { defaultSearch: missing ? 'missing' : 'chosen', defaultPrivate: 'private', templateUrls: [normal, privateEngine] };
  const context = vm.createContext({
    console: { log() {}, warn() {} }, AbortSignal, URL, navigator: { language: 'fr' },
    window: { __vm: {} },
    chrome: { windows: { getCurrent: async () => ({ incognito, type: "normal", focused: true, id: 1 }) }, tabs: {
      create: async opts => calls.navigation.push(opts), update: async (id, opts) => calls.navigation.push({ id, ...opts }),
      query: async () => [], onCreated: { addListener(fn) { calls.onCreated = fn; } }, onActivated: { addListener(fn) { calls.onActivated = fn; } },
    }, bookmarks: { search: async () => [] }, history: { search: async () => [] } },
    vivaldi: { searchEngines: {
      getTemplateUrls: async () => reply,
      getSearchRequest: async (guid, query) => { calls.request.push({ guid, query }); return { url: `https://${guid}.test/?q=${encodeURIComponent(query)}` }; },
    } },
    fetch: async (url, options) => { calls.fetch.push({ url, options }); return { ok: true, json: async () => ['test', ['test result', ['invalid'], 'test other']] }; },
  });
  vm.runInContext(source('08-search.js'), context);
  return { context, calls, normal, reply, search: context.window.__vm.search };
}
test('uses Vivaldi default GUID and native expansion without chrome.search', async () => {
  const { search, calls } = setup();
  const engine = await search.defaultEngine();
  const request = await search.request(engine, 'été & café');
  assert.equal(request.url, 'https://chosen.test/?q=%C3%A9t%C3%A9%20%26%20caf%C3%A9');
  assert.equal(calls.request[0].guid, 'chosen');
});
test('private windows use the private default; changed defaults are read live', async () => {
  const { search, reply } = setup({ incognito: true });
  assert.equal((await search.defaultEngine()).guid, 'private');
  reply.defaultPrivate = 'chosen';
  assert.equal((await search.defaultEngine()).guid, 'chosen');
});
test('suggestions use the chosen engine and encode the query', async () => {
  const { search, calls } = setup();
  assert.deepEqual(Array.from(await search.suggestions(await search.defaultEngine(), 'été & café')), ['test result', 'test other']);
  assert.equal(calls.fetch[0].url, 'https://chosen.test/suggest?q=%C3%A9t%C3%A9%20%26%20caf%C3%A9');
  assert.equal(calls.fetch[0].options.credentials, 'omit');
});
test('missing Suggest URL makes no network request to another engine', async () => {
  const { search, calls } = setup({ suggestUrl: '' });
  assert.equal((await search.suggestions(await search.defaultEngine(), 'test')).length, 0);
  assert.equal(calls.fetch.length, 0);
});
test('unresolvable default fails explicitly instead of choosing DuckDuckGo', async () => {
  const { search, calls } = setup({ missing: true });
  await assert.rejects(search.defaultEngine(), /default search engine/);
  assert.equal(calls.fetch.length, 0);
});
test('parses OpenSearch and phrase objects and rejects unknown required templates', () => {
  const { search } = setup();
  assert.deepEqual(Array.from(search.phrases([{ phrase: 'one' }, {}, { phrase: 'two' }])), ['one', 'two']);
  assert.equal(search.expand('https://test/?q=%s&encoding={inputEncoding}&optional={unused?}', 'a b'), 'https://test/?q=a%20b&encoding=UTF-8&optional=');
  assert.equal(search.expand('https://test/?q={searchTerms}&x={unknown}', 'test'), null);
});
async function loadBar(context, settingsOpen = false) {
  const nodes = [];
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.value = ''; this.style = {}; }
    append(...items) { this.children.push(...items); }
    replaceChildren(...items) { this.children = items; }
    addEventListener(name, fn) { this.events[name] = fn; }
    remove() {} focus() {} scrollIntoView() {} querySelector() { return null; }
  }
  const browser = new Element('body');
  context.document = { body: browser, querySelector: () => browser, createElement: tag => { const node = new Element(tag); nodes.push(node); return node; } };
  context.setTimeout = () => {};
  context.CustomEvent = class {};
  const events = {};
  Object.assign(context.window, { addEventListener: (name, fn) => events[name] = fn, dispatchEvent() {} });
  Object.assign(context.window.__vm, { config: {}, cssLoaded: true, settings: { get: () => true, isOpen: () => settingsOpen }, normalise: x => x, shortcut: x => x, onShortcut() {} });
  vm.runInContext(source('20-command-bar.js'), context);
  await events['vm-open-command-bar']();
  return nodes.find(node => node.tag === 'input');
}
test('Ctrl+T search and suggestion selection both navigate with the default engine', async () => {
  const { context, calls } = setup();
  const input = await loadBar(context);
  await new Promise(resolve => setImmediate(resolve));
  input.value = 'test query';
  await input.events.input();
  input.events.keydown({ key: 'ArrowDown', preventDefault() {} }); // first suggestion
  input.events.keydown({ key: 'Enter', preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.fetch[0].url, 'https://chosen.test/suggest?q=test%20query');
  assert.equal(calls.request[0].guid, 'chosen');
  assert.equal(calls.request[0].query, 'test result');
  assert.equal(calls.navigation[0].url, 'https://chosen.test/?q=test%20result');
});

test('command bar stays closed while the Vivarc settings overlay is open', async () => {
  const { context, calls } = setup();
  assert.equal(await loadBar(context, true), undefined);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.navigation.length, 0);
  assert.equal(calls.fetch.length, 0);
});

for (const win of [
  { type: 'popup', focused: true },
  { type: 'normal', focused: true, vivExtData: '{"windowType":"settings"}' },
  { type: 'normal', focused: false },
]) {
  test(`command bar ignores non-main windows: ${JSON.stringify(win)}`, async () => {
    const { context } = setup();
    context.chrome.windows.getCurrent = async () => win;
    assert.equal(await loadBar(context), undefined);
  });
}

test('first blank tab of a new workspace never reactivates the previous workspace', async () => {
  const { context, calls } = setup();
  await loadBar(context);
  calls.onActivated({ tabId: 10 });
  context.chrome.tabs.get = async () => ({ id: 10, vivExtData: '{"workspaceId":1}' });
  context.Date = { now: () => Date.now() + 6000 };
  const scheduled = [];
  context.setTimeout = fn => scheduled.push(fn);
  await calls.onCreated({ id: 20, windowId: 1, active: true, url: 'vivaldi://newtab', vivExtData: '{"workspaceId":2}' });
  assert.equal(scheduled.length, 0, 'must not schedule reactivation of the old tab');
  assert.equal(calls.navigation.length, 0);
});
