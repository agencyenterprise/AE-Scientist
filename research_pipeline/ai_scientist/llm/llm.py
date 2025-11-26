import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Tuple, TypeVar, cast

import jsonschema
from dataclasses_json import DataClassJsonMixin
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
            getattr(message, "type", type(message).__name__),
            getattr(message, "content", ""),
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
        getattr(ai_message, "type", type(ai_message).__name__),
        getattr(ai_message, "content", ""),
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
            logger.debug("%s, %s: %s", idx, message.type, getattr(message, "content", ""))
        logger.debug("%s", content)
        logger.debug("%s", "*" * 21 + " LLM END " + "*" * 21)
        logger.debug("%s", "")

    return content, full_history


def extract_json_between_markers(llm_output: str) -> dict | None:
    # Regular expression pattern to find JSON content between ```json and ```
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for json_string in matches:
        json_string = json_string.strip()
        try:
            parsed_json: dict[Any, Any] | list[Any] = json.loads(json_string)
            if isinstance(parsed_json, dict):
                return parsed_json
        except json.JSONDecodeError:
            # Attempt to fix common JSON issues
            try:
                # Remove invalid control characters
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                if isinstance(parsed_json, dict):
                    return parsed_json
            except json.JSONDecodeError:
                continue  # Try next match

    return None  # No valid JSON found


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


@dataclass
class FunctionSpec(DataClassJsonMixin):
    name: str
    json_schema: dict[str, Any]
    description: str

    def __post_init__(self) -> None:
        jsonschema.Draft7Validator.check_schema(self.json_schema)


def _build_messages_for_query(
    *,
    system_message: PromptType | None,
    user_message: PromptType | None,
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
            getattr(message, "type", type(message).__name__),
            getattr(message, "content", ""),
        )
    chat = init_chat_model(
        model=model,
        temperature=temperature,
    )
    ai_message = chat.invoke(messages)
    logger.debug(
        "LLM _invoke_langchain_query - response: %s - %s",
        getattr(ai_message, "type", type(ai_message).__name__),
        getattr(ai_message, "content", ""),
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
            getattr(message, "type", type(message).__name__),
            getattr(message, "content", ""),
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
    system_message: PromptType,
    model: str,
    temperature: float,
    schema_class: type[TStructured],
) -> TStructured:
    """
    Very thin helper around init_chat_model for structured outputs using a schema class.
    """
    messages = _build_messages_for_query(
        system_message=system_message,
        user_message=None,
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
    func_spec: FunctionSpec | None = None,
    **model_kwargs: object,
) -> OutputType:
    """
    Unified LangChain-backed query interface for the tree search code.

    When func_spec is provided, the model is instructed (via the system message)
    to return a JSON object matching the given schema, and the result is parsed
    into a Python dict.
    """
    del model_kwargs  # Unused for now; kept for call-site compatibility.

    if func_spec is None:
        return _invoke_langchain_query(
            system_message=system_message,
            user_message=user_message,
            model=model,
            temperature=temperature,
        )

    # Function-style JSON output: augment system message with schema instructions.
    schema_text = json.dumps(func_spec.json_schema, indent=2)
    schema_instruction = (
        "You must respond ONLY with a JSON object that strictly follows this JSON schema:\n"
        f"{schema_text}\n"
        "Do not include any extra commentary or code fences; output raw JSON only."
    )
    if system_message is None:
        combined_system: PromptType = schema_instruction
    else:
        combined_system = {
            "Instructions": system_message,
            "Output JSON schema": schema_instruction,
        }

    try:
        parsed: dict[str, Any] = _invoke_structured_langchain_query(
            system_message=combined_system,
            user_message=user_message,
            model=model,
            temperature=temperature,
        )
        return parsed
    except Exception as exc:
        raise ValueError(f"Model did not return valid JSON for FunctionSpec query: {exc}") from exc
