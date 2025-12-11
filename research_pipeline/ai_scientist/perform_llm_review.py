import json
import logging
import os
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Literal, Optional

import numpy as np
import pymupdf  # type: ignore[import-untyped]
import pymupdf4llm  # type: ignore[import-untyped]
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel, Field
from pypdf import PdfReader

from ai_scientist.llm import get_structured_response_from_llm

logger = logging.getLogger(__name__)


class ReviewResponseModel(BaseModel):
    Summary: str = Field(..., description="Faithful summary of the paper and its contributions.")
    Strengths: List[str] = Field(
        default_factory=list,
        description="Bullet-style strengths highlighting novelty, rigor, clarity, etc.",
    )
    Weaknesses: List[str] = Field(
        default_factory=list,
        description="Specific weaknesses or missing evidence.",
    )
    Originality: float = Field(
        ...,
        description="Rating 1-4 (low to very high) for originality/novelty.",
        ge=1,
        le=4,
    )
    Quality: float = Field(
        ...,
        description="Rating 1-4 for technical quality and correctness.",
        ge=1,
        le=4,
    )
    Clarity: float = Field(
        ...,
        description="Rating 1-4 for clarity and exposition quality.",
        ge=1,
        le=4,
    )
    Significance: float = Field(
        ...,
        description="Rating 1-4 for potential impact/significance.",
        ge=1,
        le=4,
    )
    Questions: List[str] = Field(
        default_factory=list,
        description="Clarifying questions for the authors.",
    )
    Limitations: List[str] = Field(
        default_factory=list,
        description="Limitation notes or identified risks.",
    )
    Ethical_Concerns: bool = Field(
        ...,
        alias="Ethical Concerns",
        description="True if ethical concerns exist, False otherwise.",
    )
    Soundness: float = Field(
        ...,
        description="Rating 1-4 for methodological soundness.",
        ge=1,
        le=4,
    )
    Presentation: float = Field(
        ...,
        description="Rating 1-4 for presentation quality.",
        ge=1,
        le=4,
    )
    Contribution: float = Field(
        ...,
        description="Rating 1-4 for contribution level.",
        ge=1,
        le=4,
    )
    Overall: float = Field(
        ...,
        description="Overall rating 1-10 (1=reject, 10=award level).",
        ge=1,
        le=10,
    )
    Confidence: float = Field(
        ...,
        description="Confidence rating 1-5 (1=guessing, 5=absolutely certain).",
        ge=1,
        le=5,
    )
    Decision: Literal["Accept", "Reject"] = Field(
        ...,
        description='Final decision string ("Accept" or "Reject").',
    )
    should_continue: bool = Field(
        default=True,
        description="For reflection loops; set false when no further updates required.",
    )

    class Config:
        allow_population_by_field_name = True


REVIEW_RESPONSE_SCHEMA = ReviewResponseModel

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
Produce a rigorous NeurIPS-style review. Your response must be valid JSON matching the ReviewResponseModel schema (fields defined via the structured output description). Use every field exactly once and respect the documented rating scales. Ground every claim in the paper or provided context.
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
    temperature: float,
    *,
    context: dict[str, str] | None = None,
    num_reflections: int = 2,
    num_fs_examples: int = 1,
    num_reviews_ensemble: int = 3,
    msg_history: list[BaseMessage] | None = None,
    return_msg_history: bool = False,
    reviewer_system_prompt: str = reviewer_system_prompt_balanced,
    review_instruction_form: str = neurips_form,
    calibration_notes: str = CALIBRATION_GUIDE,
) -> ReviewResponseModel | tuple[ReviewResponseModel, list[BaseMessage]]:
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

    def _invoke_review_prompt(
        prompt_text: str,
        history: list[BaseMessage] | None = None,
        *,
        system_msg: str = reviewer_system_prompt,
    ) -> tuple[ReviewResponseModel, list[BaseMessage]]:
        response_dict, updated_history = get_structured_response_from_llm(
            prompt=prompt_text,
            model=model,
            system_message=system_msg,
            temperature=temperature,
            schema_class=REVIEW_RESPONSE_SCHEMA,
            msg_history=history,
        )
        review_model = ReviewResponseModel.model_validate(response_dict)
        return review_model, updated_history

    review: Optional[ReviewResponseModel] = None
    if num_reviews_ensemble > 1:
        parsed_reviews: List[ReviewResponseModel] = []
        histories: List[list[BaseMessage]] = []
        for idx in range(num_reviews_ensemble):
            try:
                parsed, history = _invoke_review_prompt(base_prompt, msg_history)
                parsed_reviews.append(parsed)
                histories.append(history)
            except Exception as exc:
                logger.warning("Ensemble review %s failed: %s", idx, exc)
        if parsed_reviews:
            review = get_meta_review(model, temperature, parsed_reviews)
            if review is None:
                review = parsed_reviews[0]
            parsed_dicts = [parsed.model_dump() for parsed in parsed_reviews]
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
                for parsed_dict in parsed_dicts:
                    value = parsed_dict.get(score)
                    if isinstance(value, (int, float)) and limits[0] <= value <= limits[1]:
                        collected.append(float(value))
                if collected and review is not None:
                    setattr(review, score, float(np.round(np.mean(collected), 2)))
            if review is not None:
                base_history = (
                    histories[0][:-1] if histories and histories[0] else (msg_history or [])
                )
                assistant_message = AIMessage(content=json.dumps(review.model_dump(by_alias=True)))
                msg_history = base_history + [assistant_message]
        else:
            logger.warning(
                "Warning: Failed to parse ensemble reviews; falling back to single review run."
            )

    if review is None:
        review, msg_history = _invoke_review_prompt(base_prompt, msg_history)
    assert review is not None

    if num_reflections > 1 and review is not None:
        for reflection_round in range(num_reflections - 1):
            reflection_prompt = reviewer_reflection_prompt.format(
                current_round=reflection_round + 2,
                num_reflections=num_reflections,
            )
            reflection_response, msg_history = _invoke_review_prompt(
                reflection_prompt,
                msg_history,
            )
            review = reflection_response
            if not reflection_response.should_continue:
                break

    if return_msg_history:
        return review, (msg_history or [])
    return review


reviewer_reflection_prompt = """Round {current_round}/{num_reflections}.
Carefully consider the accuracy and soundness of the review you just created.
Include any factors that you think are important in evaluating the paper.
Ensure the review is clear and concise, and keep the JSON schema identical.
Do not make things overly complicated.
In the next attempt, try and refine and improve your review.
Stick to the spirit of the original review unless there are glaring issues.

Return an updated JSON object following the required schema.
Add a boolean field "should_continue" and set it to false only if no further changes are needed."""


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
    temperature: float,
    reviews: list[ReviewResponseModel],
) -> ReviewResponseModel | None:
    review_text = ""
    for i, r in enumerate(reviews):
        review_text += f"""
Review {i + 1}/{len(reviews)}:
```
{json.dumps(r.model_dump(by_alias=True))}
```
"""
    base_prompt = neurips_form + review_text
    try:
        response_dict, _ = get_structured_response_from_llm(
            prompt=base_prompt,
            model=model,
            system_message=meta_reviewer_system_prompt.format(reviewer_count=len(reviews)),
            temperature=temperature,
            schema_class=REVIEW_RESPONSE_SCHEMA,
            msg_history=None,
        )
    except Exception:
        logger.exception("Failed to generate meta-review.")
        return None
    return ReviewResponseModel.model_validate(response_dict)
