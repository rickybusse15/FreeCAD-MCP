"""MCP server entrypoint."""

from __future__ import annotations

from typing import Any

from freecad_mcp.mcp_tools import TOOL_DESCRIPTIONS, ToolRegistry


def create_mcp_server(registry: ToolRegistry | None = None) -> Any:
    registry = registry or ToolRegistry()
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        return registry

    server = FastMCP("freecad-mcp")

    @server.tool(name="project.create", description=TOOL_DESCRIPTIONS["project.create"])
    def project_create(project_name: str, parameters: list[dict[str, Any]] | None = None, workspace: str | None = None) -> dict[str, Any]:
        """Create a new FreeCAD project document with optional spreadsheet parameters."""
        return registry.call("project.create", project_name=project_name, parameters=parameters, workspace=workspace)

    @server.tool(name="project.open", description=TOOL_DESCRIPTIONS["project.open"])
    def project_open(path: str) -> dict[str, Any]:
        """Open an existing FreeCAD project document."""
        return registry.call("project.open", path=path)

    @server.tool(name="project.save", description=TOOL_DESCRIPTIONS["project.save"])
    def project_save(path: str) -> dict[str, Any]:
        """Save the active or mock project document."""
        return registry.call("project.save", path=path)

    @server.tool(name="project.export", description=TOOL_DESCRIPTIONS["project.export"])
    def project_export(path: str, output_path: str, format: str) -> dict[str, Any]:
        """Export a project to STEP, STL, or DXF."""
        return registry.call("project.export", path=path, output_path=output_path, format=format)

    @server.tool(name="param.list", description=TOOL_DESCRIPTIONS["param.list"])
    def param_list(path: str) -> dict[str, Any]:
        """List spreadsheet-backed parameters for a project."""
        return registry.call("param.list", path=path)

    @server.tool(name="param.set", description=TOOL_DESCRIPTIONS["param.set"])
    def param_set(path: str, parameter: dict[str, Any]) -> dict[str, Any]:
        """Set one named spreadsheet parameter."""
        return registry.call("param.set", path=path, parameter=parameter)

    @server.tool(name="param.batch_set", description=TOOL_DESCRIPTIONS["param.batch_set"])
    def param_batch_set(path: str, parameters: list[dict[str, Any]]) -> dict[str, Any]:
        """Set multiple named spreadsheet parameters."""
        return registry.call("param.batch_set", path=path, parameters=parameters)

    @server.tool(name="param.validate", description=TOOL_DESCRIPTIONS["param.validate"])
    def param_validate(parameters: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate parameter names, units, values, and bounds."""
        return registry.call("param.validate", parameters=parameters)

    @server.tool(name="part.create_from_template", description=TOOL_DESCRIPTIONS["part.create_from_template"])
    def part_create_from_template(path: str, template_name: str) -> dict[str, Any]:
        """Generate an initial parametric part from a named template."""
        return registry.call("part.create_from_template", path=path, template_name=template_name)

    @server.tool(name="assembly.create", description=TOOL_DESCRIPTIONS["assembly.create"])
    def assembly_create(path: str, assembly_name: str) -> dict[str, Any]:
        """Create an assembly container in a project document."""
        return registry.call("assembly.create", path=path, assembly_name=assembly_name)

    @server.tool(name="assembly.add_part", description=TOOL_DESCRIPTIONS["assembly.add_part"])
    def assembly_add_part(path: str, part: dict[str, Any]) -> dict[str, Any]:
        """Add or update a part reference in the active assembly."""
        return registry.call("assembly.add_part", path=path, part=part)

    @server.tool(name="assembly.insert_link", description=TOOL_DESCRIPTIONS["assembly.insert_link"])
    def assembly_insert_link(path: str, part: dict[str, Any]) -> dict[str, Any]:
        """Insert or update a native App::Link in the active assembly."""
        return registry.call("assembly.insert_link", path=path, part=part)

    @server.tool(name="assembly.ground", description=TOOL_DESCRIPTIONS["assembly.ground"])
    def assembly_ground(path: str, part_id: str) -> dict[str, Any]:
        """Create a native grounded joint for an assembly part."""
        return registry.call("assembly.ground", path=path, part_id=part_id)

    @server.tool(name="assembly.mate", description=TOOL_DESCRIPTIONS["assembly.mate"])
    def assembly_mate(path: str, mate: dict[str, Any]) -> dict[str, Any]:
        """Add or update a mate between two assembly part references."""
        return registry.call("assembly.mate", path=path, mate=mate)

    @server.tool(name="assembly.joint.create", description=TOOL_DESCRIPTIONS["assembly.joint.create"])
    def assembly_joint_create(path: str, joint: dict[str, Any]) -> dict[str, Any]:
        """Create a native FreeCAD Assembly joint between two linked parts."""
        return registry.call("assembly.joint.create", path=path, joint=joint)

    @server.tool(name="assembly.joint.update", description=TOOL_DESCRIPTIONS["assembly.joint.update"])
    def assembly_joint_update(path: str, joint: dict[str, Any]) -> dict[str, Any]:
        """Replace an existing native FreeCAD Assembly joint."""
        return registry.call("assembly.joint.update", path=path, joint=joint)

    @server.tool(name="assembly.joint.delete", description=TOOL_DESCRIPTIONS["assembly.joint.delete"])
    def assembly_joint_delete(path: str, joint_id: str) -> dict[str, Any]:
        """Delete a native FreeCAD Assembly joint."""
        return registry.call("assembly.joint.delete", path=path, joint_id=joint_id)

    @server.tool(name="assembly.joint.list", description=TOOL_DESCRIPTIONS["assembly.joint.list"])
    def assembly_joint_list(path: str) -> dict[str, Any]:
        """List native FreeCAD Assembly joints tracked for the active assembly."""
        return registry.call("assembly.joint.list", path=path)

    @server.tool(name="assembly.solve", description=TOOL_DESCRIPTIONS["assembly.solve"])
    def assembly_solve(path: str) -> dict[str, Any]:
        """Run the native FreeCAD Assembly solver/recompute path."""
        return registry.call("assembly.solve", path=path)

    @server.tool(name="assembly.bom", description=TOOL_DESCRIPTIONS["assembly.bom"])
    def assembly_bom(path: str) -> dict[str, Any]:
        """Return a bill of materials for the active assembly."""
        return registry.call("assembly.bom", path=path)

    @server.tool(name="assembly.explode_view", description=TOOL_DESCRIPTIONS["assembly.explode_view"])
    def assembly_explode_view(path: str, distance_mm: float = 25) -> dict[str, Any]:
        """Compute and persist an exploded-view offset plan for the active assembly."""
        return registry.call("assembly.explode_view", path=path, distance_mm=distance_mm)

    @server.tool(name="design.check_rules", description=TOOL_DESCRIPTIONS["design.check_rules"])
    def design_check_rules(parameters: list[dict[str, Any]]) -> dict[str, Any]:
        """Run manufacturability and parameter validation rules."""
        return registry.call("design.check_rules", parameters=parameters)

    @server.tool(name="assistant.plan", description=TOOL_DESCRIPTIONS["assistant.plan"])
    def assistant_plan(prompt: str, path: str | None = None) -> dict[str, Any]:
        """Convert a local workbench prompt into deterministic MCP tool actions."""
        return registry.call("assistant.plan", prompt=prompt, path=path)

    @server.tool(name="assistant.execute", description=TOOL_DESCRIPTIONS["assistant.execute"])
    def assistant_execute(prompt: str, path: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        """Execute a recognized local workbench prompt through MCP service actions."""
        return registry.call("assistant.execute", prompt=prompt, path=path, workspace=workspace)

    @server.tool(name="runtime.status", description=TOOL_DESCRIPTIONS["runtime.status"])
    def runtime_status() -> dict[str, Any]:
        """Report whether the adapter is using real FreeCAD, mock mode, or unavailable real mode."""
        return registry.call("runtime.status")

    return server


def main() -> None:
    server = create_mcp_server()
    if hasattr(server, "run"):
        server.run()
    else:
        print("mcp package is not installed; available tools:")
        for name in server.names:
            print(f"- {name}")


if __name__ == "__main__":
    main()
