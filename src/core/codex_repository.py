from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Tuple

from domain.codex_models import CodexEntry, CodexEntryType, CodexReference

from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class CodexRepository:
    """Codex repository (DB access layer).

    This is intentionally a thin wrapper around DatabaseManager to keep CodexManager
    focused on domain logic and make it easier to migrate away from Qt in later steps.
    """

    def __init__(self, database_manager: DatabaseManager):
        self._db = database_manager

    def load_all(self) -> Tuple[List[CodexEntry], List[CodexReference]]:
        codex_data = self._db.load_codex_data()

        entries: List[CodexEntry] = []
        for entry_data in codex_data.get("entries", []):
            data = dict(entry_data)
            data["entry_type"] = CodexEntryType(data["entry_type"])
            entries.append(CodexEntry(**data))

        references: List[CodexReference] = []
        for ref_data in codex_data.get("references", []):
            references.append(CodexReference(**ref_data))

        return entries, references

    def save_all(self, entries: List[CodexEntry], references: List[CodexReference]) -> None:
        entries_data: List[Dict[str, Any]] = []
        for entry in entries:
            entry_dict = asdict(entry)
            entry_dict["entry_type"] = entry.entry_type.value
            entry_dict["updated_at"] = datetime.now().isoformat()
            entries_data.append(entry_dict)

        references_data = [asdict(ref) for ref in references]
        self._db.save_codex_data(entries_data, references_data)

    def insert_entry(self, entry: CodexEntry) -> bool:
        entry_dict = asdict(entry)
        entry_dict["entry_type"] = entry.entry_type.value
        entry_dict["updated_at"] = datetime.now().isoformat()
        return bool(self._db.insert_codex_entry(entry_dict))

    def update_entry(self, entry: CodexEntry) -> bool:
        entry_dict = asdict(entry)
        entry_dict["entry_type"] = entry.entry_type.value
        entry_dict["updated_at"] = datetime.now().isoformat()
        return bool(self._db.update_codex_entry(entry.id, entry_dict))

    def delete_entry(self, entry_id: str) -> bool:
        return bool(self._db.delete_codex_entry(entry_id))

    def update_reference_access(self, ref_id: int, *, increment_access: bool = True) -> bool:
        try:
            with self._db._get_connection() as conn:  # noqa: SLF001
                if increment_access:
                    conn.execute(
                        """
                        UPDATE codex_references
                        SET access_count = access_count + 1,
                            last_accessed_at = ?
                        WHERE id = ?
                        """,
                        (datetime.now().isoformat(), ref_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE codex_references
                        SET last_accessed_at = ?
                        WHERE id = ?
                        """,
                        (datetime.now().isoformat(), ref_id),
                    )

                conn.commit()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("CodexRepository: failed to update reference access: %s", e)
            return False

    def mark_reference_as_deleted(self, ref_id: int) -> bool:
        try:
            with self._db._get_connection() as conn:  # noqa: SLF001
                conn.execute(
                    """
                    UPDATE codex_references
                    SET deleted_at = ?,
                        status = 'deleted'
                    WHERE id = ?
                    """,
                    (datetime.now().isoformat(), ref_id),
                )
                conn.commit()
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("CodexRepository: failed to mark reference as deleted: %s", e)
            return False

