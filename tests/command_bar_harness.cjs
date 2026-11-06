const assert = require('node:assert/strict');
const { test } = require('node:test');
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
  context.window.__vm.search = {
    current: () => normal,
    searchUrl: async query => `https://chosen.test/?q=${encodeURIComponent(query)}`,
    suggestUrl: () => null,
    parseSuggestions: () => [],
  };
  return { context, calls, normal, reply, search: context.window.__vm.search };
}
async function loadBar(context, settingsOpen = false, autoOpen = true) {
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
  Object.assign(context.window.__vm, { config: {}, cssLoaded: true, settings: { get: () => true, isOpen: () => settingsOpen }, normalise: x => x, shortcut: x => x, keys: { commandBar: "ctrl+t" }, onShortcut(fn) { context.shortcut = fn; } });
  vm.runInContext(source('20-command-bar.js'), context);
  context.openBar = events['vm-open-command-bar'];
  context.nodes = nodes;
  if (autoOpen) await context.openBar();
  return nodes.find(node => node.tag === 'input');
}

module.exports = { setup, loadBar };
