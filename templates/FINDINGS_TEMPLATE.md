# ⚠️ DEPRECATED — This file is no longer maintained

Content has moved to `findings.md` in the **project root** (`../findings.md`).

All skills should append entries to the root `findings.md` directly.
The root file uses a standardised format with the following sections:

- **Research Findings** — method-level insights (what works, what doesn't, and why)
- **Engineering Findings** — infrastructure and debugging lessons

Each entry uses these fixed fields:
```
- **Finding**:   one-sentence summary (required when "Finding" field is present)
- **Evidence**:  source / supporting metrics or references (paper_id, URL, wandb run)
- **Confidence**: high / medium / low
- **Context**:   when it holds, when it doesn't (optional)
- **Tags**:      comma-separated labels for grep (optional)
```

To initialise or check the root findings.md:
```bash
python3 tools/init_findings.py          # creates if missing
python3 tools/init_findings.py --check   # just check status
python3 tools/init_findings.py --force   # overwrite
```
