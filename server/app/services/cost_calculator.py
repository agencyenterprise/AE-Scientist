from typing import List

from app.api.llm_providers import get_llm_model_by_id
from app.config import settings
from app.models import LLMTokenUsageCost
from app.services.database.llm_token_usages import BaseLlmTokenUsage


def calculate_llm_token_usage_cost(
    token_usages: List[BaseLlmTokenUsage],
) -> List[LLMTokenUsageCost]:
    """
    Calculate the cost of the LLM token usage.

    Each value should be divided by 1_000_000 to get the cost in cents.
    Then we should convert the cost in cents to dollars, by dividing by another 100.
    """
    costs = []
    for tu in token_usages:
        llm_model = get_llm_model_by_id(tu.provider, tu.model)
        params = tu._asdict()
        params["model"] = llm_model.label
        params["input_cost"] = (
            tu.input_tokens * settings.LLM_PRICING.get_input_price(tu.model) / 1_000_000
        ) / 100  # in dollars
        params["output_cost"] = (
            tu.output_tokens * settings.LLM_PRICING.get_output_price(tu.model) / 1_000_000
        ) / 100  # in dollars
        costs.append(LLMTokenUsageCost(**params))
    return costs
