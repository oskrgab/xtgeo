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
make wasm-smoke    # load it in Node + Pyodide and run the read-path checks
make wasm-all      # both
```

`make wasm-smoke` needs the [`equinor/xtgeo-testdata`](https://github.com/equinor/xtgeo-testdata)
REEK fixtures. It reuses a sibling `../xtgeo-testdata` checkout if present (the
cibuildwheel convention), honours `XTGEO_TESTDATA_PATH`, or otherwise caches a
shallow clone under `wasm/.xtgeo-testdata/`.

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
  a browser consumer would, mounts the REEK fixtures, and runs the public-API
  checks, reporting pass/fail per check.
- [`smoke_checks.py`](smoke_checks.py) — the check registry that runs inside
  Pyodide. Two layers:
  - **Read path** (pure Python, resfo-backed): `import xtgeo` + both native
    modules, EGRID → `Grid` dimensions, static (INIT) and recurrent dated
    (UNRST) properties via `gridproperty_from_file` / `gridproperties_from_file`,
    a GRDECL read, and the masked `(ncol, nrow, nlay)` `values` array with a
    layer slice and a K-reduction.
  - **Native geometry** (executes `_cxtgeo` / `_internal`): cell dimensions
    `get_dz`/`get_dx`/`get_dy`, a geo-referenced 3D→2D map via
    `RegularSurface.slice_grid3d` (the native `surf_slice_grd3d` sampler),
    volumetrics `get_bulk_volume` / `get_phase_volumes` (the phase split must
    partition the bulk volume), and an XY→IJK round-trip via
    `get_ijk_from_points`. These prove the compiled modules actually *run*, not
    merely import — the operations resfo cannot provide.

  Each check asserts on observable values/shapes through xtgeo's public API —
  nothing mocked. Later slices extend coverage by appending to the `CHECKS` list.
