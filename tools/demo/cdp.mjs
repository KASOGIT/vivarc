// Evaluates JS in the demo Vivaldi's UI page (window.html) over the DevTools protocol.
// CLI: node cdp.mjs <js-expression | @file.js>     Module: import { connect } from "./cdp.mjs"
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const PORT = Number(process.env.DEMO_PORT || 9335);

export async function connect() {
  const targets = await (await fetch(`http://localhost:${PORT}/json/list`)).json();
  const target = targets.find((t) => t.url.includes("/window.html") && t.webSocketDebuggerUrl);
  if (!target) throw new Error("demo Vivaldi UI not found: run `tools/demo/demo.sh launch` first");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve) => (ws.onopen = resolve));
  let next = 0;
  const evaluate = (expression) => new Promise((resolve, reject) => {
    const id = ++next;
    ws.addEventListener("message", function onMessage(m) {
      const r = JSON.parse(m.data);
      if (r.id !== id) return;
      ws.removeEventListener("message", onMessage);
      if (r.result?.exceptionDetails) reject(new Error(r.result.exceptionDetails.exception?.description || "evaluate failed"));
      else resolve(r.result?.result?.value);
    });
    ws.send(JSON.stringify({ id, method: "Runtime.evaluate", params: { expression, awaitPromise: true, returnByValue: true } }));
  });
  return { evaluate, close: () => ws.close() };
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const arg = process.argv[2];
  const { evaluate, close } = await connect();
  const value = await evaluate(arg.startsWith("@") ? readFileSync(arg.slice(1), "utf8") : arg);
  console.log(typeof value === "string" ? value : JSON.stringify(value, null, 1));
  close();
}
