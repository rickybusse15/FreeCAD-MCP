# FreeCAD Setup

FreeCAD-MCP needs the `FreeCAD` Python module importable in the same interpreter that runs integration tests or real adapter operations.

## macOS

Common Homebrew checks:

```bash
brew install --cask freecad
which FreeCADCmd || true
find /Applications -name FreeCADCmd -o -name FreeCAD.so 2>/dev/null
```

Common app bundle paths:

```text
/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd
/Applications/FreeCAD.app/Contents/Resources/lib/FreeCAD.so
```

If `python3 -c "import FreeCAD"` fails, add the directory containing `FreeCAD.so` to `PYTHONPATH` before running FreeCAD-MCP tests:

```bash
export PYTHONPATH="/Applications/FreeCAD.app/Contents/Resources/lib:$PYTHONPATH"
freecad-mcp doctor --strict
python3 -m pytest -m freecad
```

FreeCAD macOS app bundles often use their own Python version. If your shell Python cannot import `FreeCAD.so`, run strict smoke tests through the bundled command:

```bash
freecad-mcp smoke-test --workspace /tmp/freecad-mcp-smoke --require-freecad --freecadcmd /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
```

## Linux

Package names vary by distribution:

```bash
sudo apt-get install freecad
which FreeCADCmd || which freecadcmd
find /usr -name FreeCAD.so 2>/dev/null | head
```

Typical module locations include:

```text
/usr/lib/freecad-python3/lib
/usr/lib/freecad/lib
/usr/lib/x86_64-linux-gnu/freecad/lib
```

Add the discovered library directory to `PYTHONPATH`:

```bash
export PYTHONPATH="/usr/lib/freecad-python3/lib:$PYTHONPATH"
freecad-mcp doctor --strict
python3 -m pytest -m freecad
```

## Workbench Path

For source checkout development, point FreeCAD at the workbench folder and package source:

```bash
export PYTHONPATH="/path/to/FreeCAD-MCP/src:$PYTHONPATH"
```

Then copy or symlink:

```text
/path/to/FreeCAD-MCP/src/freecad_mcp/workbench
```

into a FreeCAD `Mod/MCPDesignWorkbench` folder, or add it through FreeCAD's module search path. The package itself must remain importable because `InitGui.py` imports `freecad_mcp.workbench.commands`.
