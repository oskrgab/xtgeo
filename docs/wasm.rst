.. highlight:: python

XTGeo in the browser (Pyodide / WASM)
=====================================

This fork of XTGeo ships an **Emscripten / WebAssembly wheel** so you can read
Eclipse simulation results and run grid-aware geometry operations *in the
browser*, inside `Pyodide <https://pyodide.org>`_ — no server, no native
toolchain, no install beyond a single ``micropip`` line.

After install, ``import xtgeo`` works in the browser: the native ``_cxtgeo`` and
``_internal`` modules are cross-compiled into the wheel, so the geometry
operations (geo-referenced 3D→2D sampling, cell volumetrics, ``dz/dx/dy``,
XY→IJK lookups, height-above-FFL) actually *execute* — not just the pure-Python
read path.

The decision record is `ADR-0001
<https://github.com/oskrgab/xtgeo/blob/main/docs/adr/0001-wasm-pyodide-distribution.md>`_;
build/CI details live in `wasm/README.md
<https://github.com/oskrgab/xtgeo/blob/main/wasm/README.md>`_.

.. note::

   This is a self-hosted distribution of the ``oskrgab/xtgeo`` fork. It is
   **not** published to PyPI, and the upstream ``equinor/xtgeo`` does not ship a
   WASM wheel. You install it directly from a GitHub Release URL.


Pinned Pyodide version
-----------------------

The wheel is **ABI-locked to exactly one Pyodide release**: its Emscripten
toolchain and its bundled ``numpy`` / ``scipy`` / ``pandas``. It will only load
in that version. **Your browser app's Pyodide version must match.**

================  =========
Component         Version
================  =========
Pyodide           ``0.29.4``
Python            ``3.13.2``
Emscripten        ``4.0.9``
================  =========

The single source of truth for these pins is `wasm/versions.env
<https://github.com/oskrgab/xtgeo/blob/main/wasm/versions.env>`_. If you load a
different Pyodide version, the wheel will fail to install or import — this is by
design, not a bug. Version bumps are deliberate.


Install
-------

Load the matching Pyodide version, then ``micropip.install`` the wheel from its
GitHub Release URL. The wheel and its WASM-safe dependencies are resolved from
that single asset.

.. code-block:: python

   import micropip

   await micropip.install(
       "https://github.com/oskrgab/xtgeo/releases/download/wasm-latest/"
       "xtgeo-<version>-cp313-cp313-pyemscripten_2025_0_wasm32.whl"
   )

   import xtgeo  # native _cxtgeo and _internal load here

Replace ``<version>`` with the version in the wheel's filename on the Release
page. Two kinds of Release are published:

* **``wasm-latest``** — a rolling pre-release, refreshed with the newest build.
  Convenient for trying it out; the asset changes under you over time.
* **``wasm-v*``** — an immutable, versioned Release (e.g. ``wasm-v1.0.0``). Pin
  to one of these for a reproducible browser app.

From JavaScript (loading Pyodide yourself), the same flow looks like:

.. code-block:: javascript

   // Pyodide MUST be the pinned version (0.29.4) for the wheel to load.
   const pyodide = await loadPyodide();
   await pyodide.loadPackage("micropip");
   const micropip = pyodide.pyimport("micropip");
   await micropip.install(
     "https://github.com/oskrgab/xtgeo/releases/download/wasm-latest/" +
     "xtgeo-<version>-cp313-cp313-pyemscripten_2025_0_wasm32.whl"
   );
   pyodide.runPython("import xtgeo");


Usage example
-------------

A self-contained read → layer-extraction → 2D-map walkthrough on Eclipse files.
This mirrors the CI smoke test and runs unchanged inside Pyodide once the files
are present in the in-memory `Emscripten filesystem
<https://emscripten.org/docs/api_reference/Filesystem-API.html>`_ (e.g. written
from a file upload or ``fetch``).

