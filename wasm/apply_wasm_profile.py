#!/usr/bin/env python3
"""Apply the WASM build profile to a pyproject.toml in place.

The WASM/Pyodide wheel cannot ship a handful of install dependencies that are
either impossible to cross-compile for Emscripten or simply absent from
Pyodide. This script strips them from ``[project].dependencies`` so the wheel's
metadata resolves under ``micropip.install`` (see
``docs/adr/0001-wasm-pyodide-distribution.md``).

It is run by the WASM build *against a copy of the source tree inside the build
container*, never against the developer's checkout. The runtime guards in
``xtgeo.common._optional_deps`` make ``import xtgeo`` survive the absence of
these packages; this script only fixes the *declared* metadata.

The stripped set is the single source of truth for "what the WASM profile drops".
"""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.requirements import Requirement

try:
    import tomlkit
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("apply_wasm_profile.py requires 'tomlkit' (install it in the builder)")

# Dependencies excluded from the WASM/Pyodide wheel. Keep this list aligned with
# the lazy import guards in src/xtgeo/common/_optional_deps.py and ADR-0001.
WASM_EXCLUDED_DEPENDENCIES = frozenset(
    {
        "segyio",  # native C SEG-Y reader, no Emscripten build
        "gstools",  # Cython, absent from Pyodide
        "xtgeoviz",  # plotting stack, absent from Pyodide
        "hdf5plugin",  # HDF5 compression plugins, absent from Pyodide
    }
)


def strip_dependencies(pyproject_path: Path) -> list[str]:
    """Remove the excluded dependencies from pyproject.toml in place.

    Returns the list of dependency strings that were removed.
    """
    doc = tomlkit.parse(pyproject_path.read_text())
    dependencies = doc["project"]["dependencies"]

    kept = tomlkit.array()
    kept.multiline(True)
    removed: list[str] = []
    for dep in dependencies:
        name = Requirement(str(dep)).name.lower().replace("_", "-")
        if name in {n.lower().replace("_", "-") for n in WASM_EXCLUDED_DEPENDENCIES}:
            removed.append(str(dep))
        else:
            kept.append(str(dep))

    doc["project"]["dependencies"] = kept
    pyproject_path.write_text(tomlkit.dumps(doc))
    return removed


def main() -> int:
    pyproject_path = Path(sys.argv[1] if len(sys.argv) > 1 else "pyproject.toml")
    if not pyproject_path.is_file():
        sys.exit(f"pyproject.toml not found at {pyproject_path}")

    removed = strip_dependencies(pyproject_path)
    print(f"WASM profile applied to {pyproject_path}")
    print(f"  stripped {len(removed)} dependencies: {', '.join(removed) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
