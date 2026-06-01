"""Public-API smoke checks for the xtgeo WASM wheel, run inside Pyodide.

Each check is a function ``check_*(root)`` that asserts on externally
observable behavior through xtgeo's *public* API -- grid/property dimensions,
known property means, masked-array shapes and index-space operations. Nothing
is mocked and no build internals are touched: this is exactly what a browser
consumer would observe, just executing inside the compiled WASM wheel.

Two layers of coverage:

* The pure-Python read path (resfo-backed EGRID/INIT/UNRST/GRDECL parsing). It
  makes no native calls, but it runs inside the wheel whose native modules
  (_cxtgeo, _internal) loaded at import time.
* The native geometry operations (``Grid.get_dz``/``get_dx``/``get_dy``, the
  ``surf_slice_grd3d`` 3D->2D sampler, ``get_bulk_volume`` /
  ``get_phase_volumes`` volumetrics, and the ``get_ijk_from_points`` XY->IJK
  lookup). These actually *execute* the cross-compiled _cxtgeo / _internal
  code -- the operations resfo and pure Python cannot provide, and the reason
  the native cross-compile exists at all.

Later WASM slices extend coverage by appending a function to ``CHECKS``. The
harness in ``smoke_test.mjs`` runs every registered check and reports pass/fail.

Fixtures come from the equinor/xtgeo-testdata REEK dataset, mirroring the paths
and expected values used by the native ``tests/test_grid3d`` and
``tests/test_surface`` suites.
"""

from __future__ import annotations

import numpy as np
import numpy.ma as ma

import xtgeo

# REEK fixtures, relative to the mounted test-data root.
EGRID = "3dgrids/reek/REEK.EGRID"
INIT = "3dgrids/reek/REEK.INIT"
UNRST = "3dgrids/reek/REEK.UNRST"
GRDECL = "3dgrids/reek3/reek_sim.grdecl"  # ASCII Eclipse deck
RTOP = "surfaces/reek/1/topreek_rota.gri"  # geo-referenced top-reek map

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


# --------------------------------------------------------------------------- #
# Native geometry checks (WASM slice 3).
#
# Everything below actually *executes* the cross-compiled native modules
# (_cxtgeo / _internal), not merely imports them: cell-edge metrics, the
# C surf_slice_grd3d sampler, the C++ hexahedron volume integrator, and the
# cell-search behind XY->IJK lookup. This is the slice that justifies the whole
# native cross-compile -- these operations are exactly what resfo and the
# pure-Python read path cannot provide. Assertions stay on observable
# values/shapes through xtgeo's public API; reference numbers mirror the native
# tests/test_grid3d and tests/test_surface suites on the same REEK fixtures.
# --------------------------------------------------------------------------- #


def check_cell_dimensions(root):
    """Native get_dz/get_dx/get_dy return correctly shaped, positive metrics.

    Cell thicknesses and lateral edge lengths come from the native geometry
    code; a browser user expects physically sane (strictly positive) values
    over the active cells, shaped like the grid.
    """
    grd = _egrid(root)

    facts = {}
    for label, prop in (
        ("dz", grd.get_dz()),
        ("dx", grd.get_dx()),
        ("dy", grd.get_dy()),
    ):
        vals = prop.values
        assert isinstance(vals, ma.MaskedArray), f"{label}: {type(vals)}"
        assert vals.shape == REEK_DIMS, f"{label} shape {vals.shape}"
        active = vals.compressed()
        assert active.size > 0, f"{label}: no active cells"
        assert np.all(active > 0.0), f"{label}: non-positive edge length"
        facts[f"{label}_mean"] = float(active.mean())
        facts[f"{label}_min"] = float(active.min())

    # REEK cells are thin in Z (a few metres) and wide laterally (~150 m); use
    # generous bounds so the check tracks "physically sane", not a regression
    # pin on a specific build's averaging.
    assert 0.5 < facts["dz_mean"] < 20.0, facts["dz_mean"]
    assert 50.0 < facts["dx_mean"] < 500.0, facts["dx_mean"]
    assert 50.0 < facts["dy_mean"] < 500.0, facts["dy_mean"]
    return facts


