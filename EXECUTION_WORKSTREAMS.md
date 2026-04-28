# Multi-Agent Execution Plan and Interfile Contracts

## 1) Parallel Workstreams (Simultaneously Executable)

### WS1 — MCP Protocol & API Contract Team
**Owns**
- MCP tool schema and request/response contracts.
- Versioning for API payloads.

**Inputs**
- `contracts/param.schema.json`
- `contracts/feature.schema.json`

**Outputs**
- `contracts/mcp_tools.schema.json`
- `contracts/api_examples/*.json`

### WS2 — FreeCAD Adapter Team
**Owns**
- FreeCAD Python integration for sketches, features, spreadsheets, assemblies.

**Inputs**
- `contracts/mcp_tools.schema.json`
- `contracts/feature.schema.json`

**Outputs**
- `src/adapter/freecad_adapter.py`
- `artifacts/recompute_report.json`

### WS3 — Workbench UI Team
**Owns**
- Workbench registration, commands, docks, and viewer interaction.

**Inputs**
- `contracts/ui_events.schema.json`
- `contracts/mcp_tools.schema.json`
- `artifacts/recompute_report.json`

**Outputs**
- `src/workbench/Init.py`
- `src/workbench/InitGui.py`
- `src/workbench/docks/*.py`
- `artifacts/ui_snapshot_manifest.json`

### WS4 — Rules/Intelligence Team
**Owns**
- Rule engine, scoring, suggestion logic.

**Inputs**
- `contracts/rules.schema.json`
- `data/material_rules/*.yaml`
- `artifacts/recompute_report.json`

**Outputs**
- `src/intelligence/rule_engine.py`
- `artifacts/rule_results.json`
- `artifacts/suggestions.json`

### WS5 — Templates/Parameter Library Team
**Owns**
- Parametric templates and spreadsheet defaults.

**Inputs**
- `contracts/param.schema.json`

**Outputs**
- `templates/parts/*.fcstd`
- `templates/assemblies/*.fcstd`
- `templates/params/*.csv`

### WS6 — Integration/QA Team
**Owns**
- End-to-end tests, golden models, regression snapshots.

**Inputs**
- Outputs from WS1–WS5.

**Outputs**
- `tests/integration/*.py`
- `tests/golden/*.json`
- `artifacts/test_report.json`

## 2) Interfile Communication Structure

## Repository Layout
```text
/contracts
  mcp_tools.schema.json
  param.schema.json
  feature.schema.json
  ui_events.schema.json
  rules.schema.json
  manifest.schema.json

/data
  material_rules/*.yaml

/src
  /adapter
  /workbench
  /intelligence
  /orchestration

/templates
  /parts
  /assemblies
  /params

/artifacts
  manifest.json
  recompute_report.json
  rule_results.json
  suggestions.json
  ui_snapshot_manifest.json
  test_report.json
```

## 3) Data Presentation Contracts Between Systems

### 3.1 Global Artifact Manifest
File: `artifacts/manifest.json`
- Purpose: single discovery file for latest outputs.
- Contains:
  - `artifact_name`
  - `version`
  - `producer_workstream`
  - `created_at_utc`
  - `input_hashes`
  - `path`

### 3.2 Parameter Payload (`param.schema.json`)
- `name` (string, snake_case)
- `unit` (`mm|deg|count|string|bool`)
- `value` (number|string|bool)
- `min`/`max` (number|null)
- `description` (string)
- `category` (string)
- `source` (`template|user|rule_engine`)

### 3.3 Feature Command Payload (`feature.schema.json`)
- `feature_id` (uuid)
- `feature_type` (`pad|pocket|fillet|chamfer|pattern`)
- `references` (array of topology refs)
- `parameters` (map of `Spreadsheet.<name>` expressions)
- `rollback_on_fail` (bool)

### 3.4 Recompute Report (`recompute_report.json`)
- `doc_id`
- `recompute_success`
- `duration_ms`
- `topology_changes`
- `constraint_status`
- `errors[]`

### 3.5 Rule Results (`rule_results.json`)
- `rule_id`
- `severity` (`info|warn|error`)
- `entity_ref`
- `message`
- `recommended_fix` (optional)

### 3.6 UI Event Payload (`ui_events.schema.json`)
- `event_id`
- `event_type` (`parameter_selected|rule_clicked|viewer_focus`)
- `entity_ref`
- `timestamp_utc`

## 4) Coordination Model for Multiple Agents
- Each workstream works in its own branch prefix:
  - `ws1/*`, `ws2/*`, `ws3/*`, etc.
- Contract-first policy:
  1. WS1 publishes/updates JSON schemas.
  2. WS2–WS6 implement against schema versions.
- Merge gates:
  - No consumer PR merges unless schema validation passes.
  - All generated artifacts must be referenced in `artifacts/manifest.json`.

## 5) Execution Rhythm (Parallel Sprint Cadence)
- Daily contract sync (15 min): schema/version changes only.
- Midday integration build: assemble WS outputs and run smoke tests.
- End-of-day regression run: golden checks + UI snapshot diff.

## 6) Compatibility and Versioning Rules
- Semantic versions on contract files.
- Backward incompatible changes require:
  - increment major version,
  - migration note under `contracts/CHANGELOG.md`,
  - adapter compatibility matrix update.

## 7) Acceptance Criteria for Parallel Development
- Any team can run locally with only:
  - latest contract files,
  - latest `artifacts/manifest.json`,
  - template sample data.
- All cross-team data handoffs pass schema validation.
- Integration tests consume only published artifacts, not private in-memory states.
