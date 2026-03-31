"""SurveyMind pipeline stage functions.

Each module exposes a ``run_<stage>(args) -> int`` function matching the CLI
``--stage`` argument. Thin stages are grouped in ``_simple.py``; heavy stages
with complex helpers each get their own module.
"""

from stages._simple import (
    run_arxiv_discover,
    run_batch_triage,
    run_brainstorm,
    run_corpus_extract,
    run_taxonomy_alloc,
    run_trace_init,
    run_trace_sync,
    run_validate,
)
from stages.paper_analysis import (
    run_paper_analysis,
)
from stages.paper_download import (
    run_paper_download,
)
from stages.survey_synthesis import (
    run_gap_identify,
    run_survey_write,
    run_taxonomy_build,
)

__all__ = [
    "run_arxiv_discover",
    "run_batch_triage",
    "run_brainstorm",
    "run_corpus_extract",
    "run_paper_analysis",
    "run_paper_download",
    "run_taxonomy_build",
    "run_gap_identify",
    "run_survey_write",
    "run_taxonomy_alloc",
    "run_trace_init",
    "run_trace_sync",
    "run_validate",
]
