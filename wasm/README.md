# xtgeo WASM / Pyodide build

Cross-compiles xtgeo's native modules (`_cxtgeo`, `_internal`) into an
Emscripten `wasm32` wheel that loads in [Pyodide](https://pyodide.org). See
[`docs/adr/0001-wasm-pyodide-distribution.md`](../docs/adr/0001-wasm-pyodide-distribution.md)
for the decision record.

## Versions (single source of truth)

All pinned versions live in [`versions.env`](versions.env). The wheel is
ABI-locked to one Pyodide release — consumers must run that exact version.

| | |
|---|---|
| Pyodide | `0.29.4` |
| Python | `3.13.2` |
| Emscripten | `4.0.9` |
| pyodide-build | `0.34.4` |

## Build

```bash
make wasm          # build the wheel in the pinned Docker image -> dist/wasm/
make wasm-smoke    # load it in Node + Pyodide and assert `import xtgeo`
make wasm-all      # both
```

`make wasm` produces `dist/wasm/xtgeo-<ver>-cp313-cp313-pyemscripten_2025_0_wasm32.whl`.

> **Wheel tag note.** Pyodide ≥0.29 installs Emscripten wheels under the
> `pyemscripten_<year>_<n>_wasm32` platform tag. `pyodide build` first emits an
> `emscripten_4_0_9_wasm32` wheel and then repacks it to the `pyemscripten`
> tag, which is the form `micropip` accepts for Pyodide 0.29.4. Both are the
> same Emscripten/wasm32 artifact.

## How it works

- [`Dockerfile`](Dockerfile) — pinned toolchain image (CPython + emsdk +
  pyodide-build + the Pyodide cross-build environment).
- [`apply_wasm_profile.py`](apply_wasm_profile.py) — strips the dependencies
  that are unbuildable for / absent from Pyodide (`segyio`, `gstools`,
  `xtgeoviz`, `hdf5plugin`) from the wheel metadata. The runtime guards in
  `src/xtgeo/common/_optional_deps.py` keep `import xtgeo` working without them;
  calling an excluded feature raises a clear error.
- [`build.sh`](build.sh) — in-container: applies the profile and runs
  `pyodide build`.
- [`smoke_test.mjs`](smoke_test.mjs) — `micropip.install`s the wheel exactly as
  a browser consumer would and asserts both native modules load.
