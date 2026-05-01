# FreeCAD-MCP
MCP integration for FreeCAD

## Current State
This branch contains the first productized FreeCAD-MCP Workbench path:

- MCP server with schema-validated tools for projects, parameters, template parts, exports, rule checks, native assemblies, and local prompt actions.
- Mock mode remains available for tests, CI, and explicit CLI fallback.
- Real FreeCAD adapter path for `.FCStd` create/open/save, spreadsheet parameters, PartDesign bracket generation, native `Assembly::AssemblyObject`, `App::Link`, native joints, solve, BOM, recompute, and STEP/STL/DXF export.
- FreeCAD Workbench with document-bound session state, active-document commands, editable parameter/rule/assistant/assembly docks, and packaged-addon metadata.
- CLI diagnostics, workbench verification, and smoke test:

```bash
freecad-mcp doctor
freecad-mcp verify-workbench
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke
```

FreeCAD-backed tests are marked `freecad` and skip unless FreeCAD is importable in the active Python interpreter. On macOS app-bundle installs, use the bundled command path for real smoke runs:

```bash
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke --require-freecad --freecadcmd /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
```

## Workbench Addon

The repository root includes `package.xml`, `Init.py`, `InitGui.py`, and an icon so it can be copied or symlinked into FreeCAD's user `Mod/MCPDesignWorkbench` directory. The root wrappers add `src/` to `sys.path` and load `freecad_mcp.workbench`.

## Planning
- `ARCHITECTURE_PLAN.md`: Visual, workbench-first architecture for parametric parts and assemblies.
- `EXECUTION_WORKSTREAMS.md`: Parallel multi-agent execution plan, interfile communication contracts, and artifact/data handoff structure.

## Developer Docs
- `docs/DEVELOPMENT.md`: local install, test, build, and CLI workflow.
- `docs/FREECAD_SETUP.md`: macOS/Linux FreeCAD Python and Workbench setup.
