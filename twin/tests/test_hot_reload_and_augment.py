#!/usr/bin/env python3
"""Tests for hot-reload state migration, env context building, and tool intent mapping.

Covers:
- _reload_modules state dict completeness
- _build_env_context output structure
- _augment_with_env trigger keywords
- _augment_with_tools trigger keywords and tool execution
- _augment_with_repo trigger keywords and context injection
- _parse_structured_tool_calls JSON parsing
- _parse_legacy_tool_calls fallback parsing
"""

import os
import sys
import json
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure lib is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))


def _make_mock_orchestrator(**overrides):
    """Build a minimal SessionOrchestrator-like object for unit testing.

    We avoid importing SessionOrchestrator directly because it has heavy
    side-effects (prompt_toolkit, pynput, etc.). Instead we import the
    module and selectively bind methods under test to a mock instance.
    """
    from tools import ToolRegistry

    mock = MagicMock()
    mock.config = overrides.get('config', {'twin_config': {}})
    mock.mode = overrides.get('mode', 'personal')
    mock.agent = overrides.get('agent', {'name': 'assistant'})
    mock.model = overrides.get('model', 'qwen2.5-coder:7b')
    mock.context = overrides.get('context', None)
    mock.session_id = 'test1234'
    mock.messages = []
    mock.static_system_messages = []
    mock.running_summary = ''
    mock.env_context = ''
    mock.repo_index = []
    mock.last_repo_context = []
    mock.session_data = {
        'session_id': 'test1234',
        'mode': 'personal',
        'agent': 'assistant',
        'planning_discussion': '',
        'decisions': [],
        'reasoning': [],
        'next_steps': [],
        'files_discussed': []
    }
    mock.pasted_images = []
    mock.image_counter = 0
    mock.session_metrics = {'queries': 0, 'total_time': 0.0, 'start_time': 0, 'responses': []}
    mock.last_query_time = 0.0
    mock.last_model_used = 'qwen2.5-coder:7b'
    mock.agent_reason = 'default'
    mock.keyboard_enabled = False

    # Bind real tool registry (offline to avoid network)
    with patch('tools.ToolRegistry._detect_offline', return_value=True):
        mock.tool_registry = ToolRegistry(mock.config)

    return mock


class TestReloadStateMigration(unittest.TestCase):
    """Verify that all expected state keys are present in the reload snapshot."""

    EXPECTED_STATE_KEYS = {
        'mode', 'agent', 'context', 'model',
        'session_id', 'session_data', 'messages',
        'static_system_messages', 'running_summary',
        'env_context', 'tool_registry', 'session_metrics',
        'last_query_time', 'prompt_session',
        'pasted_images', 'image_counter',
        'repo_index', 'last_repo_context',
    }

    def test_state_dict_keys_match_expected(self):
        """The state dict built in _reload_modules must contain all expected keys."""
        # We parse the source code to extract the state dict keys rather than
        # running _reload_modules (which has heavy side effects).
        import ast

        session_path = Path(__file__).resolve().parent.parent / 'lib' / 'session.py'
        source = session_path.read_text()

        # Find the state = { ... } assignment inside _reload_modules
        tree = ast.parse(source)

        state_keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == '_reload_modules':
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name) and target.id == 'state':
                                if isinstance(child.value, ast.Dict):
                                    for key in child.value.keys:
                                        if isinstance(key, ast.Constant):
                                            state_keys.add(key.value)
                break

        self.assertTrue(len(state_keys) > 0, "Could not parse state dict from _reload_modules")

        missing = self.EXPECTED_STATE_KEYS - state_keys
        extra = state_keys - self.EXPECTED_STATE_KEYS

        self.assertEqual(missing, set(), f"Missing state keys in _reload_modules: {missing}")
        # Extra keys are warnings, not failures
        if extra:
            print(f"NOTE: extra state keys found (not necessarily wrong): {extra}")


class TestBuildEnvContext(unittest.TestCase):
    """Test _build_env_context output structure."""

    def test_contains_cwd(self):
        """Env context must include the current working directory."""
        # Import the method
        import session as session_module
        orch = _make_mock_orchestrator()

        # Bind the real method
        method = session_module.SessionOrchestrator._build_env_context

        with tempfile.TemporaryDirectory() as tmpdir:
            result = method(orch, tmpdir)
            self.assertIn(tmpdir, result)
            self.assertIn('CWD:', result)

    def test_lists_top_level_entries(self):
        """Env context should list files in the directory."""
        import session as session_module
        orch = _make_mock_orchestrator()
        method = session_module.SessionOrchestrator._build_env_context

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'hello.txt').write_text('world')
            result = method(orch, tmpdir)
            self.assertIn('hello.txt', result)

    def test_includes_readme_summary(self):
        """If README.md exists, env context should include a summary."""
        import session as session_module
        orch = _make_mock_orchestrator()

        # Bind _summarize_text too
        orch._summarize_text = session_module.SessionOrchestrator._summarize_text.__get__(orch)
        method = session_module.SessionOrchestrator._build_env_context

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'README.md').write_text('# My Project\nThis is a test project.')
            result = method(orch, tmpdir)
            self.assertIn('README summary', result)


