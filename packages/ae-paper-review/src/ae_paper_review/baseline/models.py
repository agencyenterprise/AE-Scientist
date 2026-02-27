"""Baseline Pydantic models for paper review (pre-prompt-tuning).

These models match the review schemas from before prompt tuning (commit 553991f).
They do NOT include ClarityIssue fields that were added during prompt tuning.
"""

from typing import List, Literal, Union

from pydantic import BaseModel, Field

from ..models import Conference

# Re-export Conference for convenience
__all__ = [
    "Conference",
    "BaselineNeurIPSReviewModel",
    "BaselineICLRReviewModel",
    "BaselineICMLReviewModel",
    "BaselineReviewModel",
]


# =============================================================================
# NeurIPS 2025 Baseline Review Model
# =============================================================================


class BaselineNeurIPSReviewModel(BaseModel):
    """NeurIPS 2025 baseline review model (pre-prompt-tuning).

    Matches the official NeurIPS 2025 review form structure:
    - Summary, Strengths and Weaknesses (combined), Questions, Limitations
    - Quality/Clarity/Significance/Originality ratings (1-4)
    - Overall (1-6, new 6-point scale), Confidence (1-5)
    - Ethical concerns flag
    """

    summary: str = Field(
        ...,
        alias="Summary",
        description="Brief summary of the paper and its contributions in your own understanding. Do not critique the paper here; the authors should generally agree with a well-written summary.",
    )
    strengths_and_weaknesses: str = Field(
        ...,
        alias="Strengths_And_Weaknesses",
        description="Thorough assessment of strengths and weaknesses, framed as reasons to accept or reject. Cover Quality, Clarity, Significance, and Originality dimensions.",
    )
    questions: List[str] = Field(
        ...,
        alias="Questions",
        description="Around 3-5 actionable questions and suggestions for the authors. Focus on key points where a response could change your opinion, clarify confusion, or address a limitation.",
    )
    limitations: str = Field(
        ...,
        alias="Limitations",
        description="Whether the authors adequately addressed limitations and potential negative societal impact. Say 'yes' if adequate; otherwise provide constructive suggestions.",
    )
    ethical_concerns: bool = Field(
        ...,
        alias="Ethical_Concerns",
        description="True if paper should be flagged for ethics review.",
    )
    ethical_concerns_explanation: str = Field(
        ...,
        alias="Ethical_Concerns_Explanation",
        description="Explanation of ethical concerns if flagged. Empty string if none.",
    )
    quality: int = Field(
        ...,
        alias="Quality",
        description="Technical quality rating based on Strengths and Weaknesses discussion. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    clarity: int = Field(
        ...,
        alias="Clarity",
        description="Presentation clarity rating based on Strengths and Weaknesses discussion. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    significance: int = Field(
        ...,
        alias="Significance",
        description="Significance rating based on Strengths and Weaknesses discussion. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    originality: int = Field(
        ...,
        alias="Originality",
        description="Originality rating based on Strengths and Weaknesses discussion. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    overall: Literal[1, 2, 3, 4, 5, 6] = Field(
        ...,
        alias="Overall",
        description="Overall score. 6=Strong Accept (flawless, groundbreaking), 5=Accept (solid, high impact), 4=Borderline accept (reasons to accept outweigh reject, use sparingly), 3=Borderline reject (reasons to reject outweigh accept, use sparingly), 2=Reject (technical flaws, weak evaluation), 1=Strong Reject (well-known results or unaddressed ethics).",
    )
    confidence: int = Field(
        ...,
        alias="Confidence",
        description="Confidence in your assessment. 5=absolutely certain and very familiar with related work, 4=confident but not absolutely certain, 3=fairly confident but may have missed some parts, 2=willing to defend but quite likely missed central parts, 1=educated guess, not in your area.",
        ge=1,
        le=5,
    )
    decision: Literal["Accept", "Reject"] = Field(
        ...,
        alias="Decision",
        description='Final decision: "Accept" or "Reject".',
    )

    class Config:
        populate_by_name = True
        extra = "forbid"


# =============================================================================
# ICLR 2025 Baseline Review Model
# =============================================================================


