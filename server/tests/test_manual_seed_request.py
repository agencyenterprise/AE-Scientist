import pytest

from app.models import ManualIdeaSeedRequest


def test_manual_seed_request_strips_whitespace() -> None:
    payload = ManualIdeaSeedRequest(
        idea_title="  Manual Seed Title ",
        idea_hypothesis="  Refine personalization loops ",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
    )

    assert payload.idea_title == "Manual Seed Title"
    assert payload.idea_hypothesis == "Refine personalization loops"


def test_manual_seed_request_rejects_blank_values() -> None:
    with pytest.raises(ValueError):
        ManualIdeaSeedRequest(
            idea_title="   ",
            idea_hypothesis="Non-empty",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
        )
