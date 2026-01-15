import json
import logging
import re
import traceback
import unicodedata
from pathlib import Path
from typing import NamedTuple

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from ai_scientist.llm import get_structured_response_from_llm
from ai_scientist.prompts.render import render_text
from ai_scientist.semantic_scholar import search_for_papers
from ai_scientist.writeup_artifacts import (
    filter_experiment_summaries,
    load_exp_summaries,
    load_idea_text,
)

logger = logging.getLogger(__name__)


class CitationSearchResponse(BaseModel):
    needs_more_citations: bool = Field(
        ...,
        description=(
            "True if another citation should be collected this round. "
            "When False, leave all other fields empty."
        ),
    )
    description: str = Field(
        ...,
        description=(
            "Purpose of the desired citation and the gap it fills "
            "(only populated when needs_more_citations=True)."
        ),
    )
    query: str = Field(
        ...,
        description=(
            "Semantic Scholar search query to find the desired paper "
            "(only populated when needs_more_citations=True)."
        ),
    )


class CitationSelectionResponse(BaseModel):
    should_add: bool = Field(
        ...,
        description=(
            "True if any of the retrieved papers should be added to the references. "
            "When False, leave selected_indices empty and description blank."
        ),
    )
    selected_indices: list[int] = Field(
        ...,
        description=(
            "Integer indices (0-based) referencing the provided search results. "
            "Only include entries when should_add=True."
        ),
    )
    description: str = Field(
        ...,
        description="Updated rationale for the selected citation(s), their relevance, and where to cite them.",
    )


CITATION_SEARCH_SCHEMA = CitationSearchResponse
CITATION_SELECTION_SCHEMA = CitationSelectionResponse


class _CitationSystemMsgContext(NamedTuple):
    total_rounds: int


class _CitationFirstPromptContext(NamedTuple):
    current_round: int
    total_rounds: int
    idea_text: str
    report: str
    citations: str


class _CitationSecondPromptContext(NamedTuple):
    papers: str


class CitationContext(NamedTuple):
    report: str
    citations: str


def remove_accents_and_clean(s: str) -> str:
    nfkd_form = unicodedata.normalize("NFKD", s)
    ascii_str = nfkd_form.encode("ASCII", "ignore").decode("ascii")
    ascii_str = re.sub(r"[^a-zA-Z0-9:_@{},-]+", "", ascii_str)
    ascii_str = ascii_str.lower()
    return ascii_str


def get_citation_addition(
    model: str,
    context: CitationContext,
    current_round: int,
    total_rounds: int,
    idea_text: str,
    temperature: float,
) -> str | None:
    report, citations = context
    msg_history: list[BaseMessage] = []

    try:
        system_msg = render_text(
            template_name="writeup/citation_system_msg.txt.j2",
            context=_CitationSystemMsgContext(total_rounds=total_rounds)._asdict(),
        )
        first_prompt = render_text(
            template_name="writeup/citation_first_prompt.txt.j2",
            context=_CitationFirstPromptContext(
                current_round=current_round + 1,
                total_rounds=total_rounds,
                idea_text=idea_text,
                report=report,
                citations=citations,
            )._asdict(),
        )
        structured_response, msg_history = get_structured_response_from_llm(
            prompt=first_prompt,
            model=model,
            system_message=system_msg,
            temperature=temperature,
            schema_class=CITATION_SEARCH_SCHEMA,
            msg_history=msg_history,
        )
        if not structured_response.get("needs_more_citations", True):
            logger.info("No more citations needed.")
            return None
        query = structured_response.get("query", "")
        if not isinstance(query, str) or not query.strip():
            logger.warning("Citation search response missing query.")
            return None
        papers = search_for_papers(query)
    except Exception:
        logger.exception("EXCEPTION in get_citation_addition (initial search):")
        return None

    if papers is None:
        logger.warning("No papers found.")
        return None

    paper_strings: list[str] = []
    for i, paper in enumerate(papers):
        paper_strings.append(
            "{i}: {title}. {authors}. {venue}, {year}.\nAbstract: {abstract}".format(
                i=i,
                title=paper["title"],
                authors=paper["authors"],
                venue=paper["venue"],
                year=paper["year"],
                abstract=paper["abstract"],
            )
        )
    papers_str = "\n\n".join(paper_strings)

    try:
        second_prompt = render_text(
            template_name="writeup/citation_second_prompt.txt.j2",
            context=_CitationSecondPromptContext(papers=papers_str)._asdict(),
        )
        selection_response, msg_history = get_structured_response_from_llm(
            prompt=second_prompt,
            model=model,
            system_message=system_msg,
            temperature=temperature,
            schema_class=CITATION_SELECTION_SCHEMA,
            msg_history=msg_history,
        )
        if not selection_response.get("should_add", False):
            logger.info("Do not add any.")
            return None
        selected_indices = selection_response.get("selected_indices", [])
        if not isinstance(selected_indices, list) or not selected_indices:
            logger.warning("Citation selection returned no indices.")
            return None
        if not all(isinstance(idx, int) and 0 <= idx < len(papers) for idx in selected_indices):
            logger.warning("Received invalid citation indices: %s", selected_indices)
            return None
        bibtexs = [papers[i]["citationStyles"]["bibtex"] for i in selected_indices]

        cleaned_bibtexs: list[str] = []
        for bibtex in bibtexs:
            newline_index = bibtex.find("\n")
            cite_key_line = bibtex[:newline_index]
            cite_key_line = remove_accents_and_clean(cite_key_line)
            cleaned_bibtexs.append(cite_key_line + bibtex[newline_index:])
        bibtexs = cleaned_bibtexs

        bibtex_string = "\n".join(bibtexs)
        desc = selection_response.get("description", "")
    except Exception:
        logger.exception("EXCEPTION in get_citation_addition (selecting papers):")
        return None

    references_format = """% {description}
{bibtex}"""

    references_prompt = references_format.format(bibtex=bibtex_string, description=desc)
    return references_prompt


