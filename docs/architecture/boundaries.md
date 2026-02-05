# Module Boundaries (Draft)

## Current Shared responsibilities

Shared currently bundles multiple concerns that should be separated over time:

- **State**: `current_project_path`, `current_document_id`, theme, config flags, autosave, etc.
- **Signals / events**: `projectChanged`, `documentChanged`, `documentSaved`, `themeChanged`, `configChanged`.
- **Service registry**: `ai_manager`, `task_manager`, `index_scheduler`, `rag_service`, `vector_store`, `codex_manager`, `reference_detector`, `prompt_function_registry`.
- **Caches / data**: project-scoped data dict and document cache.

This document will define the target boundaries and the incremental migration plan.

## Target replacements (directional)

To reduce Shared’s scope, we introduce two explicit boundaries:

- **AppServices**: a service registry / dependency injection container for long‑lived services.
- **AppEvents**: a centralized event bus (Qt signals) for cross‑module notifications.

These boundaries keep stateful services and signal wiring explicit, avoiding hidden coupling in Shared.