.. code-block:: python

   import xtgeo

   # 1. Read the grid geometry (EGRID) into a Grid.
   grd = xtgeo.grid_from_file("REEK.EGRID", fformat="egrid")
   print(grd.dimensions)            # (ncol, nrow, nlay), e.g. (40, 64, 14)

   # 2. Read a static property (PORO) from the INIT file. The native modules
   #    must already be loaded for this Grid to exist; the read itself is pure
   #    Python (resfo-backed).
   poro = xtgeo.gridproperty_from_file(
       "REEK.INIT", fformat="init", name="PORO", grid=grd
   )

   # 3. Extract a single layer (top of reservoir). values is a masked
   #    (ncol, nrow, nlay) numpy array, so this is plain numpy slicing.
   top_layer = poro.values[:, :, 0]      # 2D (ncol, nrow), still masked
   kmean = poro.values.mean(axis=2)      # index-space mean over K

   # 4. Sample the property onto a geo-referenced 2D map. This drives the
   #    native surf_slice_grd3d sampler: for every map node it finds the
   #    intersected cell in real-world coordinates and reads PORO there.
   surf = xtgeo.surface_from_grid3d(grd)  # a RegularSurface matching the grid
   surf.values = 1700.0                   # constant slicing depth (TVDSS)
   surf.slice_grid3d(grd, poro)

   print(surf.values.mean())              # mean PORO on the sampled map

Reading recurrent (dynamic) results from a restart file works the same way, with
a ``date``:

.. code-block:: python

   press = xtgeo.gridproperty_from_file(
       "REEK.UNRST", fformat="unrst", name="PRESSURE", grid=grd, date=19991201
   )

ROFF grid/property files read and **write** under WASM too (``roffio`` is pure
Python), so you can author or edit a property and persist it back to the
in-memory filesystem to stage a download.


Limitations
-----------

The WASM wheel deliberately drops a handful of dependencies that cannot be
cross-compiled for / are absent from Pyodide. ``import xtgeo`` still works; only
the dependent *feature* fails, and it fails with a **clear, explanatory error**
— not a cryptic stack trace. Calling one of these under WASM is expected
behavior, not a defect.

==========================================  ====================  ==========================
Feature                                     Missing dependency    What you get if you call it
==========================================  ====================  ==========================
SEG-Y / seismic ``Cube`` import & export    ``segyio``            ``ImportError``
Surface gridding from points/wells          ``gstools``           ``ImportError``
Plotting (``.quickplot``, ``.plot``)        ``xtgeoviz``          ``ModuleNotFoundError``
HDF5 export (``fformat="hdf"``)             ``hdf5plugin``        ``ImportError``
==========================================  ====================  ==========================

The ``segyio`` / ``gstools`` / ``hdf5plugin`` paths route through XTGeo's
optional-dependency guard, so calling them raises a message that names the
package and points at the reason:

.. code-block:: text

   ImportError: The optional dependency 'segyio' is required for this feature
   but is not available in this environment. It is excluded from the WASM/Pyodide
   build of xtgeo (see docs/adr/0001-wasm-pyodide-distribution.md).

Plotting imports ``xtgeoviz`` directly, so calling ``.quickplot()`` /
``.plot()`` raises a plain, equally clear ``ModuleNotFoundError: No module named
'xtgeoviz'``.

If you need any of these, run XTGeo in a normal (native) Python environment;
they are present in the PyPI wheels.


SUMMARY data: use resfo directly
---------------------------------

Eclipse **SUMMARY** files (``SMSPEC`` / ``UNSMRY`` — time-series vectors like
``FOPR``, ``WBHP``) are outside *XTGeo's* scope — and this is **not** a WASM
limitation. XTGeo has no summary-reading API on any platform; it has never read
these files.

The reader for them is `resfo <https://github.com/equinor/resfo>`_, which is a
**core XTGeo dependency** (it backs the pure-Python EGRID/INIT/UNRST read path).
The WASM profile does *not* strip it, so installing the wheel pulls ``resfo`` in
automatically — there is nothing extra to install:

.. code-block:: python

   import resfo  # already present alongside xtgeo in the wheel

   for kw, arr in resfo.read("REEK.UNSMRY"):
       ...  # (keyword, array) tuples — build your own time series

So in the browser you read grids/properties through ``xtgeo`` and summary
vectors through ``resfo`` — both running in the same Pyodide session, from the
one ``micropip.install``.
