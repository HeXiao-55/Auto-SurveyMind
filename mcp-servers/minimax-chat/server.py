#!/usr/bin/env python3
"""MiniMax Chat MCP Server — calls MiniMax Chat Completions API.

Refactored to inherit from tools/mcp_base.py, eliminating ~200 lines
of boilerplate duplication with llm-chat/server.py.

Environment Variables
--------------------
    MINIMAX_API_KEY   MiniMax API key (required)
    MINIMAX_BASE_URL  API base URL (default: https://api.minimax.chat/v1)
    MINIMAX_MODEL     Model name (default: MiniMax-M2.5)
"""

import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

import httpx
from tools.mcp_base import MCPServer


class MiniMaxServer(MCPServer):
    """MiniMax MCP server backed by tools/mcp_base.py."""

    SERVER_NAME = "minimax-chat"
    DEFAULT_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")
    BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    API_KEY = os.environ.get("MINIMAX_API_KEY", "")
    HTTP_TIMEOUT = 120.0
    MAX_TOKENS = 4096

    # ── Abstract method implementations ─────────────────────────────────────

    def _get_tool_schema(self) -> dict:
        return {
            "name": "minimax_chat",
            "description": (
                "Send a message to MiniMax M2.5 model and get a response. "
                "Use this for research reviews, code analysis, and general AI tasks."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to send to MiniMax",
                    },
                    "model": {
                        "type": "string",
                        "description": f"Model to use (default: {self.DEFAULT_MODEL})",
                        "default": self.DEFAULT_MODEL,
                    },
                    "system": {
                        "type": "string",
                        "description": "Optional system prompt",
                    },
                },
                "required": ["prompt"],
            },
        }

    def _call_api(
        self,
        messages: list[dict],
        model: str | None,
    ) -> tuple[str, str | None]:
        """Call the MiniMax Chat Completions API."""
        if not self.API_KEY:
            return "", "MINIMAX_API_KEY environment variable is not set"

        url = f"{self.BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.API_KEY}",
        }
        payload = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": self.MAX_TOKENS,
        }

        try:
            with httpx.Client(timeout=self.HTTP_TIMEOUT) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                return "", f"API error {resp.status_code}: {resp.text[:500]}"
            data = resp.json()
            return data["choices"][0]["message"]["content"], None
        except Exception as exc:
            return "", str(exc)


if __name__ == "__main__":
    MiniMaxServer().run()
