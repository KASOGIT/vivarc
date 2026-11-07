import json
import os
import subprocess

JS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "js")

HARNESS = """
const fs = require("fs"), vm = require("vm");
globalThis.window = { __vm: JSON.parse(process.argv[3] || "{}") };
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const pins = window.__vm.pins, spaces = window.__vm.spaces, workspaces = window.__vm.workspaces, settings = window.__vm.settings, search = window.__vm.search, recent = window.__vm.recent, archive = window.__vm.archive, commandBar = window.__vm.commandBar;
const input = JSON.parse(process.argv[2]);
const out = (function () { return eval(input.expr); })();
console.log(JSON.stringify(out === undefined ? null : out, (k, v) => (v === undefined ? null : v)));
"""


def run_js(module, expr, _vm=None, **data):
    """Load src/js/<module> with a fake window, then evaluate `expr`; `data` entries are variables in `expr`.
    `_vm` presets window.__vm before the module loads (for example the platform's `keys`)."""
    source = "".join(f"const {k} = {json.dumps(v)};\n" for k, v in data.items()) + f"return ({expr});"
    result = subprocess.run(["node", "-e", HARNESS, os.path.join(JS_DIR, module), json.dumps({"expr": f"(() => {{ {source} }})()"}),
                             json.dumps(_vm or {})],
                            capture_output=True, encoding="utf8", check=True)
    return json.loads(result.stdout)
