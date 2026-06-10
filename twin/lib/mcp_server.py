"""Minimal stdio MCP server exposing twin's differentiated tools.

Stage 3 of docs/architecture/local-first-foundation.md: instead of
rewriting MCP support into twin, twin's unique tools are served over MCP
so any MCP host (OpenCode, Claude Code, Cursor) can consume them.

Zero dependencies beyond twin itself: the tools-only MCP surface is three
JSON-RPC methods (initialize, tools/list, tools/call) over stdio, so the
official SDK is not needed. Local-only — no network, no API keys.

Run: python3 twin/lib/mcp_server.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "twin-tools", "version": "1.0.0"}

EXPOSED_TOOLS = ("repo_search", "gh_search_code", "gh_get_pr")


def _json_schema_type(description: str) -> str:
    if isinstance(description, str) and description.lower().startswith("int"):
        return "integer"
    return "string"


class TwinMCPServer:
    def __init__(self, registry=None):
        self._registry = registry

    def _get_registry(self):
        if self._registry is None:
            from config import ConfigLoader
            from tools import ToolRegistry
            config = ConfigLoader().load_all()
            self._registry = ToolRegistry(config)
        return self._registry

    def _tool_definitions(self) -> List[Dict[str, Any]]:
        registry = self._get_registry()
        definitions = []
        for name in EXPOSED_TOOLS:
            tool = registry.get(name)
            if tool is None:
                continue
            properties = {}
            required = []
            for arg, description in tool.args_schema.items():
                properties[arg] = {
                    "type": _json_schema_type(description),
                    "description": str(description),
                }
                if arg in tool.required_args:
                    required.append(arg)
            definitions.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return definitions

    def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in EXPOSED_TOOLS:
            return self._tool_error(f"tool not exposed over MCP: {name}")
        registry = self._get_registry()
        tool = registry.get(name)
        if tool is None:
            return self._tool_error(f"tool unavailable: {name}")
        validation_errors = registry.validate_args(name, arguments)
        if validation_errors:
            return self._tool_error("; ".join(validation_errors))
        try:
            result = tool.execute(**arguments)
        except Exception as exc:
            return self._tool_error(f"{type(exc).__name__}: {exc}")
        output = result.output
        if not isinstance(output, str):
            output = json.dumps(output, default=str, indent=2)
        if not result.success:
            return self._tool_error(result.error or output or "tool failed")
        return {"content": [{"type": "text", "text": output}], "isError": False}

    @staticmethod
    def _tool_error(message: str) -> Dict[str, Any]:
        return {"content": [{"type": "text", "text": message}], "isError": True}

    def handle(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = request.get("method", "")
        request_id = request.get("id")

        if method == "initialize":
            return self._response(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        if method in ("notifications/initialized", "initialized"):
            return None
        if method == "tools/list":
            return self._response(request_id, {"tools": self._tool_definitions()})
        if method == "tools/call":
            params = request.get("params", {})
            result = self._call_tool(params.get("name", ""), params.get("arguments", {}) or {})
            return self._response(request_id, result)
        if method == "ping":
            return self._response(request_id, {})
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }

    @staticmethod
    def _response(request_id, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def serve_stdio(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    TwinMCPServer().serve_stdio()
