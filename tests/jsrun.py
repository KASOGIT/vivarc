import json
import os
import subprocess

JS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "js")

HARNESS = """
const fs = require("fs"), vm = require("vm");
globalThis.window = { __vm: {} };
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
const pins = window.__vm.pins, spaces = window.__vm.spaces;
const input = JSON.parse(process.argv[2]);
const out = (function () { return eval(input.expr); })();
console.log(JSON.stringify(out === undefined ? null : out, (k, v) => (v === undefined ? null : v)));
"""


def run_js(module, expr, **data):
    """Load src/js/<module> with a fake window, then evaluate `expr`; `data` entries are variables in `expr`."""
    source = "".join(f"const {k} = {json.dumps(v)};\n" for k, v in data.items()) + f"return ({expr});"
    result = subprocess.run(["node", "-e", HARNESS, os.path.join(JS_DIR, module), json.dumps({"expr": f"(() => {{ {source} }})()"})],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