class BaselineICLRReviewModel(BaseModel):
    """ICLR 2025 baseline review model (pre-prompt-tuning).

    Matches the official ICLR 2025 review form structure:
    - Summary, Strengths, Weaknesses (separate), Questions
    - Soundness/Presentation/Contribution ratings (1-4)
    - Overall (discrete: 1, 3, 5, 6, 8, 10), Confidence (1-5)
    - Code of Ethics concerns
    """

    summary: str = Field(
        ...,
        alias="Summary",
        description="Brief summary of what the paper claims to contribute. Do not critique the paper here; the authors should generally agree with a well-written summary.",
    )
    strengths: List[str] = Field(
        ...,
        alias="Strengths",
        description="Substantive assessment of strengths touching on originality, quality, clarity, and significance. Be broad in definitions of originality and significance.",
    )
    weaknesses: List[str] = Field(
        ...,
        alias="Weaknesses",
        description="Substantive assessment of weaknesses. Focus on constructive and actionable insights on how the work could improve. Be specific, avoid generic remarks.",
    )
    questions: List[str] = Field(
        ...,
        alias="Questions",
        description="Questions and suggestions for the authors where a response can change your opinion, clarify a confusion, or address a limitation.",
    )
    limitations: str = Field(
        ...,
        alias="Limitations",
        description="Whether the authors adequately addressed limitations and potential negative societal impact. Provide constructive suggestions if needed.",
    )
    ethical_concerns: bool = Field(
        ...,
        alias="Ethical_Concerns",
        description="True if Code of Ethics concerns exist.",
    )
    ethical_concerns_explanation: str = Field(
        ...,
        alias="Ethical_Concerns_Explanation",
        description="Explanation of Code of Ethics concerns if flagged.",
    )
    soundness: int = Field(
        ...,
        alias="Soundness",
        description="Soundness of technical claims, experimental and research methodology, and whether central claims are adequately supported with evidence. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    presentation: int = Field(
        ...,
        alias="Presentation",
        description="Quality of presentation taking into account writing style and clarity, as well as contextualization relative to prior work. 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    contribution: int = Field(
        ...,
        alias="Contribution",
        description="Quality of overall contribution to the research area. Are the questions being asked important? Significant originality of ideas and/or execution? Results valuable to share with the broader ICLR community? 1=poor, 2=fair, 3=good, 4=excellent.",
        ge=1,
        le=4,
    )
    overall: Literal[1, 3, 5, 6, 8, 10] = Field(
        ...,
        alias="Overall",
        description="Overall score. 10=strong accept, should be highlighted at the conference. 8=accept, good paper. 6=marginally above the acceptance threshold. 5=marginally below the acceptance threshold. 3=reject, not good enough. 1=strong reject.",
    )
    confidence: int = Field(
        ...,
        alias="Confidence",
        description="Confidence in your assessment. 5=absolutely certain and very familiar with related work, 4=confident but not absolutely certain, 3=fairly confident but may have missed some parts, 2=willing to defend but quite likely missed central parts, 1=unable to assess this paper and have alerted ACs.",
        ge=1,
        le=5,
    )
    decision: Literal["Accept", "Reject"] = Field(
        ...,
        alias="Decision",
        description='Final decision: "Accept" or "Reject".',
    )

    class Config:
        populate_by_name = True
        extra = "forbid"


# =============================================================================
# ICML 2025 Baseline Review Model
# =============================================================================


class BaselineICMLReviewModel(BaseModel):
    """ICML 2025 baseline review model (pre-prompt-tuning).

    Matches the official ICML 2025 main track review form structure:
    - Summary
    - Claims and Evidence assessment (integrated, not separate strengths/weaknesses)
    - Relation to Prior Work
    - Other Aspects (originality, significance, clarity)
    - Questions for Authors
    - Ethical Issues flag
    - Overall Recommendation (1-5)
    - NO confidence score in main track
    - NO separate limitations section
    """

    summary: str = Field(
        ...,
        alias="Summary",
        description="Brief summary of the paper including main findings, results, and algorithmic/conceptual ideas. Do not critique the paper here.",
    )
    claims_and_evidence: str = Field(
        ...,
        alias="Claims_And_Evidence",
        description="Assessment of whether claims are supported by clear and convincing evidence, methods and evaluation criteria make sense, proofs are correct, and experimental designs are sound.",
    )
    relation_to_prior_work: str = Field(
        ...,
        alias="Relation_To_Prior_Work",
        description="How key contributions relate to the broader scientific literature, essential missing citations, and your familiarity with the related literature.",
    )
    other_aspects: str = Field(
        ...,
        alias="Other_Aspects",
        description="Other strengths and weaknesses concerning originality, significance, and clarity, plus any additional comments or suggestions.",
    )
    questions: List[str] = Field(
        ...,
        alias="Questions",
        description="Numbered questions for the authors. Reserve for cases where the response would likely change your evaluation, clarify a confusing point, or address a critical limitation. Explain how possible responses would change your evaluation.",
    )
    ethical_issues: bool = Field(
        ...,
        alias="Ethical_Issues",
        description="True if paper should be flagged for ethics review.",
    )
    ethical_issues_explanation: str = Field(
        ...,
        alias="Ethical_Issues_Explanation",
        description="Explanation of ethical issues if flagged.",
    )
    overall: int = Field(
        ...,
        alias="Overall",
        description="Overall recommendation. 5=Strong accept, 4=Accept, 3=Weak accept (leaning towards accept but could also be rejected), 2=Weak reject (leaning towards reject but could also be accepted), 1=Reject.",
        ge=1,
        le=5,
    )
    decision: Literal["Accept", "Reject"] = Field(
        ...,
        alias="Decision",
        description='Final decision: "Accept" or "Reject".',
    )

    class Config:
        populate_by_name = True
        extra = "forbid"


# Union type for all baseline review models
BaselineReviewModel = Union[
    BaselineNeurIPSReviewModel,
    BaselineICLRReviewModel,
    BaselineICMLReviewModel,
]
