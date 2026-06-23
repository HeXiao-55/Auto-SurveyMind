# DeepXiv MCP Server

This MCP server wraps the DeepXiv CLI and exposes paper operations to agents.

## Tools

- `search_papers(query, limit, date_from, date_to, mode)`
- `get_paper(paper_id, mode, section)`
- `download_pdf(paper_id, output_dir)`

## Requirements

- DeepXiv CLI installed (`deepxiv-sdk`)
- Valid `DEEPXIV_TOKEN` (or CLI token already configured)

## Environment Variables

- `DEEPXIV_BIN` (optional): path to `deepxiv` binary  
  Default: `~/Library/Python/3.12/bin/deepxiv`
- `DEEPXIV_TOKEN` (optional): DeepXiv token
- `DEEPXIV_TIMEOUT_SECONDS` (optional): command timeout, default `120`

## Local Run

```bash
python3 mcp-servers/deepxiv/server.py
```

## Example MCP config

```json
{
  "mcpServers": {
    "deepxiv": {
      "command": "python3",
      "args": ["/absolute/path/to/SurveyMind/mcp-servers/deepxiv/server.py"],
      "env": {
        "DEEPXIV_BIN": "/Users/yourname/Library/Python/3.12/bin/deepxiv",
        "DEEPXIV_TOKEN": "dxv_..."
      }
    }
  }
}
```
