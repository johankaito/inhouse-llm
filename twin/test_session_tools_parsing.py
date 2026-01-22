import json
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent / "lib"))

from lib.session import SessionOrchestrator  # type: ignore
from lib.tools import ToolRegistry  # type: ignore


class _DummyAgentLoader:
    def get_agent(self, name: str):
        return {"name": name, "master_prompt": ""}


class _DummyContextManager:
    def get_recent_sessions(self, *_args, **_kwargs):
        return []

    def get_context_summary(self, *_args, **_kwargs):
        return ""


def _make_orchestrator(registry: ToolRegistry) -> SessionOrchestrator:
    return SessionOrchestrator(
        config={"twin_config": {"generation_params": {}, "ollama": {}}},
        mode="personal",
        agent={"name": "decision-framework", "master_prompt": ""},
        context=None,
        model="fast",
        agent_loader=_DummyAgentLoader(),
        mode_detector=None,
        context_manager=_DummyContextManager(),
    )


class ToolParsingTests(unittest.TestCase):
    def test_parse_structured_tool_call_valid(self):
        registry = ToolRegistry({})
        orchestrator = _make_orchestrator(registry)

        payload = {"tool_calls": [{"name": "bash", "args": {"command": "echo ok"}}]}
        response = f"```json\n{json.dumps(payload)}\n```"
        calls = orchestrator._parse_tool_calls(response)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "bash")
        self.assertEqual(calls[0]["args"]["command"], "echo ok")

    def test_parse_structured_tool_call_with_missing_arg_warns_but_parses(self):
        registry = ToolRegistry({})
        orchestrator = _make_orchestrator(registry)

        payload = {"tool_calls": [{"name": "bash", "args": {"oops": "x"}}]}
        response = f"```json\n{json.dumps(payload)}\n```"
        calls = orchestrator._parse_tool_calls(response)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "bash")
        self.assertEqual(calls[0]["args"]["oops"], "x")

    def test_parse_legacy_tool_call(self):
        registry = ToolRegistry({})
        orchestrator = _make_orchestrator(registry)

        response = 'TOOL_CALL: read\nARGS: {"file_path": "README.md"}'
        calls = orchestrator._parse_tool_calls(response)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "read")
        self.assertEqual(calls[0]["args"]["file_path"], "README.md")

    def test_parse_tool_call_ignores_malformed(self):
        registry = ToolRegistry({})
        orchestrator = _make_orchestrator(registry)

        response = "TOOL_CALL: read\nARGS: not-json-here"
        calls = orchestrator._parse_tool_calls(response)

        self.assertEqual(calls, [])

    def test_should_run_post_checks_detects_file_changes(self):
        registry = ToolRegistry({})
        orchestrator = _make_orchestrator(registry)

        class _Result:
            def __init__(self, success, metadata):
                self.success = success
                self.metadata = metadata

        results = [
            _Result(True, {"file_path": "/tmp/test.txt"}),
            _Result(True, {}),
        ]
        self.assertTrue(orchestrator._should_run_post_checks(results))

        results = [_Result(True, {}), _Result(False, {"file_path": "/tmp/test.txt"})]
        self.assertFalse(orchestrator._should_run_post_checks(results))


if __name__ == "__main__":
    unittest.main()
