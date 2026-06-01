# xtgeo developer targets.
#
# WASM/Pyodide distribution (see docs/adr/0001-wasm-pyodide-distribution.md):
#   make wasm        build the Emscripten wheel in a pinned Docker image
#   make wasm-smoke  load the wheel in Node + Pyodide and assert `import xtgeo`
#   make wasm-all    build then smoke-test

WASM_DIR := wasm

# Single source of truth for all pinned WASM versions.
include $(WASM_DIR)/versions.env

WASM_IMAGE := xtgeo-wasm-builder:$(PYODIDE_VERSION)
WASM_OUTPUT := $(CURDIR)/dist/wasm

.PHONY: wasm wasm-image wasm-smoke wasm-all wasm-clean

wasm-image:
	docker build \
	  --build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	  --build-arg PYODIDE_VERSION=$(PYODIDE_VERSION) \
	  --build-arg EMSCRIPTEN_VERSION=$(EMSCRIPTEN_VERSION) \
	  --build-arg PYODIDE_BUILD_VERSION=$(PYODIDE_BUILD_VERSION) \
	  -t $(WASM_IMAGE) \
	  $(WASM_DIR)

wasm: wasm-image
	mkdir -p $(WASM_OUTPUT)
	docker run --rm \
	  -v $(CURDIR):/work/repo:ro \
	  -v $(WASM_OUTPUT):/work/output \
	  $(WASM_IMAGE)
	@echo "WASM wheel(s) in $(WASM_OUTPUT):"
	@ls -1 $(WASM_OUTPUT)/*.whl

wasm-smoke:
	$(WASM_DIR)/run_smoke_test.sh $(WASM_OUTPUT)

wasm-all: wasm wasm-smoke

wasm-clean:
	rm -rf $(WASM_OUTPUT)
