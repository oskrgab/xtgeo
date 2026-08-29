# Context: xtgeo

A Python library for subsurface data objects (3D grids, surfaces, wells, points/polygons,
cubes), with the heavy geometry implemented in C/C++ and exposed through Python wrappers.

## Glossary

### Simulation files
Umbrella term used loosely by reservoir engineers. In xtgeo it splits into two unrelated kinds,
and only one is in scope:

- **Summary data** — time-series vectors (e.g. `FOPR`, `WBHP`) in Eclipse `SMSPEC`/`UNSMRY`.
  **xtgeo does not read these.** Use `resfo` (or `resdata`/`ecl2df`) directly.
- **3D grid results** — static and recurrent cell properties (perm, poro, pressure, saturations)
  in `INIT`/`UNRST`, tied to a grid geometry from `EGRID`/`GRDECL`. This *is* xtgeo's domain.

### resfo vs xtgeo
- **resfo** — pure-Python low-level reader/writer of Eclipse binary *keyword* records. Gives raw
  arrays; knows nothing about grid geometry. Runs in Pyodide as-is.
- **xtgeo** — assembles domain objects (`Grid`, `GridProperty`, `RegularSurface`) on top of those
  raw records and provides **grid-aware operations**.

### Grid-aware operation
Any operation that needs the 3D cell geometry, not just keyword arrays: extracting a layer,
sampling a 3D property into a 2D `RegularSurface` map, cell lookups, fence/randomline extraction.
These are implemented in the native C/C++ modules (`_cxtgeo`, `_internal`), so they require a
working compiled extension on every target platform — including WASM.

### Native modules
- **`_cxtgeo`** — SWIG-generated wrapper over the C library in `src/lib/src/*.c`.
- **`_internal`** — pybind11 module over the C++ geometry/grid code.
Both are imported at the top of `xtgeo/__init__.py`, so `import xtgeo` fails entirely if either
does not build for the target platform.
