import contextlib
import json
import logging
import os
import sys
import warnings
from textwrap import dedent
from typing import Any, Dict, Generator, Iterable, List, Optional

import anthropic
import numpy as np
import openai
import pymupdf  # type: ignore[import-untyped]
import pymupdf4llm  # type: ignore[import-untyped]
from pypdf import PdfReader

from ai_scientist.llm import (
    extract_json_between_markers,
    get_batch_responses_from_llm,
    get_response_from_llm,
)

# Suppress PyMuPDF layout warning
warnings.filterwarnings("ignore", message=".*pymupdf_layout.*", category=UserWarning)
warnings.filterwarnings("ignore", message="Consider using the pymupdf_layout package.*")


@contextlib.contextmanager
def suppress_pymupdf_output() -> Generator[None, None, None]:
    """Context manager to suppress pymupdf's direct print statements."""
    original_stderr = sys.stderr
    try:
        # Redirect stderr to devnull to suppress pymupdf's print statements
        with open(os.devnull, "w") as devnull:
            sys.stderr = devnull
            yield
    finally:
        sys.stderr = original_stderr


logger = logging.getLogger(__name__)

reviewer_system_prompt_base = (
    "You are an experienced ML researcher completing a NeurIPS-style review. "
    "Provide careful, evidence-based judgments that calibrate to historical scoring standards."
)
reviewer_system_prompt_strict = reviewer_system_prompt_base + (
    " When information is missing or claims appear unsupported, lower the affected scores and explain why."
)
reviewer_system_prompt_balanced = reviewer_system_prompt_base + (
    " Reward strong evidence and novelty, but also acknowledge incremental contributions when they are solid. "
    "Do not default to middling scores—use the entire scale when justified."
)

template_instructions = """
Respond in the following format:

THOUGHT:
<THOUGHT>

REVIEW JSON:
```json
<JSON>
```

In <THOUGHT>, first briefly discuss your intuitions and reasoning for the evaluation.
Detail your high-level arguments, necessary choices and desired outcomes of the review.
Do not make generic comments here, but be specific to your current paper.
Treat this as the note-taking phase of your review.

In <JSON>, provide the review in JSON format with the following fields in the order:
- "Summary": A summary of the paper content and its contributions.
- "Strengths": A list of strengths of the paper.
- "Weaknesses": A list of weaknesses of the paper.
- "Originality": A rating from 1 to 4 (low, medium, high, very high).
- "Quality": A rating from 1 to 4 (low, medium, high, very high).
- "Clarity": A rating from 1 to 4 (low, medium, high, very high).
- "Significance": A rating from 1 to 4 (low, medium, high, very high).
- "Questions": A set of clarifying questions to be answered by the paper authors.
- "Limitations": A set of limitations and potential negative societal impacts of the work.
- "Ethical Concerns": A boolean value indicating whether there are ethical concerns.
- "Soundness": A rating from 1 to 4 (poor, fair, good, excellent).
- "Presentation": A rating from 1 to 4 (poor, fair, good, excellent).
- "Contribution": A rating from 1 to 4 (poor, fair, good, excellent).
- "Overall": A rating from 1 to 10 (very strong reject to award quality).
- "Confidence": A rating from 1 to 5 (low, medium, high, very high, absolute).
- "Decision": A decision that has to be one of the following: Accept, Reject.

For the "Decision" field, don't use Weak Accept, Borderline Accept, Borderline Reject, or Strong Reject. Instead, only use Accept or Reject.
This JSON will be automatically parsed, so ensure the format is precise.
"""

neurips_form = (
    """
## Review Form
You are filling out the standard NeurIPS review. Summaries should be faithful, and numerical scores must reflect the evidence within the paper and the auxiliary context provided.

1. **Summary** – State the main contributions factually. Authors should agree with this section.
2. **Strengths & Weaknesses** – Evaluate the work along originality, technical quality, clarity, and significance. Cite concrete passages, experiments, or missing elements.
3. **Questions for Authors** – Ask targeted questions whose answers could change your opinion or clarify uncertainty.
4. **Limitations & Ethical Considerations** – Mention stated limitations and any missing discussion of societal impact. Suggest improvements when gaps exist.
5. **Numerical Scores** – Use the scales below. Each score must align with the justification you provide.
   - Originality, Quality, Clarity, Significance, Soundness, Presentation, Contribution: 1 (poor/low) – 4 (excellent/very high)
   - Overall: 1–10 using the NeurIPS anchors (6 ≈ solid accept, 4–5 borderline, 1–3 reject, 7–8 strong accept, 9–10 award level)
   - Confidence: 1 (guessing) – 5 (certain; checked details)
6. **Decision** – Output only `Accept` or `Reject`, reflecting the balance of evidence. Borderline cases must still pick one side.

Always ground your reasoning in the supplied paper, context snippets, or obvious missing elements. Reward rigorous negative results and honest discussion of limitations.
"""
    + template_instructions
)

