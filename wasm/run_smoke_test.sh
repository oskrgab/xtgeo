#!/usr/bin/env bash
# Run the Node + Pyodide smoke test against a built WASM wheel.
#
# Installs the Pyodide runtime at the pinned version (versions.env) and loads
# the wheel exactly as a consumer would.
#
# Usage: run_smoke_test.sh [output-dir-containing-wheel]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/versions.env"

OUTDIR="${1:-${HERE}/../dist/wasm}"
wheel=$(ls "${OUTDIR}"/*emscripten*wasm32.whl 2>/dev/null | head -1 || true)
if [[ -z "${wheel}" ]]; then
    echo "No emscripten_*_wasm32 wheel found in ${OUTDIR}. Run 'make wasm' first." >&2
    exit 1
fi

cd "${HERE}"
echo "==> Installing pyodide@${PYODIDE_VERSION} (Node runtime)"
npm install --no-save --no-audit --no-fund "pyodide@${PYODIDE_VERSION}"

echo "==> Running smoke test"
node smoke_test.mjs "${wheel}"
