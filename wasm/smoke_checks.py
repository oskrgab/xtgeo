"""Public-API read-path checks for the xtgeo WASM wheel, run inside Pyodide.

Each check is a function ``check_*(root)`` that asserts on externally
observable behavior through xtgeo's *public* API -- grid/property dimensions,
known property means, masked-array shapes and index-space operations. Nothing
is mocked and no build internals are touched: this is exactly what a browser
consumer would observe, just executing inside the compiled WASM wheel.

This is the pure-Python read path (resfo-backed EGRID/INIT/UNRST/GRDECL
parsing); it makes no native calls, but it runs inside the wheel whose native
modules (_cxtgeo, _internal) loaded at import time.

Later WASM slices extend coverage by appending a function to ``CHECKS`` -- e.g.
the native geometry operations (``Grid.get_dz``, ``surf_slice_grd3d``). The
harness in ``smoke_test.mjs`` runs every registered check and reports pass/fail.

Fixtures come from the equinor/xtgeo-testdata REEK dataset, mirroring the paths
and expected values used by the native ``tests/test_grid3d`` suite.
"""

from __future__ import annotations

import numpy.ma as ma

import xtgeo

# REEK fixtures, relative to the mounted test-data root.
EGRID = "3dgrids/reek/REEK.EGRID"
INIT = "3dgrids/reek/REEK.INIT"
UNRST = "3dgrids/reek/REEK.UNRST"
GRDECL = "3dgrids/reek3/reek_sim.grdecl"  # ASCII Eclipse deck

REEK_DIMS = (40, 64, 14)


def _egrid(root):
    """Read the REEK EGRID into a Grid (reused by several checks)."""
    return xtgeo.grid_from_file(f"{root}/{EGRID}", fformat="egrid")


def check_import(root):
    """Both native modules actually loaded (not merely name-resolved)."""
    from xtgeo import _cxtgeo, _internal

    assert hasattr(_cxtgeo, "XTGeoCLibError"), "_cxtgeo did not load its contents"
    assert _internal.__name__.endswith("_internal"), "_internal did not load"
    return {"xtgeo": xtgeo.__version__}


def check_egrid_dimensions(root):
    """EGRID -> Grid with the expected (ncol, nrow, nlay) and active counts."""
    grd = _egrid(root)
    assert grd.dimensions == REEK_DIMS, f"{grd.dimensions} != {REEK_DIMS}"
    assert grd.nactive == 35838, grd.nactive
    assert grd.ntotal == 35840, grd.ntotal
    return {"dimensions": list(grd.dimensions), "nactive": grd.nactive}


def check_init_property(root):
    """Static PORO from INIT via the public gridproperty_from_file."""
    grd = _egrid(root)
    poro = xtgeo.gridproperty_from_file(
        f"{root}/{INIT}", fformat="init", name="PORO", grid=grd
    )
    assert poro.dimensions == REEK_DIMS, poro.dimensions
    assert isinstance(poro.values, ma.MaskedArray), type(poro.values)
    mean = float(poro.values.mean())
    assert abs(mean - 0.1677) < 1.0e-3, mean
    return {"PORO_mean": mean}


def check_unrst_property(root):
    """Recurrent PRESSURE/SWAT from UNRST for a known date."""
    grd = _egrid(root)
    press = xtgeo.gridproperty_from_file(
        f"{root}/{UNRST}", fformat="unrst", name="PRESSURE", grid=grd, date=19991201
    )
    assert press.dimensions == REEK_DIMS, press.dimensions
    pmean = float(press.values.mean())
    assert abs(pmean - 334.5232) < 1.0e-2, pmean

    swat = xtgeo.gridproperty_from_file(
        f"{root}/{UNRST}", fformat="unrst", name="SWAT", grid=grd, date=19991201
    )
    smean = float(swat.values.mean())
    assert abs(smean - 0.8780) < 1.0e-2, smean
    return {"PRESSURE_19991201_mean": pmean, "SWAT_19991201_mean": smean}


def check_unrst_multi_dates(root):
    """gridproperties_from_file with several dates -> dated, named props."""
    grd = _egrid(root)
    gps = xtgeo.gridproperties_from_file(
        f"{root}/{UNRST}",
        fformat="unrst",
        names=["PRESSURE", "SWAT"],
        dates=[19991201, 20010101, 20030101],
        grid=grd,
    )
    names = list(gps.names)
    for key in ("PRESSURE_19991201", "PRESSURE_20030101", "SWAT_19991201"):
        assert key in names, f"{key} not in {names}"
    pmean = float(gps["PRESSURE_20030101"].values.mean())
    assert abs(pmean - 308.45) < 1.0e-1, pmean
    return {"names": names, "PRESSURE_20030101_mean": pmean}


def check_grdecl(root):
    """ASCII GRDECL grid reads successfully with expected dimensions."""
    grd = xtgeo.grid_from_file(f"{root}/{GRDECL}", fformat="grdecl")
    assert grd.dimensions == REEK_DIMS, grd.dimensions
    assert grd.nactive == 35812, grd.nactive
    return {"dimensions": list(grd.dimensions), "nactive": grd.nactive}


def check_masked_index_ops(root):
    """values is a (ncol, nrow, nlay) masked array; slice + K-reduction work."""
    grd = _egrid(root)
    poro = xtgeo.gridproperty_from_file(
        f"{root}/{INIT}", fformat="init", name="PORO", grid=grd
    )
    vals = poro.values
    assert isinstance(vals, ma.MaskedArray), type(vals)
    assert vals.shape == REEK_DIMS, vals.shape
    assert vals.mask.any(), "expected some inactive (masked) cells"

    # Single-layer slice (top of reservoir) -> 2D (ncol, nrow).
    top = vals[:, :, 0]
    assert top.shape == REEK_DIMS[:2], top.shape

    # Index-space reduction over K -> 2D (ncol, nrow), still masked.
    kmean = vals.mean(axis=2)
    assert isinstance(kmean, ma.MaskedArray), type(kmean)
    assert kmean.shape == REEK_DIMS[:2], kmean.shape

    return {
        "values_shape": list(vals.shape),
        "layer_slice_shape": list(top.shape),
        "kmean_shape": list(kmean.shape),
    }


# Registry of checks, run in order by the Node harness. Append here in later
# slices to extend coverage (e.g. native geometry operations).
CHECKS = [
    check_import,
    check_egrid_dimensions,
    check_init_property,
    check_unrst_property,
    check_unrst_multi_dates,
    check_grdecl,
    check_masked_index_ops,
]


def run_checks(testdata_root):
    """Run every registered check, returning a JSON-serializable result list.

    Each entry is ``{name, status, facts|error|traceback}``. Exceptions are
    captured (not raised) so one failing check never hides the others; the
    harness decides the process exit code from the statuses.
    """
    results = []
    for fn in CHECKS:
        entry = {"name": fn.__name__}
        try:
            entry["facts"] = fn(testdata_root) or {}
            entry["status"] = "pass"
        except Exception as exc:  # noqa: BLE001 - report, don't crash the harness
            import traceback

            entry["status"] = "fail"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["traceback"] = traceback.format_exc()
        results.append(entry)
    return results
