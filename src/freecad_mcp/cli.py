"""Command-line interface for FreeCAD-MCP."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from freecad_mcp.diagnostics import doctor_report, print_json, smoke_test, smoke_test_via_freecadcmd, workbench_verify_report
from freecad_mcp.server import create_mcp_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="freecad-mcp")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Run the MCP server")

    doctor_parser = subparsers.add_parser("doctor", help="Report Python, MCP, FreeCAD, exporter, and Workbench status")
    doctor_parser.add_argument("--strict", action="store_true", help="Exit non-zero unless FreeCAD is importable")

    smoke_parser = subparsers.add_parser("smoke-test", help="Run the basic bracket workflow")
    smoke_parser.add_argument("--workspace", default="/tmp/freecad-mcp-smoke", help="Workspace for generated files")
    smoke_parser.add_argument("--require-freecad", action="store_true", help="Fail instead of using mock mode")
    smoke_parser.add_argument("--freecadcmd", help="Path to FreeCADCmd/freecadcmd for strict FreeCAD smoke tests")

    subparsers.add_parser("catalog", help="Print the local MCP tool catalog")
    subparsers.add_parser("verify-workbench", help="Verify FreeCAD Workbench addon readiness")

    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "serve":
        server = create_mcp_server()
        if hasattr(server, "run"):
            server.run()
            return 0
        print("mcp package is not installed; available tools:")
        for name in server.names:
            print(f"- {name}")
        return 1

    if command == "doctor":
        report = doctor_report()
        if args.strict and not report["freecad"]["usable"]:
            report["ok"] = False
        print_json(report)
        if args.strict and not report["freecad"]["usable"]:
            return 2
        return 0 if report["ok"] else 1

    if command == "smoke-test":
        try:
            if args.require_freecad and not doctor_report()["freecad"]["python_module_importable"]:
                report = smoke_test_via_freecadcmd(Path(args.workspace), freecadcmd=args.freecadcmd)
            else:
                report = smoke_test(Path(args.workspace), require_freecad=args.require_freecad)
        except Exception as exc:
            print_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
            return 2
        print_json(report)
        if args.require_freecad and report["mode"] != "freecad":
            return 2
        return 0

    if command == "catalog":
        from freecad_mcp.mcp_tools import ToolRegistry

        print_json(ToolRegistry().as_catalog())
        return 0

    if command == "verify-workbench":
        report = workbench_verify_report()
        print_json(report)
        return 0 if report["ok"] else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
