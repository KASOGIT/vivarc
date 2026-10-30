// Vivaldi's UI exposes its search engines directly; chrome.search is an extension API
// and is not reliably available in this context. Keep search and suggestions on one engine.
(() => {
  const api = () => vivaldi.searchEngines;
  const templates = async () => {
    const reply = await api().getTemplateUrls();
    return { reply, engines: Array.isArray(reply) ? reply : reply.templateUrls || [] };
  };
  const defaultEngine = async () => {
    const [{ reply, engines }, win] = await Promise.all([templates(), chrome.windows.getCurrent()]);
    const guid = win.incognito ? reply.defaultPrivate : reply.defaultSearch;
    const engine = engines.find((item) => item.guid === guid);
    if (!engine) throw new Error('Vivaldi did not expose the default search engine.');
    return engine;
  };
  // Only expand known template parameters. Unknown required parameters must never
  // produce a malformed URL or send the query to a different provider.
  const expand = (template, query) => {
    if (!template) return null;
    let unknown = false;
    const value = template.replace(/\{([^}]+)\}|%s/g, (token, key) => {
      if (token === '%s' || key === 'searchTerms') return encodeURIComponent(query);
      if (key === 'inputEncoding' || key === 'outputEncoding') return 'UTF-8';
      if (key === 'language') return encodeURIComponent(globalThis.navigator?.language || 'en');
      if (key?.endsWith('?')) return '';
      unknown = true;
      return '';
    });
    return !unknown && /^https?:\/\//i.test(value) ? value : null;
  };
  const request = async (engine, query) => {
    if (engine.guid) {
      // Native expansion also handles provider-specific placeholders and POST engines.
      return api().getSearchRequest(engine.guid, query);
    }
    const url = expand(engine.url, query);
    if (!url) throw new Error('Unsupported search URL template.');
    return { url };
  };
  const phrases = (data) => {
    const values = Array.isArray(data?.[1]) ? data[1] : Array.isArray(data) ? data : data?.suggestions || [];
    return values.map((value) => typeof value === 'string' ? value : value?.phrase || value?.value)
      .filter((value) => typeof value === 'string' && value.trim());
  };
  const suggestions = async (engine, query) => {
    // Vivaldi no longer supports Suggest POST Parameters. Do not silently use GET.
    if (engine.suggestPostParams) return [];
    const url = expand(engine.suggestUrl, query);
    if (!url) return [];
    const response = await fetch(url, { credentials: 'omit', signal: AbortSignal.timeout(2500) });
    if (!response.ok) return [];
    return phrases(await response.json());
  };
  window.__vm.search = { templates, defaultEngine, expand, request, phrases, suggestions };
})();
