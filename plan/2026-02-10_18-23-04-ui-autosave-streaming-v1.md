---
mode: plan
task: UI bottom bar cleanup + autosave persistence + cross-provider streaming
created_at: "2026-02-10T18:23:04+08:00"
complexity: complex
---

# Plan: UI bottom bar cleanup + autosave persistence + cross-provider streaming

## Goal
- Fix bottom UI: remove duplicate/overlapping status areas; keep a single clear bottom status bar.
- Make project editing durable: autosave + manual save persist into the project DB; reopening shows content (no “blank project” surprise).
- Make streaming real: add a default-on streaming toggle in API config and implement end-to-end streaming for OpenAI/Claude/Gemini with ordered, typing-like UI rendering (no乱序/串流错位).
- Close the full batch Issue CSV with repeatable verification and a final regression pass.

## Scope
- In:
  - Bottom status UI cleanup (EditorPanel vs MainWindow status bar).
  - Project document persistence: `ProjectManager.update_document_content`, editor bindings, autosave/manual save, session restore.
  - Streaming: dispatch plumbing, provider streaming endpoints/parsers (OpenAI/Claude/Gemini), and UI ordered rendering.
  - Targeted unit/Qt tests for the above.
- Out:
  - Major UI redesign beyond the bottom bar cleanup.
  - Provider/model discovery of exact context window/token limits (we only raise app-side limits and pass through values).

## Assumptions / Dependencies
- Running on `test` branch with push access to `origin/test`.
- Tests run offline (no real API calls); streaming/provider behavior validated via fixture stream chunks.
- Web research is allowed for up-to-date provider streaming specs (implementation must not hardcode outdated assumptions).

## Phases
1. Generate batch Issue CSV + this plan (timestamp/slug matched).
2. Fix bottom status UI duplication and update Qt layout tests.
3. Implement real autosave/manual save persistence to project DB; bind editors to project documents.
4. Add session restore (reopen last project + last document) and wire settings to config.
5. Implement streaming plumbing (toggle -> request dispatch -> chunk signals with context).
6. Implement provider streaming adaptation (Gemini streaming endpoint + chunk parsing; robust SSE parsing).
7. Implement UI streaming renderer (buffered typing effect, ordered, cancel-safe).
8. Run regression (`compileall` + full `pytest`) then mark `Regression_Status=DONE` via a CSV-only meta commit.

## Tests & Verification
- `C1` -> `python -m pytest -q tests/test_status_bar_layout.py`
- `C2` -> `python -m pytest -q tests/test_project_update_document_content.py`
- `C3` -> `python -m pytest -q tests/test_editor_project_persistence.py`
- `C4` -> `manual` (app restart/session restore checklist in Issue notes)
- `C5` -> `python -m pytest -q tests/test_streaming_dispatcher.py`
- `C6` -> `python -m pytest -q tests/test_provider_streaming_gemini.py`
- `C7` -> `python -m pytest -q tests/test_streaming_typed_renderer.py`
- Regression -> `python -m compileall -q src` + `python -m pytest -q`

## Issue CSV
- Path: issues/2026-02-10_18-23-04-ui-autosave-streaming-v1.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- none

## Acceptance Checklist
- [ ] Bottom bar is a single, non-overlapping status area.
- [ ] Autosave + manual save persist project document content to DB and reload correctly.
- [ ] Restart restores last project/document when enabled.
- [ ] Streaming toggle works; OpenAI/Claude/Gemini stream with correct endpoints/params and ordered UI rendering.
- [ ] All issues `Dev_Status/Review1_Status/Regression_Status` are `DONE`.

## Risks / Blockers
- Streaming formats can change; mitigate via up-to-date doc research + tolerant parsing + fixture tests.
- Qt geometry/UI tests can be font/DPI sensitive; keep assertions focused and tolerant.

## Rollback / Recovery
- Revert per-issue commits affecting the subsystem.

## Checkpoints
- Commit after each Issue row; meta commit after regression.

## References
- `src/gui/status/status_bar.py`
- `src/gui/editor/editor_panel.py`
- `src/gui/editor/text_editor.py`
- `src/core/project.py`
- `src/application/ai_completion_service.py`
- `src/core/ai_client.py`
- `src/core/ai_providers/gemini.py`
- `src/gui/ai/enhanced_ai_manager.py`
- `src/gui/main_window_parts/integrations.py`
