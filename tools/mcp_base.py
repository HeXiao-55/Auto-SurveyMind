#!/usr/bin/env python3
"""Base framework for SurveyMind MCP servers.

Eliminates the ~80% boilerplate duplication between llm-chat and minimax-chat
servers by factoring out:

- Unbuffered stdin/stdout setup
- ``debug_log`` / ``log_error`` with proper exception handling
- ``send_response`` / ``send_notification`` (both MCP and NDJSON modes)
- ``read_message`` (MCP Content-Length and NDJSON formats)
- ``main`` event loop with graceful shutdown

Subclasses only need to implement ``_call_api()`` and ``_get_tool_schema()``.

Usage (example for a new provider)
----------------------------------
    from mcp_base import MCPServer, api_call

    class MyServer(MCPServer):
        SERVER_NAME = "my-chat"
        DEFAULT_MODEL = "my-model"
        BASE_URL = os.environ.get("MY_BASE_URL", "https://api.example.com/v1")
        API_KEY = os.environ.get("MY_API_KEY", "")

        def _get_tool_schema(self) -> dict:
            return {...}

        def _call_api(self, messages: list[dict], model: str | None) -> tuple[str, str | None]:
            # Return (content, error)
            ...

    if __name__ == "__main__":
        MyServer().run()

Environment Variables (override class attributes)
-------------------------------------------------
    MY_API_KEY, MY_BASE_URL, MY_MODEL, MY_SERVER_NAME
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Global debug log path (override via env var SURVEYMIND_MCP_DEBUG) ────────────

_MCP_DEBUG_LOG = os.environ.get(
    "SURVEYMIND_MCP_DEBUG",
    os.path.join(tempfile.gettempdir(), "surveymind-mcp-debug.log"),
)


def debug_log(msg: str) -> None:
    """Write a timestamped message to the debug log file.

    Unlike the old bare ``except: pass`` pattern, logging failures are reported
    to stderr so operators can spot config errors.
    """
    try:
        with open(_MCP_DEBUG_LOG, "a") as fh:
            fh.write(f"{datetime.datetime.now()}: {msg}\n")
            fh.flush()
    except Exception as exc:
        print(f"[mcp-base debug_log failure: {exc}] {msg}", file=sys.stderr)


def log_error(msg: str) -> None:
    """Write a timestamped ERROR to the debug log file."""
    debug_log(f"ERROR: {msg}")


# ── Unbuffered binary I/O setup ─────────────────────────────────────────────────

def _setup_unbuffered_io() -> None:
    """Switch stdout/stdin to unbuffered binary mode (required by MCP protocol)."""
    sys.stdout = os.fdopen(sys.stdout.fileno(), "wb", buffering=0)
    sys.stdin = os.fdopen(sys.stdin.fileno(), "rb", buffering=0)


# ── MCP Protocol helpers ───────────────────────────────────────────────────────

class MCPProtocol:
    """Handles MCP message framing (Content-Length header or NDJSON)."""

    def __init__(self) -> None:
        self._use_ndjson = False

    def send_response(self, response: dict) -> None:
        """Send a JSON-RPC response using the negotiated protocol."""
        payload = json.dumps(response, separators=(",", ":")).encode("utf-8")
        if self._use_ndjson:
            output = payload + b"\n"
        else:
            header = f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8")
            output = header + payload
        sys.stdout.write(output)
        sys.stdout.flush()

    def send_notification(self, method: str, params: Optional[dict] = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        self.send_response({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def read_message(self) -> Optional[dict]:
        """Read one JSON-RPC message from stdin.

        Supports:
        - Standard MCP: ``Content-Length: N\\r\\n\\r\\n{json}``
        - NDJSON/line-delimited: ``{json}\\n``

        Returns None on EOF (server should exit).
        """
        first_line_bytes = sys.stdin.readline()
        if not first_line_bytes:
            return None

        first_line = first_line_bytes.decode("utf-8").rstrip("\r\n")

        # MCP Content-Length framing
        if first_line.lower().startswith("content-length:"):
            try:
                content_length = int(first_line.split(":", 1)[1].strip())
            except ValueError:
                log_error(f"Invalid Content-Length header: {first_line}")
                return None

            # Consume remaining headers until blank line
            while True:
                hdr = sys.stdin.readline()
                if not hdr:
                    return None
                if hdr.decode("utf-8").rstrip("\r\n") == "":
                    break

            body = sys.stdin.read(content_length)
            if len(body) < content_length:
                log_error(f"Incomplete body: expected {content_length}, got {len(body)}")
                return None

            try:
                return json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                log_error(f"JSON decode error: {exc}")
                return None

        # NDJSON mode — the line itself is the JSON
        if first_line.startswith("{") or first_line.startswith("["):
            self._use_ndjson = True
            try:
                return json.loads(first_line)
            except json.JSONDecodeError as exc:
                log_error(f"NDJSON decode error: {exc}")
                return None

        log_error(f"Unexpected first line format: {first_line[:100]}")
        return None


# ── Abstract base class ────────────────────────────────────────────────────────

class MCPServer(ABC):
    """Base class for SurveyMind MCP servers.

    Subclasses MUST set the following class attributes::

        SERVER_NAME   : str   — used in logs and protocol negotiation
        DEFAULT_MODEL : str   — fallback model when not specified
        BASE_URL      : str   — API base URL
        API_KEY       : str   — API key (from env)

    Subclasses MUST implement::

        _get_tool_schema() -> dict
        _call_api(messages: list[dict], model: str | None) -> tuple[str, str | None]
    """

    SERVER_NAME: str = "surveymind-mcp"
    DEFAULT_MODEL: str = "gpt-4o"
    BASE_URL: str = "https://api.openai.com/v1"
    API_KEY: str = ""

    # Subclasses can override to tweak HTTP behaviour
    HTTP_TIMEOUT: float = 120.0
    MAX_TOKENS: int = 4096

    def __init__(self) -> None:
        _setup_unbuffered_io()
        self._protocol = MCPProtocol()
        debug_log(f"=== {self.SERVER_NAME} Starting ===")
        debug_log(f"BASE_URL: {self.BASE_URL}")
        debug_log(f"MODEL: {self.DEFAULT_MODEL}")
        debug_log(f"API_KEY set: {bool(self.API_KEY)}")

    # ── Abstract methods (implement in subclass) ─────────────────────────────

    @abstractmethod
    def _get_tool_schema(self) -> dict:
        """Return the MCP tool schema for tools/list."""
        raise NotImplementedError

    @abstractmethod
    def _call_api(
        self,
        messages: list[dict],
        model: str | None,
    ) -> tuple[str, Optional[str]]:
        """Call the LLM API and return (content, error)."""
        raise NotImplementedError

    # ── Request handlers ──────────────────────────────────────────────────────

    def _handle_initialize(self, request_id: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": self.SERVER_NAME,
                    "version": "2.0.0",
                },
            },
        }

    def _handle_ping(self, request_id: Any) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    def _handle_tools_list(self, request_id: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [self._get_tool_schema()]},
        }

    def _handle_tools_call(self, request_id: Any, params: dict) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        debug_log(f"Tool call: {tool_name}, args length: {len(str(arguments))}")

        content, error = self._dispatch_tool(tool_name, arguments)

        if error:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {error}"}],
                    "isError": True,
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": content}]},
        }

    def _dispatch_tool(self, tool_name: str, arguments: dict) -> tuple[str, Optional[str]]:
        """Dispatch a tool call to the appropriate handler.

        Override this method if your server exposes multiple tools.
        Default behaviour: call the LLM with prompt/system from arguments.
        """
        prompt = arguments.get("prompt", "")
        model = arguments.get("model")
        system = arguments.get("system", "")

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return self._call_api(messages, model)

    def _handle_unknown(self, method: str, request_id: Any) -> dict:
        debug_log(f"Unknown method: {method}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

    def handle_request(self, request: dict) -> Optional[dict]:
        """Process a single JSON-RPC request. Returns response or None (notification)."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        debug_log(f"Handling: {method} id={request_id}")

        # Notifications (no id) — handled but no response sent
        if request_id is None:
            if method == "notifications/initialized":
                debug_log("Client initialised successfully")
            return None

        if method == "initialize":
            return self._handle_initialize(request_id)
        if method == "ping":
            return self._handle_ping(request_id)
        if method == "tools/list":
            return self._handle_tools_list(request_id)
        if method == "tools/call":
            return self._handle_tools_call(request_id, params)
        return self._handle_unknown(method, request_id)

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Run the MCP server event loop (read-stdin, dispatch, respond)."""
        debug_log("Entering main loop")
        while True:
            try:
                request = self._protocol.read_message()
            except Exception as exc:
                log_error(f"read_message exception: {exc}")
                break

            if request is None:
                debug_log("EOF received, exiting gracefully")
                break

            try:
                response = self.handle_request(request)
                if response:
                    self._protocol.send_response(response)
            except Exception as exc:
                log_error(f"Exception handling request: {exc}")
                try:
                    self._protocol.send_response({
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": f"Internal error: {exc}"},
                    })
                except Exception:
                    pass

        debug_log("=== Server Exiting ===")
