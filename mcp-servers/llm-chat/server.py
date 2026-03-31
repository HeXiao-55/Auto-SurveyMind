#!/usr/bin/env python3
"""Generic LLM Chat MCP Server — supports any OpenAI-compatible API.

Refactored to inherit from tools/mcp_base.py, eliminating ~200 lines
of boilerplate duplication with minimax-chat/server.py.

Environment Variables (override class attributes)
-------------------------------------------------
    LLM_API_KEY      API key (required)
    LLM_BASE_URL     API base URL (default: https://api.openai.com/v1)
    LLM_MODEL        Model name (default: gpt-4o)
    LLM_SERVER_NAME  Server name for MCP (default: llm-chat)
    LLM_MAX_TOKENS   max_tokens per request (default: 4096)
    LLM_TIMEOUT      HTTP timeout in seconds (default: 300)

Supported Providers (examples)
------------------------------
    OpenAI:  LLM_BASE_URL=https://api.openai.com/v1 LLM_MODEL=gpt-4o
    DeepSeek: LLM_BASE_URL=https://api.deepseek.com/v1 LLM_MODEL=deepseek-chat
    Kimi:    LLM_BASE_URL=https://api.moonshot.cn/v1 LLM_MODEL=moonshot-v1-32k
    MiniMax: LLM_BASE_URL=https://api.minimax.chat/v1 LLM_MODEL=MiniMax-M2.5
"""

import os
import sys
from pathlib import Path

# Allow tools/ to be imported without pip install -ing the package
_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

import httpx
from tools.mcp_base import MCPServer


class LLMServer(MCPServer):
    """OpenAI-compatible LLM MCP server backed by tools/mcp_base.py."""

    SERVER_NAME = os.environ.get("LLM_SERVER_NAME", "llm-chat")
    DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
    BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    API_KEY = os.environ.get("LLM_API_KEY", "")
    HTTP_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "300.0"))
    MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "4096"))

    # ── Abstract method implementations ─────────────────────────────────────

    def _get_tool_schema(self) -> dict:
        return {
            "name": "chat",
            "description": (
                f"Send a message to {self.DEFAULT_MODEL} and get a response. "
                f"Use this for research reviews, code analysis, and general AI tasks."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to send",
                    },
                    "model": {
                        "type": "string",
                        "description": f"Model to use (default: {self.DEFAULT_MODEL})",
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
        """Call the configured OpenAI-compatible LLM API."""
        if not self.API_KEY:
            return "", "LLM_API_KEY environment variable is not set"

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
    LLMServer().run()
