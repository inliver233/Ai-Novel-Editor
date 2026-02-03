import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_normalize_log_level() -> None:
    from core import log as log_mod

    assert log_mod._normalize_log_level("debug") == "DEBUG"
    assert log_mod._normalize_log_level("INFO") == "INFO"
    assert log_mod._normalize_log_level("warn") == "WARNING"
    assert log_mod._normalize_log_level("fatal") == "CRITICAL"
    assert log_mod._normalize_log_level("unknown") == log_mod.Defaults.LOG_LEVEL


def test_config_default_log_level(tmp_path, monkeypatch) -> None:
    from core import config as config_mod

    monkeypatch.setattr(config_mod.Config, "_get_config_dir", lambda self: tmp_path)
    cfg = config_mod.Config()

    assert cfg.get("app", "log_level") in {"INFO", "DEBUG"}
