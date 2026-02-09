from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.config_schema import (  # noqa: E402
    ConfigSchema,
    CURRENT_SCHEMA_VERSION,
    apply_defaults_inplace,
    migrate_config_inplace,
)


class TestConfigSchemaMigration(unittest.TestCase):
    def test_config_schema_exposes_version_and_defaults(self):
        schema = ConfigSchema()
        self.assertEqual(schema.version, CURRENT_SCHEMA_VERSION)
        self.assertIn("ai", schema.defaults)
        self.assertIn("ui", schema.defaults)

    def test_migrate_v0_fixture_adds_version_and_cleans_deprecated_keys(self):
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "config_v0.json"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        changed = migrate_config_inplace(data)
        defaults_changed = apply_defaults_inplace(data)

        self.assertTrue(changed)
        self.assertEqual(data["schema_version"], CURRENT_SCHEMA_VERSION)
        self.assertNotIn("theme", data)
        self.assertEqual(data["ui"]["theme"], "light")
        self.assertNotIn("cache", data["rag"])

        # Defaults should be filled for missing sections/keys.
        self.assertTrue(defaults_changed)
        self.assertIn("app", data)
        self.assertIn("project", data)
        self.assertIn("enable_tools", data["ai"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
