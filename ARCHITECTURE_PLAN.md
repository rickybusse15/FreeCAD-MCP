# FreeCAD MCP Server Plan for Parametric Parts & Assemblies

## 1) Goals
- Provide an MCP server that lets AI agents create, edit, analyze, and export **FreeCAD** models.
- Make all models **fully parametric** and **readable** by driving dimensions from spreadsheets.
- Support both **single parts** and **multi-part assemblies** with traceable design intent.
- Add intelligent design consideration through rule checks, optimization suggestions, and manufacturability feedback.
- Deliver a **usable visual product**: either a **standalone desktop app** or a **FreeCAD Workbench plugin** (or both), not just chat output.

## 2) Product Form Factors (Decision First)

### Option A — FreeCAD Workbench (Recommended)
- Implement as `MCPDesignWorkbench` inside FreeCAD.
- Native use of FreeCAD 3D viewer, tree, property panels, and recompute workflow.
- Lowest integration risk for parametric editing and assemblies.

### Option B — Standalone Desktop App
- Python desktop app (Qt/PySide) embedding FreeCAD as backend.
- Custom UI around design prompts, parameter grids, rule checks, and model viewer.
- Better product branding/packaging, but higher engineering effort.

### Option C — Hybrid
- Shared backend engine plus:
  - Workbench frontend for advanced CAD users.
  - Standalone frontend for guided workflows.

## 3) Recommended Architecture

### 3.1 Shared Core (Used by Workbench and/or Standalone)
- **MCP Transport/API Layer**
  - MCP tool registration, request validation, auth/session handling.
- **Design Orchestration Layer**
  - Converts user intent into structured CAD operations.
  - Maintains operation graph (create/update/delete features).
- **FreeCAD Adapter Layer**
  - Wraps FreeCAD Python APIs (PartDesign, Sketcher, Spreadsheet, Assembly).
  - Handles document lifecycle, recompute, save/load, export.
- **Validation & Intelligence Layer**
  - Constraint checks (over/under constrained sketches).
  - Design rules: min wall thickness, edge distance, clearance, fillet feasibility.
  - Suggestions: material-aware hints and tolerance warnings.
- **Persistence Layer**
  - `.FCStd` files, templates, parameter snapshots, and logs.

### 3.2 UI Layer Requirements (Viewer-Centric)
- **3D Viewport** with rotate/pan/zoom, sectioning, and fit-all.
- **Model Tree** showing parts, bodies, sketches, and features.
- **Parameter Grid** (spreadsheet-like) with name, unit, bounds, description.
- **Validation Panel** listing warnings/errors and impacted features.
- **Design Intent Panel** showing AI-generated rationale and change history.
- **Assembly Panel** for mates, constraints, BOM, and exploded view controls.

## 4) FreeCAD Workbench Plan (Primary Path)

### 4.1 Workbench Structure
- `Init.py` / `InitGui.py` for FreeCAD registration.
- Command modules:
  - `CmdCreateProject`
  - `CmdGeneratePart`
  - `CmdRunRuleCheck`
  - `CmdSyncMCP`
- Dock widgets:
  - `ParameterEditorDock`
  - `RuleCheckDock`
  - `DesignAssistantDock`
  - `AssemblyDock`

### 4.2 User Workflow in Workbench
1. Create/open project.
2. Choose template part or assembly.
3. Edit named spreadsheet parameters in the parameter dock.
4. Recompute and visualize directly in FreeCAD viewer.
5. Run rule checks and apply suggestions.
6. Save as `.FCStd` and export STEP/STL/DXF.

### 4.3 Workbench UX Rules
- Never hide raw FreeCAD objects from users.
- All geometry-driving values must trace to spreadsheet parameters.
- Clicking a rule warning highlights corresponding geometry.
- Parameter edits should show immediate preview after recompute.

## 5) Standalone App Plan (Alternative Path)

### 5.1 Standalone Components
- Frontend: PySide6 Qt app.
- Viewer: embedded 3D scene driven by FreeCAD document updates.
- Backend: same orchestration/validation layers as workbench.
- Local MCP bridge process for tool invocation.

### 5.2 Standalone UX
- Wizard-style design creation for non-expert users.
- Guided parameter forms mapped to internal spreadsheet cells.
- Side-by-side: parameter editor, 3D viewer, and warnings panel.

## 6) Domain Model (Canonical Objects)
- **Project**: multiple parts + optional assembly + metadata.
- **PartModel**: spreadsheet, sketches, features, bodies, properties.
- **AssemblyModel**: part refs, mates, interfaces, BOM.
- **ParameterSet**: typed values, units, bounds, descriptions.
- **DesignRuleSet**: rule definitions and severities.
- **UIState**: selected object, viewer camera, expanded tree nodes, filter states.

