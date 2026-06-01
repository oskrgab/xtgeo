#!/usr/bin/env bash
# In-container entrypoint: cross-compile xtgeo into an Emscripten wheel.
#
# Mounts (provided by `make wasm`):
#   /work/repo    read-only source checkout (incl. .git for setuptools_scm)
#   /work/output  writable directory the resulting wheel is copied into
set -euo pipefail

# Activate the pinned Emscripten toolchain.
# shellcheck disable=SC1091
source "${EMSDK}/emsdk_env.sh"

echo "==> Toolchain"
echo "    pyodide version    : ${XTGEO_PYODIDE_VERSION}"
echo "    emcc               : $(emcc --version | head -1)"
echo "    python (host)      : $(python --version)"
echo "    swig               : $(swig -version | grep -i version | head -1)"

# Work on a writable copy so the developer's checkout (mounted :ro) is never
# mutated by the WASM build profile or setuptools_scm.
BUILD_DIR=/build
rm -rf "${BUILD_DIR}"
cp -a /work/repo "${BUILD_DIR}"
cd "${BUILD_DIR}"

# The copied .git is owned by the host uid; allow setuptools_scm to read it.
git config --global --add safe.directory "${BUILD_DIR}"

echo "==> Applying WASM build profile (stripping unbuildable dependencies)"
python /usr/local/lib/xtgeo-wasm/apply_wasm_profile.py "${BUILD_DIR}/pyproject.toml"

echo "==> Cross-compiling with pyodide build"
pyodide build --outdir "${BUILD_DIR}/dist"

mkdir -p /work/output
wheel=$(ls "${BUILD_DIR}"/dist/*emscripten*wasm32.whl)
cp "${wheel}" /work/output/
echo "==> Wheel: $(basename "${wheel}")"
echo "==> Copied to mounted output directory"
