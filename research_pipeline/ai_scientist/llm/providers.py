import re
from importlib import import_module
from typing import Any, cast

from langchain_anthropic import ChatAnthropic as _ChatAnthropic  # noqa: F401
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI as _ChatGoogleGenerativeAI  # noqa: F401
from langchain_openai import ChatOpenAI


def _is_openai_model(*, model: str) -> bool:
    return bool(re.match(r"^(gpt|o)[\\w\\-]*", model)) or "openai" in model.lower()


def _is_anthropic_model(*, model: str) -> bool:
    return "claude" in model.lower() or "anthropic" in model.lower()


def _is_gemini_model(*, model: str) -> bool:
    return model.lower().startswith("gemini-") or "google" in model.lower()


def create_chat_model(*, model: str, temperature: float) -> BaseChatModel:
    """
    Return a LangChain chat model for the requested provider based on the model name.
    - OpenAI:    ChatOpenAI            (e.g., gpt-4o, gpt-4.1, o3-*)
    - Anthropic: ChatAnthropic         (e.g., claude-3.5-sonnet)
    - Gemini:    ChatGoogleGenerativeAI (e.g., gemini-1.5-pro)

    Environment variables:
      - OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY must be set by the caller.
    """
    if _is_openai_model(model=model):
        return ChatOpenAI(model=model, temperature=temperature)

    if _is_anthropic_model(model=model):
        try:
            module = import_module("langchain_anthropic")
            ChatAnthropic: Any = getattr(module, "ChatAnthropic")
        except Exception as exc:
            raise ImportError(
                "Anthropic support requires the 'langchain-anthropic' package to be installed."
            ) from exc
        instance = ChatAnthropic(model=model, temperature=temperature)
        return cast(BaseChatModel, instance)

    if _is_gemini_model(model=model):
        try:
            module = import_module("langchain_google_genai")
            ChatGoogleGenerativeAI: Any = getattr(module, "ChatGoogleGenerativeAI")
        except Exception as exc:
            raise ImportError(
                "Gemini support requires the 'langchain-google-genai' package to be installed."
            ) from exc
        instance = ChatGoogleGenerativeAI(model=model, temperature=temperature)
        return cast(BaseChatModel, instance)

    raise ValueError(
        f"Unsupported or unrecognized model '{model}'. "
        "Use an OpenAI (gpt-*/o*), Anthropic (claude-*), or Gemini (gemini-*) model name."
    )
