from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_config_set_ai_api_key_stores_securely(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core import config as config_mod
    from core import secure_key_manager as skm_mod

    monkeypatch.setattr(config_mod.Config, "_get_config_dir", lambda self: tmp_path)

    manager = skm_mod.SecureKeyManager(app_name="AI-Novel-Editor-TEST")
    monkeypatch.setattr(manager, "_get_key_store_path", lambda: tmp_path / "secure" / "api_keys.json")
    monkeypatch.setattr(config_mod, "get_secure_key_manager", lambda: manager)

    cfg = config_mod.Config()
    cfg.set("ai", "provider", "openai")
    cfg.set("ai", "api_key", "secret-ai-key")

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["ai"]["api_key"] == ""
    assert "secret-ai-key" not in (tmp_path / "config.json").read_text(encoding="utf-8")
    assert manager.retrieve_api_key("openai") == "secret-ai-key"


def test_config_set_rag_api_key_stores_securely(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core import config as config_mod
    from core import secure_key_manager as skm_mod

    monkeypatch.setattr(config_mod.Config, "_get_config_dir", lambda self: tmp_path)

    manager = skm_mod.SecureKeyManager(app_name="AI-Novel-Editor-TEST")
    monkeypatch.setattr(manager, "_get_key_store_path", lambda: tmp_path / "secure" / "api_keys.json")
    monkeypatch.setattr(config_mod, "get_secure_key_manager", lambda: manager)

    cfg = config_mod.Config()
    cfg.set_section("rag", {"enabled": True, "api_key": "secret-rag-key"})

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["rag"]["api_key"] == ""
    assert "secret-rag-key" not in (tmp_path / "config.json").read_text(encoding="utf-8")
    assert manager.retrieve_api_key("rag") == "secret-rag-key"

