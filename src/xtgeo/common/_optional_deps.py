"""Lazy handling of optional third-party dependencies.

Some dependencies are not available in every distribution of xtgeo. In
particular the WASM/Pyodide wheel (see
``docs/adr/0001-wasm-pyodide-distribution.md``) excludes ``segyio``,
``gstools``, ``hdf5plugin`` and ``xtgeoviz`` because they cannot be
cross-compiled for / are absent from Pyodide.

Importing those packages eagerly at module load time would make a bare
``import xtgeo`` fail in such an environment. Instead we import them through
:func:`optional_import`, which defers the failure until the dependent feature
is actually used and then raises a clear, actionable error.
"""

from __future__ import annotations

import importlib
from types import ModuleType


class MissingOptionalDependency:
    """Placeholder returned when an optional dependency is unavailable.

    Any attribute access or call raises :class:`ImportError` with a clear
    message, so a WASM/Pyodide user who calls an excluded feature gets a hard,
    explanatory error instead of a confusing ``AttributeError`` -- while plain
    ``import xtgeo`` keeps working.
    """

    def __init__(self, name: str, error: BaseException) -> None:
        self._name = name
        self._error = error

    def _fail(self) -> None:
        raise ImportError(
            f"The optional dependency {self._name!r} is required for this "
            f"feature but is not available in this environment. It is excluded "
            f"from the WASM/Pyodide build of xtgeo "
            f"(see docs/adr/0001-wasm-pyodide-distribution.md)."
        ) from self._error

    def __getattr__(self, _attr: str):
        self._fail()

    def __call__(self, *_args, **_kwargs):
        self._fail()


def optional_import(name: str) -> ModuleType | MissingOptionalDependency:
    """Import ``name`` if present, else return a failing placeholder.

    The placeholder lets ``import xtgeo`` succeed in environments where the
    dependency is absent (e.g. Pyodide); using it raises a clear error.
    """
    try:
        return importlib.import_module(name)
    except ImportError as err:
        return MissingOptionalDependency(name, err)
