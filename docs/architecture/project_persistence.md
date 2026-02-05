# Project Persistence Roadmap (Incremental)

This roadmap fixes the intended incremental persistence route for Project data.

## Phases

**Phase 1**
- Keep `save_project_full()` (full rewrite) behavior for safety.
- Route all persistence calls through `ProjectRepository` (auditability).

**Phase 2**
- Implement and use incremental APIs: `upsert_document`, `delete_document`, `move_document`, `reorder_children`.
- Editor “save single document” must use incremental path (no `DELETE FROM documents`).

**Phase 3**
- Reserve full rewrites only for structural operations (bulk import / full tree reorder).
- All non-structural edits must use incremental APIs (no full-table rewrites).

## Outline implications

- Phase 1: debounce + worker calculation + main-thread apply to reduce UI jank.
- Phase 2: introduce an outline model (e.g., `QAbstractItemModel`) to enable incremental updates for rename/move/reorder.
- Phase 2: avoid full tree rebuilds on rename/move/reorder; update only affected nodes.