class TestAugmentWithEnv(unittest.TestCase):
    """Test _augment_with_env trigger keywords."""

    def _run_augment(self, user_input: str, env_context: str = 'CWD: /tmp/test'):
        import session as session_module
        orch = _make_mock_orchestrator()
        orch.env_context = env_context
        method = session_module.SessionOrchestrator._augment_with_env
        return method(orch, user_input)

    def test_triggers_on_pwd(self):
        result = self._run_augment('what is the pwd?')
        self.assertIn('[Auto context]', result)

    def test_triggers_on_current_directory(self):
        result = self._run_augment('what is the current directory')
        self.assertIn('[Auto context]', result)

    def test_no_trigger_on_unrelated(self):
        result = self._run_augment('tell me a joke')
        self.assertNotIn('[Auto context]', result)
        self.assertEqual(result, 'tell me a joke')


class TestAugmentWithTools(unittest.TestCase):
    """Test _augment_with_tools trigger keywords."""

    def _run_augment(self, user_input: str):
        import session as session_module
        orch = _make_mock_orchestrator()
        method = session_module.SessionOrchestrator._augment_with_tools
        return method(orch, user_input)

    def test_triggers_on_list_files(self):
        result = self._run_augment('can you list files here?')
        self.assertIn('[Tool context]', result)

    def test_no_trigger_on_unrelated(self):
        result = self._run_augment('explain monads')
        self.assertNotIn('[Tool context]', result)


class TestAugmentWithRepo(unittest.TestCase):
    """Test _augment_with_repo trigger and context injection."""

    def test_triggers_on_find(self):
        import session as session_module
        orch = _make_mock_orchestrator()
        orch.repo_index = [
            {'file': 'lib/tools.py', 'start_line': 1, 'text': 'tool registry implementation find grep'},
        ]
        method = session_module.SessionOrchestrator._augment_with_repo
        result = method(orch, 'find the tool registry implementation')
        self.assertIn('[Repo context', result)
        self.assertIn('lib/tools.py', result)

    def test_no_trigger_on_unrelated(self):
        import session as session_module
        orch = _make_mock_orchestrator()
        orch.repo_index = [
            {'file': 'lib/tools.py', 'start_line': 1, 'text': 'tool registry'},
        ]
        method = session_module.SessionOrchestrator._augment_with_repo
        result = method(orch, 'tell me a joke')
        self.assertNotIn('[Repo context', result)


class TestParseStructuredToolCalls(unittest.TestCase):
    """Test _parse_structured_tool_calls JSON parsing."""

    def _parse(self, response: str):
        import session as session_module
        orch = _make_mock_orchestrator()
        method = session_module.SessionOrchestrator._parse_structured_tool_calls
        return method(orch, response)

    def test_parses_fenced_json(self):
        response = '''Here is my plan:
```json
{"tool_calls": [{"name": "read", "args": {"file_path": "foo.py"}}]}
```
'''
        calls = self._parse(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tool'], 'read')
        self.assertEqual(calls[0]['args']['file_path'], 'foo.py')

    def test_parses_inline_json(self):
        response = 'Let me read that: {"tool_calls": [{"name": "bash", "args": {"command": "ls"}}]}'
        calls = self._parse(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tool'], 'bash')

    def test_returns_empty_on_no_json(self):
        calls = self._parse('No tools needed here.')
        self.assertEqual(calls, [])

    def test_warns_on_unknown_arg(self):
        response = '{"tool_calls": [{"name": "read", "args": {"file_path": "x.py", "bogus": 1}}]}'
        calls = self._parse(response)
        # Should still parse but validation warnings are printed
        self.assertEqual(len(calls), 1)


class TestParseLegacyToolCalls(unittest.TestCase):
    """Test _parse_legacy_tool_calls fallback parsing."""

    def _parse(self, response: str):
        import session as session_module
        orch = _make_mock_orchestrator()
        method = session_module.SessionOrchestrator._parse_legacy_tool_calls
        return method(orch, response)

    def test_parses_legacy_format(self):
        response = 'TOOL_CALL: read\nARGS: {"file_path": "bar.py"}'
        calls = self._parse(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tool'], 'read')

    def test_returns_empty_on_no_match(self):
        calls = self._parse('Just a normal response')
        self.assertEqual(calls, [])


class TestSummarizeText(unittest.TestCase):
    """Test _summarize_text deterministic summarizer."""

    def _summarize(self, text, **kwargs):
        import session as session_module
        orch = _make_mock_orchestrator()
        method = session_module.SessionOrchestrator._summarize_text
        return method(orch, text, **kwargs)

    def test_respects_max_chars(self):
        long_text = 'This is a sentence. ' * 200
        result = self._summarize(long_text, max_chars=100)
        self.assertLessEqual(len(result), 103)  # +3 for possible "..."

    def test_respects_max_items(self):
        text = 'One. Two. Three. Four. Five. Six. Seven. Eight.'
        result = self._summarize(text, max_items=3)
        self.assertLessEqual(result.count('- '), 3)

    def test_empty_input(self):
        result = self._summarize('')
        self.assertEqual(result, '')


if __name__ == '__main__':
    unittest.main()
