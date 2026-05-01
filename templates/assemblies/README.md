# Assembly Templates

Assembly templates are represented as native FreeCAD Assembly objects with MCP metadata stored only for traceability.
The current implementation supports:

- `assembly.create` for creating a named assembly container.
- `assembly.insert_link` and the compatibility `assembly.add_part` alias for native `App::Link` insertion.
- `assembly.ground` for native grounded joints.
- `assembly.joint.create/update/delete/list` and the compatibility `assembly.mate` alias for native joint records.
- `assembly.solve` for native assembly recompute/solve.
- `assembly.bom` for deterministic bill-of-materials output.
- `assembly.explode_view` for visual exploded-view offsets.

Templates should keep named part IDs and interface references stable so prompt-to-actions and UI forms can create repeatable joints.