def gather_citations(
    base_path: Path,
    logs_dir: Path,
    model: str,
    temperature: float,
    num_cite_rounds: int,
    run_dir_name: str,
) -> str | None:
    """
    Resume-aware citation gathering that persists progress per run directory.
    """
    cache_base = logs_dir / run_dir_name if run_dir_name else base_path
    cache_base.mkdir(parents=True, exist_ok=True)
    citations_cache_path = cache_base / "cached_citations.bib"
    progress_path = cache_base / "citations_progress.json"

    citations_text = ""
    current_round = 0
    if citations_cache_path.exists() and progress_path.exists():
        try:
            citations_text = citations_cache_path.read_text(encoding="utf-8")
            progress_data = json.loads(progress_path.read_text(encoding="utf-8"))
            current_round = int(progress_data.get("completed_rounds", 0))
            logger.info("Resuming citation gathering from round %s", current_round)
        except Exception:
            logger.warning("Warning: failed to load cached citations; starting fresh.")
            logger.debug(traceback.format_exc())
            citations_text = ""
            current_round = 0

    idea_text = load_idea_text(base_path=base_path, logs_dir=logs_dir, run_dir_name=run_dir_name)
    summaries = load_exp_summaries(base_path=base_path, run_dir_name=run_dir_name)
    filtered_summaries = filter_experiment_summaries(
        exp_summaries=summaries, step_name="citation_gathering"
    )
    filtered_summaries_str = json.dumps(filtered_summaries, indent=2)

    for round_idx in range(current_round, num_cite_rounds):
        try:
            context_for_citation = CitationContext(
                report=filtered_summaries_str,
                citations=citations_text,
            )
            addition = get_citation_addition(
                model=model,
                context=context_for_citation,
                current_round=round_idx,
                total_rounds=num_cite_rounds,
                idea_text=idea_text,
                temperature=temperature,
            )
            if addition is None:
                citations_cache_path.write_text(citations_text, encoding="utf-8")
                progress_path.write_text(
                    json.dumps(
                        {"completed_rounds": round_idx, "status": "completed"},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                break

            title_match = re.search(r" title = {(.*?)}", addition, flags=re.IGNORECASE)
            if title_match:
                new_title = title_match.group(1).lower()
                existing_titles = [
                    t.lower()
                    for t in re.findall(r" title = {(.*?)}", citations_text, flags=re.IGNORECASE)
                ]
                if new_title in existing_titles:
                    logger.info("Skipping duplicate citation: %s", new_title)
                    continue

            citations_text = f"{citations_text}\n{addition}".strip()
            citations_cache_path.write_text(citations_text, encoding="utf-8")
            progress_path.write_text(
                json.dumps(
                    {"completed_rounds": round_idx + 1, "status": "in_progress"},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("EXCEPTION in gather_citations during round %s:", round_idx)
            citations_cache_path.write_text(citations_text, encoding="utf-8")
            progress_path.write_text(
                json.dumps({"completed_rounds": round_idx, "status": "error"}, indent=2),
                encoding="utf-8",
            )
            continue

    return citations_text if citations_text else None