CALIBRATION_GUIDE = dedent(
    """
Calibration guidance:
- Use the full 1–4 and 1–10 scales. Do not default to 3/4 or 5/10 when unsure.
- If experiments are missing or inconclusive, lower Quality and Significance rather than the entire review.
- Strong clarity or reproducibility should be rewarded even if results are incremental.
- Confidence should reflect how well the supplied context addresses your questions (e.g., lack of metrics → low confidence).
"""
)


def _format_mapping_block(title: str, data: Dict[str, Any]) -> str:
    if not data:
        return ""
    lines = [title + ":"]
    for key, value in data.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lines.append(f"- {key}: {text}")
    return "\n".join(lines)


def _render_context_block(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return ""

    blocks: list[str] = []

    overview = context.get("idea_overview")
    if isinstance(overview, dict):
        block = _format_mapping_block("Idea Overview", overview)
        if block:
            blocks.append(block)

    signals = context.get("paper_signals")
    if isinstance(signals, dict):
        block = _format_mapping_block("Automatic Checks", signals)
        if block:
            blocks.append(block)

    section_highlights = context.get("section_highlights")
    if isinstance(section_highlights, dict):
        for section, text in section_highlights.items():
            if not text:
                continue
            blocks.append(f"{section} Highlights:\n{text}")

    novelty = context.get("novelty_review")
    if novelty:
        if isinstance(novelty, str):
            blocks.append(f"Novelty Scan:\n{novelty}")
        elif isinstance(novelty, Iterable):
            formatted = "\n".join(f"- {item}" for item in novelty if item)
            if formatted:
                blocks.append(f"Novelty Scan:\n{formatted}")

    additional = context.get("additional_notes")
    if additional:
        blocks.append(f"Additional Notes:\n{additional}")

    blocks = [b for b in blocks if b]
    return "\n\n".join(blocks)


def perform_review(
    text: str,
    model: str,
    client: openai.OpenAI | anthropic.Anthropic,
    temperature: float,
    *,
    context: dict[str, str] | None = None,
    num_reflections: int = 2,
    num_fs_examples: int = 1,
    num_reviews_ensemble: int = 3,
    msg_history: list[dict[str, Any]] | None = None,
    return_msg_history: bool = False,
    reviewer_system_prompt: str = reviewer_system_prompt_balanced,
    review_instruction_form: str = neurips_form,
    calibration_notes: str = CALIBRATION_GUIDE,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | dict[str, Any]:
    context_block = _render_context_block(context)
    base_prompt = review_instruction_form
    if calibration_notes:
        base_prompt += f"\n\nCalibration notes:\n{calibration_notes.strip()}\n"
    if context_block:
        base_prompt += f"\n\nContext for your evaluation:\n{context_block}\n"

    if num_fs_examples > 0:
        fs_prompt = get_review_fewshot_examples(num_fs_examples)
        base_prompt += fs_prompt

    base_prompt += f"""
Here is the paper you are asked to review:
```
{text}
```"""

    review: Optional[Dict[str, Any]] = None
    if num_reviews_ensemble > 1:
        llm_reviews, msg_histories = get_batch_responses_from_llm(
            base_prompt,
            model=model,
            client=client,
            system_message=reviewer_system_prompt,
            print_debug=False,
            msg_history=msg_history,
            temperature=temperature,
            n_responses=num_reviews_ensemble,
        )
        parsed_reviews: List[Dict[str, Any]] = []
        for idx, rev in enumerate(llm_reviews):
            try:
                parsed = extract_json_between_markers(rev)
            except Exception as exc:
                logger.warning(f"Ensemble review {idx} failed: {exc}")
                continue
            if parsed:
                parsed_reviews.append(parsed)

        if parsed_reviews:
            review = get_meta_review(model, client, temperature, parsed_reviews)
            if review is None:
                review = parsed_reviews[0]
            for score, limits in [
                ("Originality", (1, 4)),
                ("Quality", (1, 4)),
                ("Clarity", (1, 4)),
                ("Significance", (1, 4)),
                ("Soundness", (1, 4)),
                ("Presentation", (1, 4)),
                ("Contribution", (1, 4)),
                ("Overall", (1, 10)),
                ("Confidence", (1, 5)),
            ]:
                collected: List[float] = []
                for parsed in parsed_reviews:
                    value = parsed.get(score)
                    if isinstance(value, (int, float)) and limits[0] <= value <= limits[1]:
                        collected.append(float(value))
                if collected:
                    review[score] = float(np.round(np.mean(collected), 2))
            msg_history = msg_histories[0][:-1]
            msg_history += [
                {
                    "role": "assistant",
                    "content": f"""
THOUGHT:
I will start by aggregating the opinions of {num_reviews_ensemble} reviewers that I previously obtained.

REVIEW JSON:
```json
{json.dumps(review)}
```
""",
                }
            ]
        else:
            logger.warning(
                "Warning: Failed to parse ensemble reviews; falling back to single review run."
            )

    if review is None:
        llm_review, msg_history = get_response_from_llm(
            base_prompt,
            model=model,
            client=client,
            system_message=reviewer_system_prompt,
            print_debug=False,
            msg_history=msg_history,
            temperature=temperature,
        )
        review = extract_json_between_markers(llm_review)

    if num_reflections > 1 and review is not None:
        for _ in range(num_reflections - 1):
            reflection_text, msg_history = get_response_from_llm(
                reviewer_reflection_prompt,
                client=client,
                model=model,
                system_message=reviewer_system_prompt,
                msg_history=msg_history,
                temperature=temperature,
            )
            updated_review = extract_json_between_markers(reflection_text)
            if updated_review is not None:
                review = updated_review
            if "I am done" in reflection_text:
                break

    if review is None:
        review = {}
    if return_msg_history:
        return review, (msg_history or [])
    return review


reviewer_reflection_prompt = """Round {current_round}/{num_reflections}.
In your thoughts, first carefully consider the accuracy and soundness of the review you just created.
Include any other factors that you think are important in evaluating the paper.
Ensure the review is clear and concise, and the JSON is in the correct format.
Do not make things overly complicated.
In the next attempt, try and refine and improve your review.
Stick to the spirit of the original review unless there are glaring issues.

Respond in the same format as before:
THOUGHT:
<THOUGHT>

REVIEW JSON:
```json
<JSON>
```

If there is nothing to improve, simply repeat the previous JSON EXACTLY after the thought and include "I am done" at the end of the thoughts but before the JSON.
ONLY INCLUDE "I am done" IF YOU ARE MAKING NO MORE CHANGES."""


def load_paper(pdf_path: str, num_pages: int | None = None, min_size: int = 100) -> str:
    try:
        text: str
        if num_pages is None:
            text = str(pymupdf4llm.to_markdown(pdf_path))
        else:
            reader = PdfReader(pdf_path)
            min_pages = min(len(reader.pages), num_pages)
            text = str(pymupdf4llm.to_markdown(pdf_path, pages=list(range(min_pages))))
        if len(text) < min_size:
            raise Exception("Text too short")
    except Exception as e:
        logger.warning(f"Error with pymupdf4llm, falling back to pymupdf: {e}")
        try:
            with suppress_pymupdf_output():
                doc = pymupdf.open(pdf_path)
            if num_pages:
                doc = doc[:num_pages]
            text = ""
            for page in doc:
                text += page.get_text()
            if len(text) < min_size:
                raise Exception("Text too short")
        except Exception as e:
            logger.warning(f"Error with pymupdf, falling back to pypdf: {e}")
            reader = PdfReader(pdf_path)
            if num_pages is None:
                pages = reader.pages
            else:
                pages = reader.pages[:num_pages]
            text = "".join(page.extract_text() for page in pages)
            if len(text) < min_size:
                raise Exception("Text too short")
    return text


def load_review(json_path: str) -> str:
    with open(json_path, "r") as json_file:
        loaded = json.load(json_file)
    return str(loaded["review"])


dir_path = os.path.dirname(os.path.realpath(__file__))

fewshot_papers = [
    os.path.join(dir_path, "fewshot_examples/132_automated_relational.pdf"),
    os.path.join(dir_path, "fewshot_examples/attention.pdf"),
    os.path.join(dir_path, "fewshot_examples/2_carpe_diem.pdf"),
]

fewshot_reviews = [
    os.path.join(dir_path, "fewshot_examples/132_automated_relational.json"),
    os.path.join(dir_path, "fewshot_examples/attention.json"),
    os.path.join(dir_path, "fewshot_examples/2_carpe_diem.json"),
]


def get_review_fewshot_examples(num_fs_examples: int = 1) -> str:
    fewshot_prompt = """
Below are some sample reviews, copied from previous machine learning conferences.
Note that while each review is formatted differently according to each reviewer's style, the reviews are well-structured and therefore easy to navigate.
"""
    for paper_path, review_path in zip(
        fewshot_papers[:num_fs_examples], fewshot_reviews[:num_fs_examples]
    ):
        txt_path = paper_path.replace(".pdf", ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r") as f:
                paper_text = f.read()
        else:
            paper_text = load_paper(paper_path)
        review_text = load_review(review_path)
        fewshot_prompt += f"""
Paper:

```
{paper_text}
```

Review:

```
{review_text}
```
"""
    return fewshot_prompt


meta_reviewer_system_prompt = """You are an Area Chair at a machine learning conference.
You are in charge of meta-reviewing a paper that was reviewed by {reviewer_count} reviewers.
Your job is to aggregate the reviews into a single meta-review in the same format.
Be critical and cautious in your decision, find consensus, and respect the opinion of all the reviewers."""


def get_meta_review(
    model: str,
    client: openai.OpenAI | anthropic.Anthropic,
    temperature: float,
    reviews: list[dict[str, Any]],
) -> dict[str, Any] | None:
    review_text = ""
    for i, r in enumerate(reviews):
        review_text += f"""
Review {i + 1}/{len(reviews)}:
```
{json.dumps(r)}
```
"""
    base_prompt = neurips_form + review_text
    llm_review, _ = get_response_from_llm(
        base_prompt,
        model=model,
        client=client,
        system_message=meta_reviewer_system_prompt.format(reviewer_count=len(reviews)),
        print_debug=False,
        msg_history=None,
        temperature=temperature,
    )
    meta_review = extract_json_between_markers(llm_review)
    return meta_review