## 7) Parameter Strategy (Spreadsheet-Centric)

### 7.1 Naming Convention
- Prefix by scope:
  - `g_` = global assembly-level.
  - `p_` = part-level.
  - `m_` = manufacturing/tolerance.
- Examples:
  - `p_base_len_mm`, `p_base_w_mm`, `p_thickness_mm`, `m_clearance_fit_mm`.

### 7.2 Spreadsheet Layout Standard
Columns:
1. `Name`
2. `Expression`
3. `Unit`
4. `Value`
5. `Min`
6. `Max`
7. `Description`
8. `Category`

Rules:
- Every driven dimension references `Spreadsheet.<Name>`.
- No unnamed sketch dimensions.
- Every parameter includes bounds and description.

### 7.3 UI Binding Rules
- Every parameter row maps bi-directionally between spreadsheet and UI grid.
- Invalid entries are blocked before recompute.
- Unit conversion is displayed but canonical storage is mm/deg.

## 8) Assembly Approach
- Use FreeCAD assembly APIs compatible with target stable release.
- Assembly spreadsheet defines interfaces (pitch, offsets, envelopes).
- Parts consume interface values via linked expressions.
- Mates use named datum planes/axes for robust regeneration.

## 9) MCP Tooling Surface (UI + API)

### 9.1 Project/Document Tools
- `project.create`, `project.open`, `project.save`, `project.export`

### 9.2 Parameter Tools
- `param.list`, `param.set`, `param.batch_set`, `param.validate`

### 9.3 Modeling Tools
- `part.create_from_template`, `sketch.create`, `sketch.add_profile`
- `feature.pad`, `feature.pocket`, `feature.fillet`, `feature.chamfer`

### 9.4 Assembly Tools
- `assembly.create`, `assembly.add_part`, `assembly.mate`, `assembly.bom`, `assembly.explode_view`

### 9.5 UX/Viewer Tools
- `viewer.focus_object`
- `viewer.section_plane`
- `viewer.capture_snapshot`
- `ui.select_parameter`
- `ui.show_rule_violation`

### 9.6 Intelligence Tools
- `design.check_rules`
- `design.optimize_parameter`
- `design.suggest_improvements`

## 10) Safety, Robustness, Traceability
- Transaction model per command:
  1. snapshot,
  2. apply,
  3. recompute,
  4. validate,
  5. commit/rollback.
- Structured logs for tools, parameters, features, and rule outcomes.
- Crash-safe autosave after successful transactions.
- Undo/redo integration with FreeCAD command stack when in workbench mode.

## 11) Implementation Phases (Updated for Usability)

### Phase 1 — Workbench Shell + Viewer Integration
- Build `MCPDesignWorkbench` registration and toolbar commands.
- Add parameter dock bound to spreadsheet.
- Confirm live model viewing and recompute loop in FreeCAD.

### Phase 2 — Parametric Part Authoring
- Template-driven part generation.
- Feature library and parameter validation.
- Export support (STEP/STL/DXF).

### Phase 3 — Assembly + BOM + Visual Controls
- Assembly creation/mating.
- Exploded view controls and BOM panel.
- Cross-part linked parameters.

### Phase 4 — Intelligent Design Assistance
- Rule engine with configurable thresholds.
- Suggestion panel with geometry highlighting.
- Parameter sweeps and scored alternatives.

### Phase 5 — Standalone Packaging (Optional)
- Reuse shared backend in PySide app.
- Bundle installer and project templates.
- Add guided workflows for novice users.

## 12) Test Strategy
- **Unit**: parameter parsing, units, bounds, rule logic.
- **Integration**: part/assembly generation via MCP commands.
- **UI automation**: parameter edits reflect in viewer and tree.
- **Golden models**: verify mass/volume/key dimensions.
- **Regression**: deterministic rebuild from saved parameter snapshots.

## 13) Deliverables
- FreeCAD workbench package (primary deliverable).
- MCP server with documented schema.
- Parametric templates for parts/assemblies.
- Example assembly with top-level spreadsheet and BOM.
- Optional standalone app package sharing same backend.

## 14) Definition of Done
- Solution is usable through a visual interface (workbench and/or standalone app).
- Every geometry-driving number is a named spreadsheet parameter.
- Assemblies rebuild after top-level edits without manual fixes.
- Rule checker flags critical manufacturability issues in UI.
- Export and viewer interactions work for validated configurations.
- Logs explain automated decisions and changed parameters/features.

## 15) Multi-Agent Execution
- Execution is split into parallel workstreams with explicit contracts and artifact handoffs.
- See `EXECUTION_WORKSTREAMS.md` for team partitioning, repository structure, JSON schemas, artifact manifest expectations, and merge gates.
- All subsystem communication must occur via versioned files under `contracts/` and `artifacts/` to keep teams decoupled.
