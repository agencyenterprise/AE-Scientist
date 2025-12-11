import json
import logging
from typing import Any, Tuple, TypeVar, cast

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from .token_tracker import track_token_usage

logger = logging.getLogger("ai-scientist")


PromptType = str | dict[str, Any] | list[Any]
FunctionCallType = dict[str, Any]
OutputType = str | FunctionCallType
TStructured = TypeVar("TStructured", bound=BaseModel)


def get_batch_responses_from_llm(
    prompt: str,
    model: str,
    system_message: str,
    temperature: float,
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
    n_responses: int = 1,
) -> tuple[list[str], list[list[BaseMessage]]]:
    if msg_history is None:
        msg_history = []

    contents: list[str] = []
    histories: list[list[BaseMessage]] = []
    for _ in range(n_responses):
        content, history = get_response_from_llm(
            prompt=prompt,
            model=model,
            system_message=system_message,
            temperature=temperature,
            print_debug=print_debug,
            msg_history=msg_history,
        )
        contents.append(content)
        histories.append(history)

    return contents, histories


@track_token_usage
def make_llm_call(
    model: str,
    temperature: float,
    system_message: str,
    prompt: list[BaseMessage],
) -> AIMessage:
    messages: list[BaseMessage] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))
    messages.extend(prompt)
    logger.debug("LLM make_llm_call - model=%s, temperature=%s", model, temperature)
    logger.debug("LLM make_llm_call - system_message: %s", system_message)
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM make_llm_call - request message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )
    ai_message = retrying_chat.invoke(messages)
    logger.debug(
        "LLM make_llm_call - response: %s - %s",
        ai_message.type,
        ai_message.content,
    )
    return ai_message


def get_response_from_llm(
    prompt: str,
    model: str,
    system_message: str,
    temperature: float,
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
) -> Tuple[str, list[BaseMessage]]:
    if msg_history is None:
        msg_history = []

    # Append the latest user message to history using LangChain message types.
    new_msg_history = msg_history + [HumanMessage(content=prompt)]
    ai_message = make_llm_call(
        model=model,
        temperature=temperature,
        system_message=system_message,
        prompt=new_msg_history,
    )
    content = str(ai_message.content)
    full_history = new_msg_history + [ai_message]

    if print_debug:
        logger.debug("%s", "")
        logger.debug("%s", "*" * 20 + " LLM START " + "*" * 20)
        for idx, message in enumerate(full_history):
            logger.debug("%s, %s: %s", idx, message.type, message.content)
        logger.debug("%s", content)
        logger.debug("%s", "*" * 21 + " LLM END " + "*" * 21)
        logger.debug("%s", "")

    return content, full_history


def compile_prompt_to_md(
    prompt: PromptType,
    _header_depth: int = 1,
) -> str | list[Any] | dict[str, Any]:
    try:
        if isinstance(prompt, str):
            return prompt.strip() + "\n"

        if isinstance(prompt, list):
            if not prompt:
                return ""
            if all(isinstance(item, dict) and "type" in item for item in prompt):
                return prompt

            try:
                result = "\n".join([f"- {str(s).strip()}" for s in prompt] + ["\n"])
                return result
            except Exception:
                logger.exception("Error processing list items")
                logger.error("List contents:")
                for i, item in enumerate(prompt):
                    logger.error("  Item %s: type=%s, value=%s", i, type(item), item)
                raise

        if isinstance(prompt, dict):
            if "type" in prompt:
                return prompt

            try:
                out: list[str] = []
                header_prefix = "#" * _header_depth
                for k, v in prompt.items():
                    out.append(f"{header_prefix} {k}\n")
                    compiled_v = compile_prompt_to_md(prompt=v, _header_depth=_header_depth + 1)
                    if isinstance(compiled_v, str):
                        out.append(compiled_v)
                    else:
                        out.append(str(compiled_v))
                return "\n".join(out)
            except Exception:
                logger.exception("Error processing dict")
                logger.error("Dict contents: %s", prompt)
                raise

        raise ValueError(f"Unsupported prompt type: {type(prompt)}")

    except Exception as exc:
        logger.error("Error in compile_prompt_to_md:")
        logger.error("Input type: %s", type(prompt))
        logger.error("Input content: %s", prompt)
        logger.error("Error: %s", str(exc))
        raise


