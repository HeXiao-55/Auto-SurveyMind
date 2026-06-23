#!/usr/bin/env python3
"""DeepXiv MCP bridge for SurveyMind.

Exposes three tools:
- search_papers
- get_paper
- download_pdf

This server shells out to the DeepXiv CLI and normalizes outputs for
SurveyMind compatibility.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


class DeepXivMcpServer:
    def __init__(self) -> None:
        self.deepxiv_bin = os.environ.get(
            "DEEPXIV_BIN",
            str(Path.home() / "Library" / "Python" / "3.12" / "bin" / "deepxiv"),
        )
        self.timeout = int(os.environ.get("DEEPXIV_TIMEOUT_SECONDS", "120"))
        self.default_format = os.environ.get("DEEPXIV_DEFAULT_FORMAT", "json")

    # -----------------------------
    # JSON-RPC framing
    # -----------------------------
    def _read_message(self) -> dict[str, Any] | None:
        first = sys.stdin.buffer.readline()
        if not first:
            return None
        line = first.decode("utf-8").rstrip("\r\n")

        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            while True:
                hdr = sys.stdin.buffer.readline()
                if not hdr:
                    return None
                if hdr in (b"\r\n", b"\n"):
                    break
            body = sys.stdin.buffer.read(content_length)
            return json.loads(body.decode("utf-8"))

        if line.startswith("{"):
            return json.loads(line)

        return None

    def _send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("utf-8")
        sys.stdout.buffer.write(header + data)
        sys.stdout.buffer.flush()

    # -----------------------------
    # Tool schemas
    # -----------------------------
    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_papers",
                "description": "Search papers through DeepXiv and return normalized records.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                        "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                        "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                        "mode": {"type": "string", "enum": ["bm25", "vector", "hybrid"], "default": "hybrid"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_paper",
                "description": "Get one paper in brief/head/section mode from DeepXiv.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "paper_id": {"type": "string"},
                        "mode": {"type": "string", "enum": ["brief", "head", "section"], "default": "brief"},
                        "section": {"type": "string"},
                    },
                    "required": ["paper_id"],
                },
            },
            {
                "name": "download_pdf",
                "description": "Download PDF for a paper id using DeepXiv metadata.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "paper_id": {"type": "string"},
                        "output_dir": {"type": "string"},
                    },
                    "required": ["paper_id", "output_dir"],
                },
            },
        ]

    # -----------------------------
    # Helpers
    # -----------------------------
    def _run_cli(self, args: list[str]) -> tuple[str, str | None]:
        cmd = [self.deepxiv_bin] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError:
            return "", f"DeepXiv binary not found: {self.deepxiv_bin}"
        except subprocess.TimeoutExpired:
            return "", f"DeepXiv command timeout ({self.timeout}s): {' '.join(cmd)}"
        except Exception as exc:
            return "", str(exc)

        if result.returncode != 0:
            return "", (result.stderr or result.stdout or "unknown error").strip()
        return result.stdout, None

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | list[Any] | None:
        s = text.strip()
        if not s:
            return None

        # DeepXiv may print informational text before JSON.
        first_obj = s.find("{")
        first_arr = s.find("[")
        starts = [x for x in [first_obj, first_arr] if x >= 0]
        if not starts:
            return None
        idx = min(starts)
        candidate = s[idx:]
        try:
            return json.loads(candidate)
        except Exception:
            return None

    @staticmethod
    def _normalize_search_item(item: dict[str, Any], query: str) -> dict[str, Any]:
        paper_id = str(item.get("arxiv_id") or item.get("id") or "").strip()
        categories = item.get("categories") or []
        if categories and isinstance(categories[0], str) and " " in categories[0]:
            categories = [c for c in categories[0].split() if c]
        return {
            "id": paper_id,
            "arxiv_id": paper_id,
            "title": item.get("title", ""),
            "authors": item.get("authors", []),
            "abstract": item.get("abstract", ""),
            "published": item.get("publish_at", "") or item.get("published", ""),
            "categories": categories,
            "pdf_url": f"https://arxiv.org/pdf/{paper_id}" if paper_id else "",
            "abs_url": f"https://arxiv.org/abs/{paper_id}" if paper_id else "",
            "query_hit": [query],
            "provider_meta": {
                "score": item.get("score"),
                "token_count": item.get("token_count"),
                "status": item.get("status"),
            },
        }

    # -----------------------------
    # Tool implementations
    # -----------------------------
    def _tool_search_papers(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        limit = int(arguments.get("limit", 20))
        mode = str(arguments.get("mode", "hybrid"))
        date_from = str(arguments.get("date_from", "")).strip()
        date_to = str(arguments.get("date_to", "")).strip()

        args = ["search", query, "--limit", str(limit), "--format", "json", "--mode", mode]
        if date_from:
            args.extend(["--date-from", date_from])
        if date_to:
            args.extend(["--date-to", date_to])

        out, err = self._run_cli(args)
        if err:
            raise RuntimeError(err)
        payload = self._extract_json(out)
        if not isinstance(payload, dict):
            raise RuntimeError("DeepXiv search returned non-JSON payload")

        rows = payload.get("results", []) if isinstance(payload.get("results"), list) else []
        normalized = [self._normalize_search_item(r, query) for r in rows if isinstance(r, dict)]
        return {
            "query": query,
            "total": payload.get("total", len(normalized)),
            "results": normalized,
        }

    def _tool_get_paper(self, arguments: dict[str, Any]) -> dict[str, Any]:
        paper_id = str(arguments.get("paper_id", "")).strip()
        if not paper_id:
            raise ValueError("paper_id is required")
        mode = str(arguments.get("mode", "brief"))

        if mode == "brief":
            out, err = self._run_cli(["paper", paper_id, "--brief"])
            if err:
                raise RuntimeError(err)
            return {"paper_id": paper_id, "mode": mode, "content": out.strip()}

        if mode == "head":
            out, err = self._run_cli(["paper", paper_id, "--head"])
            if err:
                raise RuntimeError(err)
            payload = self._extract_json(out)
            if payload is None:
                return {"paper_id": paper_id, "mode": mode, "content": out.strip()}
            return {"paper_id": paper_id, "mode": mode, "content": payload}

        if mode == "section":
            section = str(arguments.get("section", "")).strip()
            if not section:
                raise ValueError("section is required when mode=section")
            out, err = self._run_cli(["paper", paper_id, "--section", section])
            if err:
                raise RuntimeError(err)
            return {"paper_id": paper_id, "mode": mode, "section": section, "content": out.strip()}

        raise ValueError("mode must be one of: brief, head, section")

    def _tool_download_pdf(self, arguments: dict[str, Any]) -> dict[str, Any]:
        paper_id = str(arguments.get("paper_id", "")).strip()
        output_dir = str(arguments.get("output_dir", "")).strip()
        if not paper_id:
            raise ValueError("paper_id is required")
        if not output_dir:
            raise ValueError("output_dir is required")

        out_dir = Path(output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{paper_id}.pdf"
        if out_path.exists() and out_path.stat().st_size > 1024:
            return {
                "arxiv_id": paper_id,
                "path": str(out_path),
                "size_kb": round(out_path.stat().st_size / 1024, 2),
                "skipped": True,
            }

        # Resolve canonical source URL via deepxiv --head.
        head_out, err = self._run_cli(["paper", paper_id, "--head"])
        if err:
            raise RuntimeError(f"failed to fetch paper head: {err}")
        payload = self._extract_json(head_out)
        if not isinstance(payload, dict):
            raise RuntimeError("paper --head did not return JSON")

        src_url = str(payload.get("src_url") or payload.get("pdf_url") or f"https://arxiv.org/pdf/{paper_id}")
        req = urllib.request.Request(src_url, headers={"User-Agent": "SurveyMind-DeepXiv-MCP/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = resp.read()

        if len(data) < 1024:
            raise RuntimeError(f"downloaded file too small from {src_url}")
        out_path.write_bytes(data)

        return {
            "arxiv_id": paper_id,
            "path": str(out_path),
            "size_kb": round(out_path.stat().st_size / 1024, 2),
            "skipped": False,
            "source_url": src_url,
        }

    # -----------------------------
    # Dispatch
    # -----------------------------
    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_papers":
            return self._tool_search_papers(arguments)
        if name == "get_paper":
            return self._tool_get_paper(arguments)
        if name == "download_pdf":
            return self._tool_download_pdf(arguments)
        raise ValueError(f"unknown tool: {name}")

    def run(self) -> None:
        while True:
            req = self._read_message()
            if req is None:
                break

            method = req.get("method")
            request_id = req.get("id")
            params = req.get("params", {})

            if request_id is None and method == "notifications/initialized":
                continue

            if method == "initialize":
                self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "deepxiv", "version": "0.1.0"},
                        },
                    }
                )
                continue

            if method == "ping":
                self._send({"jsonrpc": "2.0", "id": request_id, "result": {}})
                continue

            if method == "tools/list":
                self._send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": self._tools()}})
                continue

            if method == "tools/call":
                try:
                    tool_name = params.get("name", "")
                    arguments = params.get("arguments", {}) or {}
                    result = self._call_tool(tool_name, arguments)
                    self._send(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
                        }
                    )
                except Exception as exc:
                    self._send(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [{"type": "text", "text": f"Error: {exc}"}],
                                "isError": True,
                            },
                        }
                    )
                continue

            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    DeepXivMcpServer().run()
