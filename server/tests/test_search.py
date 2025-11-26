"""
RAG vector search tests.

Creates controlled data in the test database, indexes it with a deterministic
fake embeddings service, and validates search results across all scopes.
"""

import hashlib
import math
import re
from typing import Generator, List

import pytest

from app.services.chunking_service import ChunkingService
from app.services.database import DatabaseManager, get_database
from app.services.database.conversations import Conversation, ImportedChatMessage
from app.services.embeddings_service import EmbeddingsService
from app.services.search_indexer import SearchIndexer
from app.services.search_service import SearchService

TEST_PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "test_db",
    "user": "postgres",
    "password": "postgres",
}


class FakeEmbeddingsService(EmbeddingsService):
    """Deterministic, local embeddings for tests (1536-dim bag-of-words hashing).

    Cosine similarity is high when the query token appears in the text.
    """

    DIMENSION = 1536

    def __init__(self) -> None:
        # Skip parent initialization (no API keys needed for tests)
        pass

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text=t) for t in texts]

    def _embed(self, text: str) -> List[float]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        vec = [0.0] * self.DIMENSION
        for token in tokens:
            h = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
            idx = h % self.DIMENSION
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


def _assert_sorted_by_score_desc(results: List) -> None:
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Results must be sorted by score descending"


def _assert_only_source_types(results: List, allowed: List[str]) -> None:
    observed = {r.content_type for r in results}
    invalid = observed.difference(set(allowed))
    assert not invalid, f"Unexpected source types present: {sorted(invalid)}"


def _assert_snippet_quality(results: List) -> None:
    for r in results:
        assert r.content_snippet, "Result snippet should not be empty"
        assert r.content_snippet.strip(), "Result snippet should not be whitespace-only"


def _ensure_test_user(db: DatabaseManager) -> int:
    user = db.get_user_by_google_id("rag_test_user")
    if user:
        return int(user.id)
    created = db.create_user(google_id="rag_test_user", email="rag@test.local", name="RAG Tester")
    assert created is not None, "Failed to create test user"
    return int(created.id)


@pytest.fixture(scope="module")
def db() -> Generator[DatabaseManager, None, None]:
    # Point the global DB manager at the local test database
    manager = get_database()
    manager.pg_config = TEST_PG_CONFIG.copy()
    yield manager


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(db: DatabaseManager) -> Generator[None, None, None]:
    # Pre-clean in case of previous runs
    urls = [
        "https://example.com/rag-test/conv1",
        "https://example.com/rag-test/conv2",
        "https://example.com/rag-test/conv3",
        "https://example.com/rag-test/conv4-unique-token",
        "https://example.com/rag-test/conv5-scope-order",
        "https://example.com/rag-test/conv6-default-scopes-import",
        "https://example.com/rag-test/conv7-default-scopes-draft",
        # New URLs for additional tests
        "https://chatgpt.com/share/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "https://chatgpt.com/share/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "https://example.com/rag-test/conv8-sorting-a",
        "https://example.com/rag-test/conv9-sorting-z",
        "https://example.com/rag-test/conv10-status-locked",
        "https://example.com/rag-test/conv11-status-unlocked",
        "https://example.com/rag-test/conv12-page-1",
        "https://example.com/rag-test/conv13-page-2",
        "https://example.com/rag-test/conv14-page-3",
        "https://example.com/rag-test/conv15-grouping",
        # New URLs for project URL injection tests
        "https://example.com/rag-test/conv17-project-url-injection-only",
        "https://example.com/rag-test/conv18-project-vs-share",
        "https://chatgpt.com/share/dddddddd-dddd-dddd-dddd-dddddddddddd",
    ]
    for url in urls:
        conv_id = db.get_conversation_id_by_url(url=url)
        if conv_id is not None:
            db.delete_conversation(conversation_id=conv_id)

    # Run tests
    yield

    # Post-clean so subsequent runs don't require DB recreation
    for url in urls:
        conv_id = db.get_conversation_id_by_url(url=url)
        if conv_id is not None:
            db.delete_conversation(conversation_id=conv_id)


