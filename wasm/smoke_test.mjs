// Node + Pyodide smoke test for the xtgeo WASM wheel.
//
// Loads Pyodide, micropip.installs the freshly built emscripten wheel exactly
// as a browser consumer would, and asserts that `import xtgeo` succeeds with
// both native modules (_cxtgeo, _internal) loaded.
//
// Usage: node smoke_test.mjs <path-to-wheel>

import { loadPyodide, version as pyodideVersion } from "pyodide";
import { readFileSync } from "node:fs";
import { basename } from "node:path";

const wheelPath = process.argv[2];
if (!wheelPath) {
  console.error("usage: node smoke_test.mjs <path-to-wheel>");
  process.exit(2);
}

const wheelName = basename(wheelPath);
console.log(`Pyodide runtime version : ${pyodideVersion}`);
console.log(`Wheel under test        : ${wheelName}`);

if (!/emscripten.*wasm32\.whl$/.test(wheelName)) {
  console.error(`ERROR: ${wheelName} is not an emscripten_*_wasm32 wheel`);
  process.exit(1);
}

const pyodide = await loadPyodide();
await pyodide.loadPackage("micropip");

// Make the wheel visible to micropip via the in-memory Emscripten filesystem.
const wheelBytes = readFileSync(wheelPath);
const emfsPath = `/tmp/${wheelName}`;
pyodide.FS.writeFile(emfsPath, wheelBytes);

const micropip = pyodide.pyimport("micropip");
console.log("Installing wheel and resolving dependencies via micropip...");
await micropip.install(`emfs:${emfsPath}`);

console.log("Importing xtgeo and its native modules...");
const result = await pyodide.runPythonAsync(`
import xtgeo
from xtgeo import _cxtgeo, _internal

# Touch a symbol from each native module so we prove they actually loaded,
# not merely that the name resolved.
assert hasattr(_cxtgeo, "XTGeoCLibError"), "_cxtgeo did not load its contents"
assert _internal.__name__.endswith("_internal"), "_internal did not load"

import json
json.dumps({
    "version": xtgeo.__version__,
    "cxtgeo": _cxtgeo.__name__,
    "internal": _internal.__name__,
})
`);

const info = JSON.parse(result);
console.log("");
console.log("PASS: import xtgeo succeeded under Pyodide");
console.log(`  xtgeo.__version__ : ${info.version}`);
console.log(`  native modules    : ${info.cxtgeo}, ${info.internal}`);
