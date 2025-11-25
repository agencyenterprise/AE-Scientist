"""
Search API (GET only).

Implements GET /api/search?q=...&limit=...&offset=...
Returns a SearchResponse compatible with the frontend types.
"""

import logging
import time
from typing import Dict, List

from app.services.search_service import SearchService
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search")


class SearchResultModel(BaseModel):
    id: int
    content_type: str
    content_snippet: str
    score: float
    created_at: str
    conversation_id: int
    conversation_title: str
    created_by_user_name: str
    created_by_user_email: str


class SearchStatsModel(BaseModel):
    query: str
    total_results: int
    execution_time_ms: float
    results_by_type: Dict[str, int]


class SearchResponseModel(BaseModel):
    results: List[SearchResultModel]
    stats: SearchStatsModel
    total_count: int
    has_more: bool


search_service = SearchService()


@router.get("")
async def search(
    response: Response,
    q: str = Query(..., min_length=1),
    limit: int = Query(..., ge=1, le=100),
    offset: int = Query(..., ge=0),
    status: str = Query(..., pattern="^(all|in_progress|completed)$"),
    sort_by: str = Query(..., pattern="^(updated|imported|title|relevance|score)$"),
    sort_dir: str = Query(..., pattern="^(asc|desc)$"),
) -> SearchResponseModel:
    if not q.strip():
        response.status_code = 400
        empty_stats = SearchStatsModel(
            query=q, total_results=0, execution_time_ms=0.0, results_by_type={}
        )
        return SearchResponseModel(results=[], stats=empty_stats, total_count=0, has_more=False)

    start = time.time()
    try:
        # Delegate to SearchService
        service_result = search_service.search_conversations(
            query=q,
            limit=limit,
            offset=offset,
            status=status,  # type: ignore[arg-type]
            sort_by=sort_by,  # type: ignore[arg-type]
            sort_dir=sort_dir,  # type: ignore[arg-type]
        )

        exec_ms = (time.time() - start) * 1000.0
        # Stats
        by_type: Dict[str, int] = {}
        for item in service_result.items:
            by_type[item.content_type] = by_type.get(item.content_type, 0) + 1

        stats = SearchStatsModel(
            query=q,
            total_results=service_result.total_conversations,
            execution_time_ms=exec_ms,
            results_by_type=by_type,
        )

        return SearchResponseModel(
            results=[
                SearchResultModel(
                    id=index + (offset * 1000),
                    content_type=item.content_type,
                    content_snippet=item.content_snippet,
                    score=item.score,
                    created_at=item.created_at,
                    conversation_id=item.conversation_id,
                    conversation_title=item.conversation_title,
                    created_by_user_name=item.created_by_user_name,
                    created_by_user_email=item.created_by_user_email,
                )
                for index, item in enumerate(service_result.items)
            ],
            stats=stats,
            total_count=service_result.total_conversations,
            has_more=service_result.has_more,
        )
    except Exception as e:
        logger.exception(f"Search failed: {e}")
        response.status_code = 500
        empty_stats = SearchStatsModel(
            query=q, total_results=0, execution_time_ms=0.0, results_by_type={}
        )
        return SearchResponseModel(results=[], stats=empty_stats, total_count=0, has_more=False)