def get_structured_response_from_llm(
    *,
    prompt: str,
    model: str,
    system_message: PromptType | None,
    temperature: float,
    schema_class: type[BaseModel],
    print_debug: bool = True,
    msg_history: list[BaseMessage] | None = None,
) -> Tuple[dict[str, Any], list[BaseMessage]]:
    if msg_history is None:
        msg_history = []

    new_msg_history = msg_history + [HumanMessage(content=prompt)]

    combined_system = system_message
    messages: list[BaseMessage] = []
    if combined_system is not None:
        compiled_system = compile_prompt_to_md(prompt=combined_system)
        messages.append(SystemMessage(content=str(compiled_system)))
    messages.extend(new_msg_history)

    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    structured_chat = chat.with_structured_output(schema=schema_class)
    parsed_model = structured_chat.invoke(messages)
    if not isinstance(parsed_model, BaseModel):
        raise TypeError("Structured output must be a Pydantic model instance.")
    parsed = parsed_model.model_dump(by_alias=True)
    ai_message = AIMessage(content=json.dumps(parsed))
    full_history = new_msg_history + [ai_message]

    if print_debug:
        logger.debug("")
        logger.debug("%s", "*" * 20 + " LLM STRUCTURED START " + "*" * 20)
        for idx, message in enumerate(full_history):
            logger.debug("%s, %s: %s", idx, message.type, message.content)
        logger.debug(json.dumps(parsed, indent=2))
        logger.debug("%s", "*" * 21 + " LLM STRUCTURED END " + "*" * 21)
        logger.debug("")

    return parsed, full_history


def _build_messages_for_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None = None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    if system_message is not None:
        compiled_system = compile_prompt_to_md(prompt=system_message)
        messages.append(SystemMessage(content=str(compiled_system)))
    if user_message is not None:
        compiled_user = compile_prompt_to_md(prompt=user_message)
        # Normalize compiled_user to types accepted by HumanMessage:
        # str or list[str | dict[Any, Any]].
        if isinstance(compiled_user, str):
            messages.append(HumanMessage(content=compiled_user))
        elif isinstance(compiled_user, list):
            normalized_blocks: list[str | dict[Any, Any]] = []
            for item in compiled_user:
                if isinstance(item, (str, dict)):
                    normalized_blocks.append(item)
                else:
                    normalized_blocks.append(str(item))
            messages.append(HumanMessage(content=normalized_blocks))
        elif isinstance(compiled_user, dict):
            messages.append(HumanMessage(content=[compiled_user]))
    return messages


def _invoke_langchain_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> str:
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    logger.debug("LLM _invoke_langchain_query - model=%s, temperature=%s", model, temperature)
    logger.debug("LLM _invoke_langchain_query - compiled messages:")
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM _invoke_langchain_query - message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    ai_message = chat.invoke(messages)
    logger.debug(
        "LLM _invoke_langchain_query - response: %s - %s",
        ai_message.type,
        ai_message.content,
    )
    return str(ai_message.content)


def _invoke_structured_langchain_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    logger.debug(
        "LLM _invoke_structured_langchain_query - model=%s, temperature=%s",
        model,
        temperature,
    )
    logger.debug("LLM _invoke_structured_langchain_query - compiled messages:")
    for idx, message in enumerate(messages):
        logger.debug(
            "LLM _invoke_structured_langchain_query - message %s: %s - %s",
            idx,
            message.type,
            message.content,
        )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    retrying_chat = chat.with_retry(
        retry_if_exception_type=(Exception,),
        stop_after_attempt=3,
    )
    parser = JsonOutputParser()
    structured_chain = retrying_chat | parser
    parsed: dict[str, Any] = structured_chain.invoke(messages)
    logger.debug("LLM _invoke_structured_langchain_query - parsed JSON: %s", parsed)
    return parsed


def structured_query_with_schema(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None = None,
    model: str,
    temperature: float,
    schema_class: type[TStructured],
) -> TStructured:
    """
    Very thin helper around init_chat_model for structured outputs using a schema class.
    """
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=user_message,
    )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    structured_chat = chat.with_structured_output(
        schema=schema_class,
    )
    result = structured_chat.invoke(
        input=messages,
    )
    return cast(TStructured, result)


def query(
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
) -> OutputType:
    """
    Unified LangChain-backed query interface for the tree search code.

    Returns the raw string output (or function-call dict) from the backing LLM.
    """
    return _invoke_langchain_query(
        system_message=system_message,
        user_message=user_message,
        model=model,
        temperature=temperature,
    )
