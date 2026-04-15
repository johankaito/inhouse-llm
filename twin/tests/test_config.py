#!/usr/bin/env python3
"""Unit tests for twin/lib/config.py"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config import ConfigLoader


class TestResolveModelAlias(unittest.TestCase):
    """Tests for ConfigLoader.resolve_model_alias"""

    def _loader_with_aliases(self, aliases: dict) -> ConfigLoader:
        loader = ConfigLoader()
        loader.config = {"twin_config": {"model_aliases": aliases}}
        return loader

    def test_known_alias_resolves(self):
        loader = self._loader_with_aliases({"fast": {"model": "qwen2.5-coder:3b-fast"}})
        self.assertEqual(loader.resolve_model_alias("fast"), "qwen2.5-coder:3b-fast")

    def test_unknown_alias_returns_as_is(self):
        loader = self._loader_with_aliases({"fast": {"model": "qwen2.5-coder:3b-fast"}})
        self.assertEqual(loader.resolve_model_alias("qwen2.5-coder:32b"), "qwen2.5-coder:32b")

    def test_empty_aliases(self):
        loader = self._loader_with_aliases({})
        self.assertEqual(loader.resolve_model_alias("anything"), "anything")

    def test_no_twin_config_key(self):
        loader = ConfigLoader()
        loader.config = {}
        self.assertEqual(loader.resolve_model_alias("fast"), "fast")


class TestValidateModelExists(unittest.TestCase):
    """Tests for ConfigLoader.validate_model_exists"""

    @patch("config.subprocess.run")
    def test_model_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NAME               ID         SIZE    MODIFIED\nqwen2.5-coder:7b   abc123     4.7GB   2 days ago\n",
        )
        loader = ConfigLoader()
        exists, models = loader.validate_model_exists("qwen2.5-coder:7b")
        self.assertTrue(exists)
        self.assertIn("qwen2.5-coder:7b", models)

    @patch("config.subprocess.run")
    def test_model_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NAME               ID         SIZE    MODIFIED\nqwen2.5-coder:7b   abc123     4.7GB   2 days ago\n",
        )
        loader = ConfigLoader()
        exists, models = loader.validate_model_exists("nonexistent:latest")
        self.assertFalse(exists)
        self.assertIn("qwen2.5-coder:7b", models)

    @patch("config.subprocess.run", side_effect=FileNotFoundError)
    def test_ollama_not_installed(self, mock_run):
        loader = ConfigLoader()
        exists, models = loader.validate_model_exists("qwen2.5-coder:7b")
        self.assertFalse(exists)
        self.assertEqual(models, [])

    @patch("config.subprocess.run")
    def test_empty_model_list(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="NAME\n")
        loader = ConfigLoader()
        exists, models = loader.validate_model_exists("any")
        self.assertFalse(exists)
        self.assertEqual(models, [])

    @patch("config.subprocess.run")
    def test_subprocess_nonzero_return(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        loader = ConfigLoader()
        exists, models = loader.validate_model_exists("any")
        self.assertFalse(exists)
        self.assertEqual(models, [])


class TestGetModelForAgent(unittest.TestCase):
    """Tests for ConfigLoader.get_model_for_agent"""

    def test_agent_specific_preference(self):
        loader = ConfigLoader()
        loader.config = {
            "twin_config": {
                "agent_model_preferences": {"technical-lead": "balanced"},
                "mode_defaults": {"work": "fast"},
                "default_model": "fast",
            }
        }
        self.assertEqual(loader.get_model_for_agent("technical-lead", "work"), "balanced")

    def test_falls_back_to_mode_default(self):
        loader = ConfigLoader()
        loader.config = {
            "twin_config": {
                "agent_model_preferences": {},
                "mode_defaults": {"work": "quality"},
                "default_model": "fast",
            }
        }
        self.assertEqual(loader.get_model_for_agent("unknown-agent", "work"), "quality")

    def test_falls_back_to_global_default(self):
        loader = ConfigLoader()
        loader.config = {
            "twin_config": {
                "agent_model_preferences": {},
                "mode_defaults": {},
                "default_model": "fast",
            }
        }
        self.assertEqual(loader.get_model_for_agent("unknown-agent", "personal"), "fast")

    def test_empty_twin_config(self):
        loader = ConfigLoader()
        loader.config = {}
        self.assertEqual(loader.get_model_for_agent("any", "personal"), "fast")


class TestGetDefaultTwinConfig(unittest.TestCase):
    def test_returns_expected_keys(self):
        loader = ConfigLoader()
        defaults = loader.get_default_twin_config()
        self.assertIn("default_model", defaults)
        self.assertIn("model_aliases", defaults)
        self.assertEqual(defaults["default_model"], "fast")


class TestLoadTwinConfigMissing(unittest.TestCase):
    @patch.object(Path, "exists", return_value=False)
    def test_missing_twin_config_returns_defaults(self, _mock):
        loader = ConfigLoader()
        result = loader.load_twin_config()
        self.assertEqual(result["default_model"], "fast")


class TestGetModelInfo(unittest.TestCase):
    def test_known_alias(self):
        loader = ConfigLoader()
        loader.config = {
            "twin_config": {
                "model_aliases": {
                    "fast": {"model": "qwen2.5-coder:3b-fast", "description": "Fast"}
                }
            }
        }
        info = loader.get_model_info("fast")
        self.assertIsNotNone(info)
        self.assertEqual(info["model"], "qwen2.5-coder:3b-fast")

    def test_unknown_alias_returns_none(self):
        loader = ConfigLoader()
        loader.config = {"twin_config": {"model_aliases": {}}}
        self.assertIsNone(loader.get_model_info("nonexistent"))


if __name__ == "__main__":
    unittest.main()
