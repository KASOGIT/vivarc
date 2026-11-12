import os
import shutil
import subprocess
import unittest

from jsrun import JS_DIR

# The browser UI loses focus to the page's webview, so navigator.clipboard rejects there ("Document is not focused").
# The copy still has to reach the clipboard.
HARNESS = """
const fs = require("fs"), vm = require("vm");
let clipboard = "";
const listeners = {};
globalThis.window = {};
Object.defineProperty(globalThis, "navigator", { value: { platform: "MacIntel",
  clipboard: { writeText: () => Promise.reject(new Error("Document is not focused.")) } } });
globalThis.indexedDB = { open: () => ({}) };
globalThis.vivaldi = { tabsPrivate: { onKeyboardShortcut: { addListener() {} } } };
globalThis.MutationObserver = class { observe() {} disconnect() {} };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "" });
globalThis.setTimeout = () => 0;
const print = console.log;
console.log = () => {};
globalThis.document = {
  documentElement: { classList: { add() {} } },
  querySelector: () => null,
  addEventListener: (type, fn) => { listeners[type] = fn; },
  removeEventListener: (type, fn) => { if (listeners[type] === fn) delete listeners[type]; },
  execCommand: (cmd) => {
    if (cmd !== "copy" || !listeners.copy) return false;
    const data = {};
    listeners.copy({ clipboardData: { setData: (t, v) => { data[t] = v; } }, preventDefault() {}, stopPropagation() {} });
    clipboard = data["text/plain"] || "";
    return true;
  },
};
vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
Promise.resolve(window.__vm.copyText("https://example.com/page")).then(() => print(clipboard));
"""


@unittest.skipUnless(shutil.which("node"), "node is needed to test the copy helper")
class CopyText(unittest.TestCase):
    def test_copies_when_the_ui_document_is_not_focused(self):
        result = subprocess.run(["node", "-e", HARNESS, os.path.join(JS_DIR, "00-core.js")],
                                capture_output=True, encoding="utf8", check=True)
        self.assertEqual(result.stdout.strip(), "https://example.com/page")


if __name__ == "__main__":
    unittest.main()