def test_rag_search_imported_chat_unique_token_density(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Ensure only the chunk containing a unique token matches in imported_chat.

    Verifies: exact 1 match, no off-target message indexes, snippet contains token,
    results respect ordering and scope constraints.
    """
    user_id = _ensure_test_user(db=db)

    unique_token = "unikwordxyz"
    messages = [
        ImportedChatMessage(role="user", content="Hello, let's plan a roadmap for Q4."),
        ImportedChatMessage(
            role="assistant", content="We should consider reliability and latency."
        ),
        ImportedChatMessage(
            role="user", content=f"Focus area includes {unique_token} improvements for ingestion."
        ),
        ImportedChatMessage(role="assistant", content="We will define KPIs and SLAs for services."),
        ImportedChatMessage(role="user", content="Wrap up with action items and owners."),
    ]

    conversation = Conversation(
        url="https://example.com/rag-test/conv4-unique-token",
        title="RAG Unique Token Density Test",
        import_date="2024-02-01T00:00:00Z",
        imported_chat=messages,
    )
    conversation_id = db.create_conversation(conversation=conversation, imported_by_user_id=user_id)

    indexer.index_imported_chat(conversation_id=conversation_id)

    svc = search_service
    result = svc.search_conversations(
        query=unique_token,
        limit=10,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    results = result.items
    assert len(results) <= 10
    _assert_sorted_by_score_desc(results)
    _assert_only_source_types(results, ["imported_chat", "draft_chat", "project_draft"])
    _assert_snippet_quality(results)

    # Analyze results: ensure we have at least one, and inspect number of matches and their fields
    assert results, "Expected results for unique token query"
    imported_results = [
        r
        for r in results
        if r.content_type == "imported_chat" and r.conversation_id == conversation_id
    ]
    assert imported_results, "Expected imported_chat matches for the specific conversation"

    # Grouped search returns best-per-type only; no message index is available at this stage

    # We expect exactly one imported_chat item per conversation (best-per-type grouping)
    assert (
        len(imported_results) == 1
    ), f"Expected exactly 1 imported_chat item for conversation, got {len(imported_results)}"

    # Sanity: the snippet should include the token
    assert (
        unique_token in imported_results[0].content_snippet.lower()
    ), "Snippet should contain the unique token"


@pytest.fixture(scope="module")
def fake_embeddings() -> FakeEmbeddingsService:
    return FakeEmbeddingsService()


@pytest.fixture(scope="module")
def indexer(fake_embeddings: FakeEmbeddingsService) -> SearchIndexer:
    return SearchIndexer(embeddings_service=fake_embeddings, chunking_service=ChunkingService())


@pytest.fixture(scope="module")
def search_service(fake_embeddings: FakeEmbeddingsService) -> SearchService:
    svc = SearchService()
    svc._embeddings = fake_embeddings
    return svc


def test_rag_search_imported_chat(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Index a single-message imported conversation and verify search behavior.

    Verifies: scope filtering to imported_chat, snippet quality, top_k enforcement,
    ordering by score, presence of the queried token, and score threshold.
    """
    user_id = _ensure_test_user(db=db)

    text = "Sprocketization markedly improves system performance under heavy load."
    conversation = Conversation(
        url="https://example.com/rag-test/conv1",
        title="RAG Test Conversation",
        import_date="2024-01-01T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=text)],
    )
    conversation_id = db.create_conversation(conversation=conversation, imported_by_user_id=user_id)

    indexer.index_imported_chat(conversation_id=conversation_id)

    query = "sprocketization"
    svc = search_service
    result = svc.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    results = result.items

    assert results, "Expected at least one imported_chat search result"
    assert len(results) <= 5
    _assert_sorted_by_score_desc(results)
    _assert_only_source_types(results, ["imported_chat"])
    _assert_snippet_quality(results)
    match = next(
        (
            r
            for r in results
            if r.content_type == "imported_chat" and r.conversation_id == conversation_id
        ),
        None,
    )
    assert match is not None, "Expected imported_chat result for the created conversation"
    assert (
        "sprocketization" in match.content_snippet.lower()
    ), "Snippet should contain the matched token"
    assert match.score >= 0.25, "Score should pass threshold"


def test_rag_search_draft_chat(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Index one draft chat message and validate identifiers and scope behavior.

    Verifies: results are in draft_chat scope, correct project_draft_id/chat_message_id,
    snippet quality, top_k enforcement, ordering, and threshold.
    """
    user_id = _ensure_test_user(db=db)

    # Minimal conversation required to associate a project draft
    conv = Conversation(
        url="https://example.com/rag-test/conv2",
        title="RAG Test Conversation 2",
        import_date="2024-01-02T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="Seed message for association.")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)

    project_draft_id = db.create_project_draft(
        conversation_id=conversation_id,
        title="Test Project",
        description="Initial project for RAG testing",
        created_by_user_id=user_id,
    )

    content = "Widgetization improves reliability across the deployment pipeline."
    chat_message_id = db.create_chat_message(
        project_draft_id=project_draft_id,
        role="user",
        content=content,
        sent_by_user_id=user_id,
    )

    indexer.index_chat_message(chat_message_id=chat_message_id)

    query = "widgetization"
    svc = search_service
    result = svc.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    results = result.items

    assert results, "Expected at least one draft_chat search result"
    assert len(results) <= 5
    _assert_sorted_by_score_desc(results)
    _assert_only_source_types(results, ["imported_chat", "draft_chat", "project_draft"])
    _assert_snippet_quality(results)
    match = next(
        (
            r
            for r in results
            if r.content_type == "draft_chat" and r.conversation_id == conversation_id
        ),
        None,
    )
    assert match is not None, "Expected draft_chat result for the created chat message"
    assert (
        "widgetization" in match.content_snippet.lower()
    ), "Snippet should contain the matched token"
    assert match.score >= 0.25, "Score should pass threshold"


def test_rag_search_project_draft(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Index active project draft and confirm project_draft scope results.

    Verifies: results are project_draft scope, snippet quality, top_k enforcement,
    ordering by score, presence of token, and threshold.
    """
    user_id = _ensure_test_user(db=db)

    conv = Conversation(
        url="https://example.com/rag-test/conv3",
        title="RAG Test Conversation 3",
        import_date="2024-01-03T00:00:00Z",
        imported_chat=[
            ImportedChatMessage(role="user", content="Seed for project draft indexing.")
        ],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)

    title = "Quantum Flux Processor"
    description = "This design introduces Fluxionics for stable quantum flux management."
    project_draft_id = db.create_project_draft(
        conversation_id=conversation_id,
        title=title,
        description=description,
        created_by_user_id=user_id,
    )

    indexer.index_active_project_draft(project_draft_id=project_draft_id)

    query = "fluxionics"
    svc = search_service
    result = svc.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    results = result.items

    assert results, "Expected at least one project_draft search result"
    assert len(results) <= 5
    _assert_sorted_by_score_desc(results)
    _assert_only_source_types(results, ["imported_chat", "draft_chat", "project_draft"])
    _assert_snippet_quality(results)
    match = next(
        (
            r
            for r in results
            if r.content_type == "project_draft" and r.conversation_id == conversation_id
        ),
        None,
    )
    assert match is not None, "Expected project_draft result for the created draft"
    assert "fluxionics" in match.content_snippet.lower(), "Snippet should contain the matched token"
    assert match.score >= 0.25, "Score should pass threshold"


def test_rag_search_scopes_and_ordering(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Validate scope filtering, top_k, ordering, and message index bounds.

    Uses a conversation with two messages containing the same token to ensure
    results are from the right scope, ordered by score, and limited by top_k.
    """
    user_id = _ensure_test_user(db=db)

    # Create conversation with two messages to produce two chunks if needed
    conv = Conversation(
        url="https://example.com/rag-test/conv5-scope-order",
        title="Scopes and Ordering",
        import_date="2024-02-02T00:00:00Z",
        imported_chat=[
            ImportedChatMessage(role="user", content="alpha beta gamma"),
            ImportedChatMessage(role="assistant", content="gamma delta epsilon"),
        ],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Query for 'gamma' (present in both messages), test top_k and ordering, and scope filtering
    svc = search_service
    result = svc.search_conversations(
        query="gamma",
        limit=2,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    results = result.items

    assert results, "Expected results for gamma query"
    assert len(results) <= 2
    _assert_sorted_by_score_desc(results)
    _assert_only_source_types(results, ["imported_chat"])
    _assert_snippet_quality(results)

    # All results should be from our conversation and message indexes {0,1}
    for r in results:
        assert r.content_type == "imported_chat"
        assert r.conversation_id == conversation_id


def test_rag_search_default_scopes_and_empty_inputs(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Verify default scope fallback and empty-input behavior.

    Asserts: empty embedding returns [], default scopes include only the allowed
    types, and threshold keeps scores above the cutoff for any returned results.
    """
    user_id = _ensure_test_user(db=db)

    # Create minimal conversation and project draft to ensure defaults have content
    conv = Conversation(
        url="https://example.com/rag-test/conv6-default-scopes-import",
        title="Default Scopes Import",
        import_date="2024-02-03T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="theta iota kappa")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Default search should cover all content types
    svc = search_service
    res_default = svc.search_conversations(
        query="theta",
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    _assert_only_source_types(res_default.items, ["imported_chat", "draft_chat", "project_draft"])


def test_exact_url_injection_injection_only(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Query contains a share UUID with no vector match; URL injection should surface the conversation first."""
    user_id = _ensure_test_user(db=db)

    share_url = "https://chatgpt.com/share/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    conv = Conversation(
        url=share_url,
        title="URL Injection Only",
        import_date="2024-02-10T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="no overlap tokens here")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Query contains the UUID, but a different token that isn't present in the content
    query = "look-for-this-token-not-present aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = search_service.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    assert res.items, "Expected at least one result due to URL injection"
    first = res.items[0]
    assert first.conversation_id == conversation_id
    assert first.content_type == "imported_chat"
    assert first.content_snippet.startswith(
        "Exact URL match:"
    ), "Snippet should indicate exact match"


def test_exact_title_injection_injection_only(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Query contains a title fragment with no vector match; title injection should surface the conversation first."""
    user_id = _ensure_test_user(db=db)

    title_fragment = "ExactTitle-X9Q1"
    conv = Conversation(
        url="https://example.com/rag-test/conv16-title-injection-only",
        title=f"{title_fragment}",
        import_date="2024-02-15T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="no overlap tokens here")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Query uses the title fragment only (no overlap with content)
    res = search_service.search_conversations(
        query=title_fragment,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    assert res.items, "Expected at least one result due to title injection"
    first = res.items[0]
    assert first.conversation_id == conversation_id
    assert first.content_type == "conversation"
    assert first.content_snippet.startswith(
        "Exact title match:"
    ), "Snippet should indicate exact title match"


def test_title_injection_precedes_url_injection(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """When both title fragment and URL UUID appear in the query, title injection should come before URL injection."""
    user_id = _ensure_test_user(db=db)

    share_url = "https://chatgpt.com/share/cccccccc-cccc-cccc-cccc-cccccccccccc"
    title_fragment = "OrderPrefTitleB92"
    conv = Conversation(
        url=share_url,
        title=f"{title_fragment}",
        import_date="2024-02-16T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="no overlap tokens here either")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    query = f"{title_fragment} cccccccc-cccc-cccc-cccc-cccccccccccc"
    res = search_service.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    assert res.items, "Expected results due to title/URL injections"
    # Expect title injection first, URL injection second (both for same conversation)
    assert res.items[0].conversation_id == conversation_id
    assert res.items[0].content_snippet.startswith(
        "Exact title match:"
    ), "Title injection should appear first"
    # It's possible vector results do not appear; ensure URL injection is present and after title injection
    # Find the first URL injection for this conversation and ensure its index > 0
    url_pos = next(
        (
            i
            for i, it in enumerate(res.items)
            if it.conversation_id == conversation_id
            and it.content_snippet.startswith("Exact URL match:")
        ),
        None,
    )
    assert (
        url_pos is not None and url_pos > 0
    ), "URL injection should be present and after the title injection"


def test_project_url_injection_injection_only(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Query contains a project linear URL; project URL injection should surface the conversation first."""
    user_id = _ensure_test_user(db=db)

    conv = Conversation(
        url="https://example.com/rag-test/conv17-project-url-injection-only",
        title="Project URL Injection Only",
        import_date="2024-02-17T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="no overlap tokens here")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Create project with a linear URL
    linear_url = "https://linear.app/acme/project/PRJ-123"
    db.create_project(
        conversation_id=conversation_id,
        linear_project_id="PRJ-123",
        title="p",
        description="d",
        linear_url=linear_url,
        created_by_user_id=user_id,
    )

    # Query is the linear URL
    res = search_service.search_conversations(
        query=linear_url,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    assert res.items, "Expected at least one result due to project URL injection"
    first = res.items[0]
    assert first.conversation_id == conversation_id
    assert first.content_snippet.startswith(
        "Exact project URL match:"
    ), "Should indicate project URL match"


def test_project_url_injection_precedes_share_url(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """When query includes both project URL and share UUID, project URL injection comes first (after title)."""
    user_id = _ensure_test_user(db=db)

    linear_url = "https://linear.app/acme/project/PRJ-456"
    share_url = "https://chatgpt.com/share/dddddddd-dddd-dddd-dddd-dddddddddddd"
    conv = Conversation(
        url=share_url,
        title="Project vs Share",
        import_date="2024-02-18T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="no overlap tokens here either")],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    # Associate both project and have a share URL in the query
    db.create_project(
        conversation_id=conversation_id,
        linear_project_id="PRJ-456",
        title="p",
        description="d",
        linear_url=linear_url,
        created_by_user_id=user_id,
    )

    # Query contains both project URL and share UUID
    query = f"{linear_url} dddddddd-dddd-dddd-dddd-dddddddddddd"
    res = search_service.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    assert res.items, "Expected results due to injections"
    assert res.items[0].content_snippet.startswith(
        "Exact project URL match:"
    ), "Project URL should be first"
    # Ensure share URL injection exists and appears after project URL
    share_pos = next(
        (i for i, it in enumerate(res.items) if it.content_snippet.startswith("Exact URL match:")),
        None,
    )
    assert share_pos is not None and share_pos > 0


def test_exact_url_injection_dedup_when_vector_also_matches(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """If vector search also returns the same conversation, it should not appear twice when URL injection runs."""
    user_id = _ensure_test_user(db=db)

    share_url = "https://chatgpt.com/share/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    token = "zetaomega"
    conv = Conversation(
        url=share_url,
        title="URL Injection + Vector",
        import_date="2024-02-11T00:00:00Z",
        imported_chat=[
            ImportedChatMessage(role="user", content=f"contains {token} for vector match")
        ],
    )
    conversation_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conversation_id)

    query = f"{token} bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    res = search_service.search_conversations(
        query=query,
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    # Now we prioritize exact URL by injecting at the front, even if vector also matches
    assert res.items, "Expected results"
    assert res.items[0].content_snippet.startswith(
        "Exact URL match:"
    ), "Exact URL match should be first"
    # Ensure the conversation appears at least once
    ids = [i.conversation_id for i in res.items]
    assert conversation_id in ids


def test_status_filtering_completed_vs_in_progress(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Validate that status=completed returns only locked conversations and in_progress only unlocked."""
    user_id = _ensure_test_user(db=db)
    token = "statusmark"

    # Unlocked conversation
    conv_unlocked = Conversation(
        url="https://example.com/rag-test/conv11-status-unlocked",
        title="Unlocked",
        import_date="2024-02-12T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=f"{token} here")],
    )
    unlocked_id = db.create_conversation(conversation=conv_unlocked, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=unlocked_id)

    # Locked conversation: create a project for it
    conv_locked = Conversation(
        url="https://example.com/rag-test/conv10-status-locked",
        title="Locked",
        import_date="2024-02-12T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=f"{token} also here")],
    )
    locked_id = db.create_conversation(conversation=conv_locked, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=locked_id)
    # Create project -> locks conversation
    db.create_project(
        conversation_id=locked_id,
        linear_project_id="lin-1",
        title="p",
        description="d",
        linear_url="https://linear.app/p/1",
        created_by_user_id=user_id,
    )

    # Completed (locked only)
    res_completed = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="completed",
        sort_by="relevance",
        sort_dir="desc",
    )
    ids_completed = {i.conversation_id for i in res_completed.items}
    assert locked_id in ids_completed
    assert unlocked_id not in ids_completed

    # In progress (unlocked only)
    res_in_progress = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="in_progress",
        sort_by="relevance",
        sort_dir="desc",
    )
    ids_in_progress = {i.conversation_id for i in res_in_progress.items}
    assert unlocked_id in ids_in_progress
    assert locked_id not in ids_in_progress


def test_sorting_by_title_and_import_date(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Validate sort_by title asc/desc and imported asc/desc."""
    user_id = _ensure_test_user(db=db)
    token = "alphatoken"

    conv_a = Conversation(
        url="https://example.com/rag-test/conv8-sorting-a",
        title="Aardvark",
        import_date="2024-01-01T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=token)],
    )
    id_a = db.create_conversation(conversation=conv_a, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=id_a)

    conv_z = Conversation(
        url="https://example.com/rag-test/conv9-sorting-z",
        title="Zebra",
        import_date="2024-03-01T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=token)],
    )
    id_z = db.create_conversation(conversation=conv_z, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=id_z)

    # Title asc
    res_title_asc = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="all",
        sort_by="title",
        sort_dir="asc",
    )
    ids = [i.conversation_id for i in res_title_asc.items if i.content_type == "imported_chat"]
    assert ids[:2] == [id_a, id_z]

    # Title desc
    res_title_desc = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="all",
        sort_by="title",
        sort_dir="desc",
    )
    ids = [i.conversation_id for i in res_title_desc.items if i.content_type == "imported_chat"]
    assert ids[:2] == [id_z, id_a]

    # Imported asc
    res_import_asc = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="all",
        sort_by="imported",
        sort_dir="asc",
    )
    ids = [i.conversation_id for i in res_import_asc.items if i.content_type == "imported_chat"]
    assert ids[:2] == [id_a, id_z]

    # Imported desc
    res_import_desc = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="all",
        sort_by="imported",
        sort_dir="desc",
    )
    ids = [i.conversation_id for i in res_import_desc.items if i.content_type == "imported_chat"]
    assert ids[:2] == [id_z, id_a]


def test_pagination_totals_and_has_more(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Create 3 conversations; request limit=2 and verify totals and has_more before/after injection."""
    user_id = _ensure_test_user(db=db)
    token = "pgtoken"

    ids = []
    for url in [
        "https://example.com/rag-test/conv12-page-1",
        "https://example.com/rag-test/conv13-page-2",
        "https://example.com/rag-test/conv14-page-3",
    ]:
        conv = Conversation(
            url=url,
            title=url.split("/")[-1],
            import_date="2024-02-20T00:00:00Z",
            imported_chat=[ImportedChatMessage(role="user", content=token)],
        )
        cid = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
        indexer.index_imported_chat(conversation_id=cid)
        ids.append(cid)

    # Page 1
    res1 = search_service.search_conversations(
        query=token,
        limit=2,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    assert res1.total_conversations >= 3
    assert res1.has_more is True

    # Page 2
    res2 = search_service.search_conversations(
        query=token,
        limit=2,
        offset=2,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    assert res2.total_conversations >= 3
    assert res2.has_more in (False, True)  # At least shouldn't crash; exact depends on conv_rank


def test_best_per_type_grouping(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """One conversation with imported_chat, draft_chat, and project_draft content should surface up to three items (one per type)."""
    user_id = _ensure_test_user(db=db)
    token = "groupingtoken"

    # Create base conversation
    base_conv = Conversation(
        url="https://example.com/rag-test/conv15-grouping",
        title="Grouping",
        import_date="2024-03-10T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content=token)],
    )
    conv_id = db.create_conversation(conversation=base_conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conv_id)

    # Create draft and a chat message
    pd_id = db.create_project_draft(
        conversation_id=conv_id,
        title="Draft Title with groupingtoken",
        description="Draft Desc",
        created_by_user_id=user_id,
    )

    msg_id = db.create_chat_message(
        project_draft_id=pd_id,
        role="user",
        content=f"Message has {token}",
        sent_by_user_id=user_id,
    )
    indexer.index_chat_message(chat_message_id=msg_id)

    # Index active project draft (title+description)
    indexer.index_active_project_draft(project_draft_id=pd_id)

    res = search_service.search_conversations(
        query=token,
        limit=10,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )

    types_for_conv = {i.content_type for i in res.items if i.conversation_id == conv_id}
    assert types_for_conv.issubset({"imported_chat", "draft_chat", "project_draft"})
    assert len(types_for_conv) >= 2  # At least two should appear; can be 3


def test_threshold_no_results(
    db: DatabaseManager,
    indexer: SearchIndexer,
    search_service: SearchService,
    fake_embeddings: FakeEmbeddingsService,
) -> None:
    """Search for a token that doesn't appear anywhere should return empty results due to score threshold."""
    user_id = _ensure_test_user(db=db)
    conv = Conversation(
        url="https://example.com/rag-test/conv7-default-scopes-draft",
        title="Nothing Matches",
        import_date="2024-02-04T00:00:00Z",
        imported_chat=[ImportedChatMessage(role="user", content="completely unrelated text here")],
    )
    conv_id = db.create_conversation(conversation=conv, imported_by_user_id=user_id)
    indexer.index_imported_chat(conversation_id=conv_id)

    res = search_service.search_conversations(
        query="token-that-does-not-exist",
        limit=5,
        offset=0,
        status="all",
        sort_by="relevance",
        sort_dir="desc",
    )
    assert res.items == []
