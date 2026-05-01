# Development

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Local Test Loop

```bash
python3 -m pytest
python3 -m pytest -m workbench
python3 -m pytest -m freecad
```

The default suite is designed to run without FreeCAD installed. FreeCAD-backed integration tests are marked `freecad` and skip unless the `FreeCAD` Python module is importable in the active interpreter.

## Running the MCP Server

```bash
freecad-mcp serve
```

Run this after installing the package in editable mode.

## Diagnostics and Smoke Test

```bash
freecad-mcp doctor
freecad-mcp verify-workbench
freecad-mcp doctor --strict
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke --require-freecad
```

`doctor --strict` exits non-zero when neither the `FreeCAD` Python module nor `FreeCADCmd/freecadcmd` can be found. `smoke-test` runs the basic bracket workflow in real FreeCAD mode when available and otherwise uses mock mode unless `--require-freecad` is set. On macOS app-bundle installs where the shell Python cannot import `FreeCAD.so`, `smoke-test --require-freecad` runs through `freecadcmd -P <package-path>` automatically. You can override discovery with:

```bash
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke --require-freecad --freecadcmd /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
```

## Build Checks

```bash
python3 -m build
python3 -m venv /tmp/freecad-mcp-wheel-venv
/tmp/freecad-mcp-wheel-venv/bin/python -m pip install dist/freecad_mcp-*.whl
/tmp/freecad-mcp-wheel-venv/bin/freecad-mcp doctor
```

## Workbench Installation

Install the full package into FreeCAD's Python environment or add this repo's `src/` directory to FreeCAD's `PYTHONPATH`, then add `src/freecad_mcp/workbench` to a FreeCAD module path or copy it into a FreeCAD `Mod/MCPDesignWorkbench` folder. The Workbench registers active-document commands and Qt-safe docks for parameters, rule checks, design history, and assembly status.

See `docs/FREECAD_SETUP.md` for platform-specific FreeCAD path discovery.
