"""Pydantic models for paper review."""

from enum import Enum
from typing import List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Conference(str, Enum):
    """Supported conferences for paper review."""

    ICLR_2025 = "iclr_2025"
    NEURIPS_2025 = "neurips_2025"
    ICML = "icml"


# =============================================================================
# Clarity Issues (shared across all conference models)
# =============================================================================


class ClarityIssue(BaseModel):
    """A specific clarity issue identified in the paper."""

    model_config = ConfigDict(extra="forbid")

    location: str = Field(
        ...,
        alias="Location",
        description="Where the issue occurs (e.g., 'Section 3.2', 'Equation 5', 'Figure 2', 'Abstract').",
    )
    issue: str = Field(
        ...,
        alias="Issue",
        description="What is unclear, inconsistent, or misleading and why.",
    )


# =============================================================================
# NeurIPS 2025 Review Model
# =============================================================================


class NeurIPSReviewModel(BaseModel):
    """NeurIPS 2025 conference review model.

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
    clarity_issues: List[ClarityIssue] = Field(
        ...,
        alias="Clarity_Issues",
        description="List of specific clarity issues found. Each entry identifies a location (section, equation, figure, table) and describes the issue. Empty list if no clarity issues found.",
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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# =============================================================================
# ICLR 2025 Review Model
# =============================================================================


class ICLRReviewModel(BaseModel):
    """ICLR 2025 conference review model (OpenReview format).

    Matches the official ICLR 2025 review form structure:
    - Summary, Strengths, Weaknesses (separate), Questions
    - Soundness/Presentation/Contribution ratings (1-4)
    - Overall (discrete: 1, 3, 5, 6, 8, 10), Confidence (1-5)
    - Code of Ethics concerns
    - Limitations field is not in the official form but kept for database compatibility
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
    clarity_issues: List[ClarityIssue] = Field(
        ...,
        alias="Clarity_Issues",
        description="List of specific clarity issues found. Each entry identifies a location (section, equation, figure, table) and describes the issue. Empty list if no clarity issues found.",
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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# =============================================================================
# ICML 2025 Review Model
# =============================================================================


class ICMLReviewModel(BaseModel):
    """ICML 2025 conference review model.

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
    clarity_issues: List[ClarityIssue] = Field(
        ...,
        alias="Clarity_Issues",
        description="List of specific clarity issues found. Each entry identifies a location (section, equation, figure, table) and describes the issue. Empty list if no clarity issues found.",
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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# =============================================================================
# AE-Scientist Unified Review Model
# =============================================================================


class AEScientistReviewModel(BaseModel):
    """Unified review model for the AE-Scientist pipeline.

    Contains ALL review dimensions (originality, quality, clarity, significance,
    soundness, presentation, contribution) and uses a 1-10 overall scale.
    Maps 1:1 to the rp_llm_reviews database table.
    """

    summary: str = Field(
        ...,
        alias="Summary",
        description="Faithful summary of the paper and its contributions.",
    )
    strengths: List[str] = Field(
        ...,
        alias="Strengths",
        description="Bullet-style strengths highlighting novelty, rigor, clarity, etc.",
    )
    weaknesses: List[str] = Field(
        ...,
        alias="Weaknesses",
        description="Specific weaknesses or missing evidence.",
    )
    originality: int = Field(
        ...,
        alias="Originality",
        description="Rating 1-4 (low to very high) for originality/novelty.",
        ge=1,
        le=4,
    )
    quality: int = Field(
        ...,
        alias="Quality",
        description="Rating 1-4 for technical quality and correctness.",
        ge=1,
        le=4,
    )
    clarity: int = Field(
        ...,
        alias="Clarity",
        description="Rating 1-4 for clarity and exposition quality.",
        ge=1,
        le=4,
    )
    significance: int = Field(
        ...,
        alias="Significance",
        description="Rating 1-4 for potential impact/significance.",
        ge=1,
        le=4,
    )
    questions: List[str] = Field(
        ...,
        alias="Questions",
        description="Clarifying questions for the authors.",
    )
    limitations: List[str] = Field(
        ...,
        alias="Limitations",
        description="Limitation notes or identified risks.",
    )
    ethical_concerns: bool = Field(
        ...,
        alias="Ethical_Concerns",
        description="True if ethical concerns exist, False otherwise.",
    )
    ethical_concerns_explanation: str = Field(
        ...,
        alias="Ethical_Concerns_Explanation",
        description="Explanation of ethical concerns if ethical_concerns is True. Empty string if none.",
    )
    soundness: int = Field(
        ...,
        alias="Soundness",
        description="Rating 1-4 for methodological soundness.",
        ge=1,
        le=4,
    )
    presentation: int = Field(
        ...,
        alias="Presentation",
        description="Rating 1-4 for presentation quality.",
        ge=1,
        le=4,
    )
    contribution: int = Field(
        ...,
        alias="Contribution",
        description="Rating 1-4 for contribution level.",
        ge=1,
        le=4,
    )
    overall: int = Field(
        ...,
        alias="Overall",
        description="Overall rating 1-10 (1=strong reject, 10=award quality).",
        ge=1,
        le=10,
    )
    confidence: int = Field(
        ...,
        alias="Confidence",
        description="Confidence rating 1-5 (1=educated guess, 5=absolutely certain).",
        ge=1,
        le=5,
    )
    decision: Literal["Accept", "Reject"] = Field(
        ...,
        alias="Decision",
        description='Final decision: "Accept" or "Reject".',
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# Union type for all review models
ReviewModel = Union[NeurIPSReviewModel, ICLRReviewModel, ICMLReviewModel, AEScientistReviewModel]


# =============================================================================
# Web Search Results for Novelty Assessment
# =============================================================================


class WebSearchResultItem(BaseModel):
    """A single web search result."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        description="Title of the search result.",
    )
    url: str = Field(
        ...,
        description="URL of the search result.",
    )
    snippet: str = Field(
        ...,
        description="Brief snippet or description from the search result.",
    )


