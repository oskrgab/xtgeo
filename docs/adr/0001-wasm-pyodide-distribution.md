---
status: accepted
---

# WASM/Pyodide distribution via self-hosted Emscripten wheel

## Context

This fork (`oskrgab/xtgeo`) needs xtgeo usable inside Pyodide so a reservoir engineer can,
in the browser, read Eclipse 3D results (`INIT`/`UNRST`/`EGRID`/`GRDECL`) and ROFF, build
`Grid`/`GridProperty`/`RegularSurface` objects, and run **grid-aware geometry operations**
(geo-referenced 3D→2D surface sampling, cell volumetrics, `dz/dx/dy`, XY→IJK lookups,
height-above-FFL). SUMMARY vectors are explicitly out of scope — `resfo` handles those directly.

Property reading and index-space work (`prop.values[:, :, 0]`, reductions over K) are pure-Python
in xtgeo and need no compiled code. The geometry operations, however, live in the native modules
`_cxtgeo` (SWIG over `src/lib/src/*.c`) and `_internal` (pybind11 over the C++ geometry). Because the
required workflow includes those operations, the native modules **must** be cross-compiled for WASM —
a pure-Python WASM distribution would not suffice.

## Decision

- **Cross-compile with `pyodide-build`** into an `emscripten_*_wasm32` wheel, reusing the existing
  scikit-build-core/CMake setup. OpenMP stays disabled (stock Pyodide is single-threaded; already
  guarded). Eigen3 + fmt come via the existing FetchContent path.
- **Pin to a single latest-stable Pyodide version** as the source of truth in CI. The wheel is
  ABI-locked to that version's Emscripten and bundled numpy/scipy/pandas; bumps are deliberate.
- **Self-host the wheel** as a GitHub Release asset; consumers `micropip.install('<release-url>')`.
  We do not own the `xtgeo` name on PyPI, so a renamed PyPI package is deferred.
- **Strip unbuildable install dependencies** in the WASM build profile — drop `segyio`, `gstools`,
  `xtgeoviz`, `hdf5plugin` (absent from Pyodide). Their lazy imports fail only if those features are
  called. `pyarrow` (Pyodide ≥0.27) and `h5py` are present but unused on the ECL/ROFF path.
- **Verify with a Node + Pyodide smoke test** in CI: install the wheel, then `import xtgeo` → build a
  `Grid` from a small EGRID → load a property from UNRST/INIT → extract a layer → assert values.
  The full pytest suite cannot run under WASM (no multiprocessing/xdist, hypothesis excluded).
- **Reproduce locally with a pinned Docker image** (`make wasm`) identical to CI.
- **Trigger** via a new `.github/workflows/wasm.yml`: build + smoke-test on PRs touching native/build
  files; publish to a GitHub Release on `workflow_dispatch` and on `wasm-v*` tags.

## Considered options

- **`resfo` alone** — pure-Python, runs in Pyodide today, but provides only raw `(keyword, array)`
  tuples: no grid geometry, no object model, none of the geometry operations required. Rejected.
- **Pure-Python xtgeo WASM** (decouple native imports, ship a plain wheel) — covers reading +
  index-space maps with no Emscripten/SWIG/ABI pain. Rejected because the required workflow needs
  native geometry operations.
- **Full custom Pyodide distribution / emscripten-forge** — heavier than a loadable wheel and less
  aligned with "works in stock Pyodide." Rejected.
- **Publish a renamed package to PyPI** — nicer `micropip` UX but adds a divergent package name and
  metadata upkeep. Deferred until the build is proven.

## Consequences

- The first real risk to retire is whether the SWIG-generated wrapper (numpy headers) and
  pybind11/Eigen/fmt compile under Emscripten at all — that is the implementation spike.
- WASM users get a hard error if they call SEGY/Cube, gstools gridding, xtgeoviz plotting, or the
  HDF5 export path. This is accepted, not a bug.
- The wheel only loads in the pinned Pyodide version; consumers must match it.