def check_surf_slice_grd3d(root):
    """Sample a 3D property onto a geo-referenced RegularSurface (native path).

    ``RegularSurface.slice_grid3d`` drives the native ``surf_slice_grd3d``
    sampler: for every map node it finds the intersected cell in real-world
    coordinates and reads the property there. We sample PORO at a constant
    depth and assert the map keeps the surface geometry and is populated with
    sane porosity, mirroring tests/test_surface/test_regular_surface_vs_grd3d.
    """
    grd = _egrid(root)
    surf = xtgeo.surface_from_file(f"{root}/{RTOP}")
    poro = xtgeo.gridproperty_from_file(
        f"{root}/{INIT}", fformat="init", name="PORO", grid=grd
    )

    ncol, nrow = surf.ncol, surf.nrow
    surf.values = 1700.0  # constant slicing depth (TVDSS) within the reservoir
    surf.slice_grid3d(grd, poro)

    assert (surf.ncol, surf.nrow) == (ncol, nrow), (surf.ncol, surf.nrow)
    assert isinstance(surf.values, ma.MaskedArray), type(surf.values)

    sampled = surf.values.count()  # nodes that actually hit a cell
    assert sampled > 0, "no surface nodes intersected the grid"
    assert sampled < surf.values.size, "expected nodes outside the grid footprint"

    mean = float(surf.values.mean())
    assert 0.0 < mean < 1.0, mean  # a porosity fraction
    assert abs(mean - 0.1667) < 2.0e-2, mean  # known REEK PORO map mean
    return {
        "surface_shape": [ncol, nrow],
        "sampled_nodes": int(sampled),
        "PORO_map_mean": mean,
    }


def check_bulk_and_phase_volumes(root):
    """Native volumetrics: get_bulk_volume and get_phase_volumes.

    Bulk volume integrates each corner-point cell (the native C++ hexahedron
    decomposition). The phase split (gas/oil/water about given contacts) must
    partition that same bulk volume exactly -- a strong, build-independent
    invariant -- so we assert positivity, shape, and gas+oil+water == bulk.
    """
    grd = _egrid(root)

    bulk = grd.get_bulk_volume()
    assert isinstance(bulk.values, ma.MaskedArray), type(bulk.values)
    assert bulk.values.shape == REEK_DIMS, bulk.values.shape
    bulk_active = bulk.values.compressed()
    assert bulk_active.size > 0, "no active cells"
    assert np.all(bulk_active > 0.0), "non-positive bulk volume"
    bulk_total = float(bulk_active.sum())

    # Contacts spanning the reservoir so all three phases are represented.
    gas, oil, water = grd.get_phase_volumes(water_contact=1700.0, gas_contact=1600.0)
    gsum = float(gas.values.sum())
    osum = float(oil.values.sum())
    wsum = float(water.values.sum())
    for label, value in (("gas", gsum), ("oil", osum), ("water", wsum)):
        assert value > 0.0, f"{label} volume not positive: {value}"

    phase_total = gsum + osum + wsum
    # The phase split is a partition of the bulk volume; relative match.
    assert abs(phase_total - bulk_total) <= 1.0e-6 * bulk_total, (
        phase_total,
        bulk_total,
    )
    return {
        "bulk_total": bulk_total,
        "gas_total": gsum,
        "oil_total": osum,
        "water_total": wsum,
    }


def check_ijk_from_points(root):
    """Native XY(Z)->IJK lookup maps a known cell centre back to that cell.

    ``get_ijk_from_points`` runs the native cell search in real-world space.
    We take the geo-referenced centre of a chosen active cell (via get_xyz) and
    feed it back: a robust, fixture-independent round-trip that proves the
    lookup honours the grid's actual coordinates rather than index arithmetic.
    """
    grd = _egrid(root)

    target = (20, 30, 7)  # 1-based (I, J, K) of a known active cell
    xp, yp, zp = grd.get_xyz(asmasked=False)
    i, j, k = target
    x = float(xp.values[i - 1, j - 1, k - 1])
    y = float(yp.values[i - 1, j - 1, k - 1])
    z = float(zp.values[i - 1, j - 1, k - 1])

    points = xtgeo.Points([(x, y, z)])
    df = grd.get_ijk_from_points(points)
    found = (int(df["IX"][0]), int(df["JY"][0]), int(df["KZ"][0]))
    assert found == target, f"{found} != {target}"
    return {"point": [x, y, z], "target_ijk": list(target), "found_ijk": list(found)}


# Registry of checks, run in order by the Node harness. Append here in later
# slices to extend coverage.
CHECKS = [
    check_import,
    check_egrid_dimensions,
    check_init_property,
    check_unrst_property,
    check_unrst_multi_dates,
    check_grdecl,
    check_masked_index_ops,
    # Native geometry operations (slice 3).
    check_cell_dimensions,
    check_surf_slice_grd3d,
    check_bulk_and_phase_volumes,
    check_ijk_from_points,
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
