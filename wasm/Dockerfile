# Reproducible cross-compilation environment for the xtgeo WASM/Pyodide wheel.
#
# All versions are passed in as build args from wasm/versions.env (the single
# source of truth) by the `make wasm` target -- do not hard-code them here.
#
# The image pins, in lockstep:
#   * the host CPython (must match the Pyodide target's Python minor version)
#   * the Emscripten SDK (the wheel is ABI-locked to it)
#   * pyodide-build (the cross-compilation frontend)
#   * the Pyodide cross-build environment (headers + bundled numpy/scipy/...)

ARG PYTHON_VERSION=3.13.2
FROM python:${PYTHON_VERSION}-slim-bookworm

ARG PYODIDE_VERSION
ARG EMSCRIPTEN_VERSION
ARG PYODIDE_BUILD_VERSION

# Build tools: git (FetchContent of Eigen3/fmt + emsdk), cmake/ninja (the
# scikit-build-core backend), and xz/curl for emsdk downloads.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        cmake \
        ninja-build \
        swig \
        xz-utils \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Emscripten SDK, pinned to the version the Pyodide release expects --------
ENV EMSDK=/opt/emsdk
RUN git clone https://github.com/emscripten-core/emsdk.git ${EMSDK} \
    && cd ${EMSDK} \
    && ./emsdk install ${EMSCRIPTEN_VERSION} \
    && ./emsdk activate ${EMSCRIPTEN_VERSION}

# --- Cross-compilation frontend + cross-build environment ---------------------
RUN pip install --no-cache-dir \
        "pyodide-build[resolve]==${PYODIDE_BUILD_VERSION}" \
        tomlkit \
        packaging

# Download the pinned Pyodide cross-build environment (Python headers + the
# bundled scientific stack the wheel is ABI-locked against).
RUN pyodide xbuildenv install "${PYODIDE_VERSION}"

# Persist the pin so the build script and introspection can read it.
ENV XTGEO_PYODIDE_VERSION=${PYODIDE_VERSION}
ENV XTGEO_EMSCRIPTEN_VERSION=${EMSCRIPTEN_VERSION}

COPY build.sh /usr/local/bin/wasm-build
COPY apply_wasm_profile.py /usr/local/lib/xtgeo-wasm/apply_wasm_profile.py
RUN chmod +x /usr/local/bin/wasm-build

WORKDIR /work
ENTRYPOINT ["/usr/local/bin/wasm-build"]
