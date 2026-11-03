// The command bar's search engine: the default one picked in Vivaldi's settings (the private-window default in a
// private window), read through vivaldi.searchEngines, the same API Vivaldi's own address bar uses. chrome.search is
// not available to Vivaldi's UI, so it cannot run the search for us. DuckDuckGo is only used when Vivaldi gives no answer.
(() => {
  const FALLBACK = {
    name: "DuckDuckGo",
    url: "https://duckduckgo.com/?q={searchTerms}",
    suggestUrl: "https://duckduckgo.com/ac/?q={searchTerms}&type=list",
  };

  // getTemplateUrls() answers { templateUrls: [...], defaultSearch: guid, defaultPrivate: guid, ... }.
  const defaultEngine = (reply, incognito) => {
    const guid = (incognito && reply?.defaultPrivate) || reply?.defaultSearch;
    return (reply?.templateUrls || []).find((t) => t.guid === guid && t.url) || null;
  };

  // A template with the query filled in, or null when it does not take a query in the URL or is not a web address
  // (for example Google's {google:baseURL}, which only Vivaldi itself can expand).
  const fill = (template, query) => {
    if (!template || !/\{searchTerms\}|%s/.test(template)) return null;
    const url = template.replace(/\{searchTerms\}|%s/g, encodeURIComponent(query)).replace(/\{[^}]*\}/g, "");
    return /^https?:\/\//i.test(url) ? url : null;
  };

  // Where to ask for suggestions: the engine's own suggest URL. An engine without one (or with a POST-only one)
  // gets no suggestions, rather than sending what you type to a service you did not pick.
  const suggestUrl = (engine, query) => (engine && !engine.suggestPostParams ? fill(engine.suggestUrl, query) : null);

  // Suggest replies are OpenSearch JSON, [query, [phrases], ...], possibly behind Google's )]}' guard;
  // DuckDuckGo without type=list answers [{phrase}].
  const parseSuggestions = (text) => {
    let data;
    try { data = JSON.parse(String(text).replace(/^\)\]\}'?\s*/, "")); } catch (_) { return []; }
    const phrases = Array.isArray(data?.[1]) ? data[1] : Array.isArray(data) ? data.map((d) => d?.phrase) : [];
    return phrases.filter((p) => typeof p === "string" && p);
  };

  const api = { FALLBACK, defaultEngine, fill, suggestUrl, parseSuggestions };
  window.__vm.search = api;
  if (typeof vivaldi === "undefined" || !vivaldi.searchEngines) return;

  let reply = null;
  let incognito = false;
  const load = async () => {
    try { reply = await vivaldi.searchEngines.getTemplateUrls(); } catch (e) { console.warn("[vivarc] search engines:", e); }
  };
  load();
  vivaldi.searchEngines.onTemplateUrlsChanged?.addListener(load);
  chrome.windows.getCurrent().then((w) => { incognito = !!w.incognito; }).catch(() => {});

  api.current = () => defaultEngine(reply, incognito) || FALLBACK;
  // Vivaldi builds the search URL itself, so engines with placeholders like {google:baseURL} work as in the address bar.
  // Without an engine it is the default one; a keyword engine from Vivaldi's list passes its own.
  api.searchUrl = async (query, engine = api.current()) => {
    if (engine.guid) {
      try {
        const request = await vivaldi.searchEngines.getSearchRequest(engine.guid, query);
        if (request?.url && !request.postParams) return request.url;
      } catch (e) {
        console.warn("[vivarc] search request:", e);
      }
    }
    return fill(engine.url, query) || fill(FALLBACK.url, query);
  };
})();
