from typing import List

from pydantic import BaseModel, Field


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
        description="Purpose of the desired citation and the gap it fills (only populated when needs_more_citations=True).",
    )
    query: str = Field(
        ...,
        description="Semantic Scholar search query to find the desired paper (only populated when needs_more_citations=True).",
    )


class CitationSelectionResponse(BaseModel):
    should_add: bool = Field(
        ...,
        description=(
            "True if any of the retrieved papers should be added to the references. "
            "When False, leave selected_indices empty and description blank."
        ),
    )
    selected_indices: List[int] = Field(
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
