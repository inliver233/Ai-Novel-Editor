from __future__ import annotations

from pathlib import Path


def test_export_dialog_opens_file_without_shell_invocation() -> None:
    path = Path("src/gui/dialogs/export_dialog.py")
    content = path.read_text(encoding="utf-8")

    assert "os.startfile" not in content
    assert "os.system(" not in content
    assert "xdg-open" not in content
    assert "QDesktopServices.openUrl" in content