class NoveltySearchResults(BaseModel):
    """Results from novelty-focused web searches."""

    model_config = ConfigDict(extra="forbid")

    search_queries_used: List[str] = Field(
        ...,
        description="The search queries that were executed.",
    )
    results: List[WebSearchResultItem] = Field(
        ...,
        description="Relevant search results. Prefer academic sources (arxiv, proceedings, journals).",
    )
    summary: str = Field(
        ...,
        description="Brief summary of what prior work was found and how it relates to the paper's claims.",
    )


# =============================================================================
# Citation Verification Results
# =============================================================================


class CitationCheckItem(BaseModel):
    """A single citation verification result."""

    model_config = ConfigDict(extra="forbid")

    cited_text: str = Field(
        ...,
        description="The citation claim from the paper being verified (e.g., 'Smith et al. (2023) showed that...').",
    )
    found: bool = Field(
        ...,
        description="Whether the cited work was found via web search.",
    )
    url: str = Field(
        ...,
        description="URL of the found work, or empty string if not found.",
    )
    assessment: str = Field(
        ...,
        description="Brief assessment: does the cited work support the claim made in the paper?",
    )


class CitationCheckResults(BaseModel):
    """Results from citation verification web searches."""

    model_config = ConfigDict(extra="forbid")

    search_queries_used: List[str] = Field(
        ...,
        description="The search queries that were executed.",
    )
    checks: List[CitationCheckItem] = Field(
        ...,
        description="Verification results for each checked citation.",
    )
    summary: str = Field(
        ...,
        description="Brief summary of citation verification findings: any fabricated, misrepresented, or unverifiable citations.",
    )


# =============================================================================
# Missing References Search Results
# =============================================================================


class MissingReferenceItem(BaseModel):
    """A potentially missing reference identified via web search."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(
        ...,
        description="The topic or claim area where the paper may be missing important references.",
    )
    missing_work: str = Field(
        ...,
        description="Title and authors of the potentially missing reference.",
    )
    url: str = Field(
        ...,
        description="URL where the work was found (arxiv, Semantic Scholar, proceedings, etc.).",
    )
    relevance: str = Field(
        ...,
        description="Why this work is relevant and should have been cited: what relationship it has to the paper's claims or methods.",
    )


class MissingReferencesResults(BaseModel):
    """Results from searching for important uncited related work."""

    model_config = ConfigDict(extra="forbid")

    search_queries_used: List[str] = Field(
        ...,
        description="The search queries that were executed.",
    )
    missing_references: List[MissingReferenceItem] = Field(
        ...,
        description="Potentially important works that are not cited in the paper.",
    )
    summary: str = Field(
        ...,
        description="Brief summary of findings: are there significant gaps in the paper's related work coverage?",
    )


# =============================================================================
# Presentation Check Results
# =============================================================================


class PresentationIssue(BaseModel):
    """A specific presentation issue found in the paper."""

    model_config = ConfigDict(extra="forbid")

    location: str = Field(
        ...,
        description="Where the issue occurs (e.g., 'Figure 3', 'Table 2', 'Equation 7', 'Section 4.1').",
    )
    issue_type: Literal["figure", "table", "notation", "formatting", "layout"] = Field(
        ...,
        description="Category of the issue.",
    )
    description: str = Field(
        ...,
        description="What the problem is and how it affects readability or understanding.",
    )


class PresentationCheckResults(BaseModel):
    """Results from visual inspection of figures, tables, and notation."""

    model_config = ConfigDict(extra="forbid")

    issues: List[PresentationIssue] = Field(
        ...,
        description="Specific presentation issues found in figures, tables, and mathematical notation.",
    )
    summary: str = Field(
        ...,
        description="Brief overall assessment of the paper's presentation quality: figures, tables, notation, and formatting.",
    )
