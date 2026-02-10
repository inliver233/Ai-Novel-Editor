---
mode: plan
task: UI+Autosave+Streaming fixes v2
created_at: "2026-02-10T23:07:08+08:00"
complexity: complex
---

# Plan: UI + Autosave + Streaming fixes v2

## Goal
- Fix streaming completion so it never overwrites existing document text and caret stays stable; output renders in-order like typing.
- Ensure blank/scratch editing is auto-saved and restored reliably (including on app close) so content isn鈥檛 lost.
- Clean up bottom status bar visual clutter (no stacked separators/overlaps) and keep key info readable.
- Confirm max_tokens UI supports large values (>= 1,000,000) and config persists correctly.
- Verify provider streaming request/response formats for OpenAI/Anthropic/Gemini against latest docs and keep code + tests aligned.

## Scope
- In:
  - Ghost text/inline completion rendering (`src/gui/editor/*ghost*`, `src/gui/editor/smart_completion_manager.py`)
  - Streaming request/parse plumbing (`src/core/ai_client.py`, `src/core/ai_providers/*`, `src/core/ai_qt_client.py`, `src/gui/ai/enhanced_ai_manager.py`)
  - Autosave/session restore for scratch + project docs (`src/gui/editor/editor_panel.py`, `src/gui/editor/text_editor.py`, `src/main.py`, `src/core/config*.py`)
  - Status bar UI (`src/gui/status/status_bar.py` + related tests)
  - AI config center UI token/stream toggles (`src/gui/ai/unified_ai_config_dialog.py`)
- Out:
  - Changing project DB schema
  - Adding new providers beyond existing list (only ensure existing auto-adaptation is correct)

## Assumptions / Dependencies
- Use venv python: `.tmp\\ane0305-venv-311\\Scripts\\python.exe`
- PyQt6 + pytest-qt available for tests.
- Provider streaming docs may change; rely on official docs as of 2026-02-10.

## Phases
1. Create plan + Issue CSV contract; validate CSV.
2. Streaming render safety: move ghost preview to non-destructive overlay; add tests guarding no overwrite/cursor chaos.
3. Autosave reliability: flush on close; persist/restore scratch doc; add tests + manual checklist.
4. Status bar cleanup: remove redundant separators and fix sizing; update layout test.
5. Provider streaming verification: web research + adjust provider strategies/SSE parsing as needed; add/refresh fixtures.
6. Regression: run `python -m compileall -q src` and targeted pytest suite; mark Regression DONE via meta commit.

## Tests & Verification
- Streaming safety -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q tests/test_streaming_ghost_no_overwrite.py`
- Scratch autosave -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q tests/test_scratch_autosave_restore.py`
- Status bar -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q tests/test_status_bar_layout.py`
- Config UI -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q tests/test_ai_config_max_tokens_range.py`
- Provider streaming -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q tests/test_provider_streaming_openai_claude.py`
- Regression -> `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m compileall -q src` + `.tmp\\ane0305-venv-311\\Scripts\\python.exe -m pytest -q`

## Issue CSV
- Path: issues/2026-02-10_23-01-37-ui-autosave-streaming-v2.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `manual` for UI verification.
- `none` for code work; web search (non-MCP) for provider docs.

## Acceptance Checklist
- [ ] Streaming completion never modifies document text until user accepts.
- [ ] Streaming output appears in-order like typing; cancel stops updates; stale chunks ignored.
- [ ] Closing the app does not lose recently typed content (project docs and scratch).
- [ ] New/empty project starts with empty content (no ghost/saved garbage).
- [ ] Bottom status bar has clean separators, no stacked lines or clipping.
- [ ] Max tokens UI supports >= 1,000,000 and persists.
- [ ] All issues Dev/Review1/Regression are DONE with tests evidence in Notes.

## Risks / Blockers
- PyQt paint overlay differences across platforms/themes; needs manual QA.
- Streaming SSE formats may evolve; fixtures might need updates.

## Rollback / Recovery
- Keep old Optimal ghost system code; allow toggling default back if deep overlay causes regressions.
- For autosave: keep scratch autosave file separate and non-destructive.

## Checkpoints
- Commit + push per issue.
- Meta commit for Regression_Status after batch passes.

## References
- src/gui/editor/text_editor.py
- src/gui/editor/optimal_ghost_text.py
- src/gui/editor/deep_integrated_ghost_text.py
- src/gui/editor/smart_completion_manager.py
- src/core/ai_client.py
- src/gui/status/status_bar.py
