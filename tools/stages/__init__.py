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
    run_validate_and_improve,
)
from stages.code_discover import (
    run_code_discover,
)
from stages.repo_setup import (
    run_repo_setup,
)
from stages.repo_reproduce import (
    run_repo_reproduce,
)
from stages.algo_implement import (
    run_algo_implement,
)
from stages.reflect_improve import (
    run_reflect_improve,
)
from stages.model_deliver import (
    run_model_deliver,
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
    "run_validate_and_improve",
    "run_taxonomy_alloc",
    "run_trace_init",
    "run_trace_sync",
    "run_validate",
    "run_code_discover",
    "run_repo_setup",
    "run_repo_reproduce",
    "run_algo_implement",
    "run_reflect_improve",
    "run_model_deliver",
]
