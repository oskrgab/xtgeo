// Node + Pyodide smoke-test harness for the xtgeo WASM wheel.
//
// Loads Pyodide, micropip.installs the freshly built emscripten wheel exactly
// as a browser consumer would, mounts the REEK fixtures from
// equinor/xtgeo-testdata, and runs the public-API read-path checks defined in
// smoke_checks.py. Each check asserts on observable values/shapes through
// xtgeo's public API -- nothing mocked, no build internals. Later slices add
// assertions by appending to the CHECKS registry in smoke_checks.py.
//
// Usage: node smoke_test.mjs <path-to-wheel> <path-to-xtgeo-testdata>

import { loadPyodide, version as pyodideVersion } from "pyodide";
import { readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const wheelPath = process.argv[2];
const testdataDir = process.argv[3];
if (!wheelPath || !testdataDir) {
  console.error(
    "usage: node smoke_test.mjs <path-to-wheel> <path-to-xtgeo-testdata>",
  );
  process.exit(2);
}

const here = dirname(fileURLToPath(import.meta.url));
const wheelName = basename(wheelPath);

console.log(`Pyodide runtime version : ${pyodideVersion}`);
console.log(`Wheel under test        : ${wheelName}`);
console.log(`Test fixtures           : ${testdataDir}`);

if (!/emscripten.*wasm32\.whl$/.test(wheelName)) {
  console.error(`ERROR: ${wheelName} is not an emscripten_*_wasm32 wheel`);
  process.exit(1);
}

const pyodide = await loadPyodide();
await pyodide.loadPackage("micropip");

// Make the wheel visible to micropip via the in-memory Emscripten filesystem.
const wheelBytes = readFileSync(wheelPath);
const emfsWheel = `/tmp/${wheelName}`;
pyodide.FS.writeFile(emfsWheel, wheelBytes);

const micropip = pyodide.pyimport("micropip");
console.log("Installing wheel and resolving dependencies via micropip...");
await micropip.install(`emfs:${emfsWheel}`);

// Mount the host test fixtures read-only so the pure-Python read path can open
// them exactly as it would on a real disk.
pyodide.FS.mkdirTree("/testdata");
pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: testdataDir }, "/testdata");

// Load the Python check registry and run every check inside Pyodide.
const checksSrc = readFileSync(join(here, "smoke_checks.py"), "utf8");
pyodide.FS.writeFile("/tmp/smoke_checks.py", checksSrc);

console.log("Running public-API read-path checks under Pyodide...\n");
const resultsJson = await pyodide.runPythonAsync(`
import sys, json
sys.path.insert(0, "/tmp")
import smoke_checks
json.dumps(smoke_checks.run_checks("/testdata"))
`);

const results = JSON.parse(resultsJson);
let failed = 0;
for (const r of results) {
  if (r.status === "pass") {
    console.log(`  PASS  ${r.name}  ${JSON.stringify(r.facts)}`);
  } else {
    failed += 1;
    console.log(`  FAIL  ${r.name}  ${r.error}`);
    if (r.traceback) {
      console.log(r.traceback.replace(/^/gm, "        "));
    }
  }
}

console.log("");
const total = results.length;
if (failed) {
  console.error(`FAIL: ${failed}/${total} read-path checks failed under Pyodide`);
  process.exit(1);
}
console.log(`PASS: all ${total} read-path checks passed under Pyodide`);
