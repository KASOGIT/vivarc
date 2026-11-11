// Visits the sites the storyboard shows once, so a fresh profile does not film YouTube's cookie wall or Apple's
// region banner: opens each page, clicks its consent / close button in the page itself, then closes the tab.
import { PORT, connect } from "./cdp.mjs";

const PAGES = [
  ["https://www.youtube.com/results?search_query=rick+astley", "youtube.com",
    `[...document.querySelectorAll("button")].find(b=>/accept all|tout accepter/i.test(b.textContent))?.click()`],
  ["https://www.apple.com/", "apple.com",
    `document.querySelector(".ac-ls-close, [class*=locale] button[aria-label], button[aria-label*=lose i]")?.click()`],
];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const inPage = async (match, expression) => {
  const targets = await (await fetch(`http://localhost:${PORT}/json/list`)).json();
  const target = targets.find((t) => t.type === "page" && t.url.includes(match));
  if (!target) return "no page";
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression } }));
  await wait(500);
  ws.close();
  return "clicked";
};

const ui = await connect();
for (const [url, match, click] of PAGES) {
  const id = await ui.evaluate(`chrome.tabs.create({url:${JSON.stringify(url)},active:false}).then(t=>t.id)`);
  await wait(5000);
  console.log(match, await inPage(match, click));
  await wait(2500);
  await ui.evaluate(`chrome.tabs.remove(${id})`);
}
ui.close();
