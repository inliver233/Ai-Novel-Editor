from __future__ import annotations

"""
BackupService v1 (Phase 1).

This module is the hard-coded landing point for backup/restore workflows during
the refactor baseline work. The API will be filled in incrementally by the
corresponding Issue CSV tasks (create/restore/list).
"""


class BackupServiceError(RuntimeError):
    """Raised when a backup/restore operation fails."""

