# Module Boundaries (Draft)

## Current Shared responsibilities

Shared currently bundles multiple concerns that should be separated over time:

- **State**: `current_project_path`, `current_document_id`, theme, config flags, autosave, etc.
- **Signals / events**: `projectChanged`, `documentChanged`, `documentSaved`, `themeChanged`, `configChanged`.
- **Service registry**: `ai_manager`, `task_manager`, `index_scheduler`, `rag_service`, `vector_store`, `codex_manager`, `reference_detector`, `prompt_function_registry`.
- **Caches / data**: project-scoped data dict and document cache.

This document will define the target boundaries and the incremental migration plan.
