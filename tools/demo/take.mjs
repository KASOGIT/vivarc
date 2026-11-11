// The storyboard: drives the demo Vivaldi with real input while `demo.sh record` films it.
// Every target is looked up in the live UI right before it is clicked, so layout shifts (a new favorites row, the URL
// bar appearing) never send a click to the wrong place. Edit the STORY section to change the demo.
import { execFileSync } from "node:child_process";
import { connect } from "./cdp.mjs";

const bin = process.env.DEMO_INPUT;
const { evaluate, close } = await connect();
const input = (cmds) => execFileSync(bin, [cmds]);
const wait = (ms) => input(`wait ${ms}`);
const center = `const b=e.getBoundingClientRect();return [Math.round(screenX+b.x+b.width/2),Math.round(screenY+b.y+b.height/2)]`;
const at = async (selector, text = "") => {
  const p = await evaluate(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})]
    .find(e=>e.getBoundingClientRect().width&&(e.title||e.textContent||"").includes(${JSON.stringify(text)}));
    if(!e)return null;${center}})()`);
  if (!p) throw new Error(`not found: ${selector} ${text}`);
  return p;
};
const click = async (selector, text, ms = 600) => { const [x, y] = await at(selector, text); input(`click ${x} ${y} ${ms}`); };
const rclick = async (selector, text) => { const [x, y] = await at(selector, text); input(`rclick ${x} ${y}`); };
const toggle = async (label, ms = 450) => {
  const p = await evaluate(`(()=>{const row=[...document.querySelectorAll(".vm-set-row")].find(r=>r.textContent.includes(${JSON.stringify(label)}));
    const e=row&&row.querySelector("input");if(!e)return null;${center}})()`);
  if (!p) throw new Error(`no setting ${label}`);
  input(`click ${p[0]} ${p[1]} ${ms}`);
};
// Key codes: 17 t, 8 c, 36 return, 48 tab, 53 escape, 125 down.
const commandBar = (text) => input(`move 760 420 500; wait 200; key 17 cmd; wait 600; type ${text}; wait 700`);

// ---- STORY ----
wait(1200);
await rclick(".vm-row.vm-tab", "vivaldi.com/blog"); wait(500);
await click(".vm-menu-item", "Add to Favorites", 350); wait(1500);
await rclick(".vm-row.vm-tab", "excalidraw"); wait(500);
await click(".vm-menu-item", "Pin Tab", 350); wait(1500);

commandBar("glass"); input("key 125; wait 300; key 36; wait 900");
await toggle("Liquid glass", 500); wait(1300);
await toggle("URL bar", 400); wait(1300);
input("move 734 600 400; wait 200; scroll 110 -7; wait 900");
await click(".vm-set-close", "", 500); wait(700);

const [nx, ny] = await at(".vm-space-name");
input(`click ${nx + 262} ${ny} 600; wait 600`);
await click(".vm-theme-swatch:nth-child(3)", "", 400); wait(700);
await click(".vm-theme-swatch:nth-child(9)", "", 300); wait(1100);
input("key 53; wait 400");

commandBar("split"); input("key 125; wait 350; key 36; wait 900");
input("type apple.com; wait 400; key 36; wait 2600");

commandBar("yt"); input("key 48; wait 700; type rick astley never gonna give you up; wait 500; key 36; wait 3200");
input("key 8 cmd,shift; wait 2500");
// ---- END ----
close();
