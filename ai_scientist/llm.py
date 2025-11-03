import json
import os
import re
from typing import Any, cast

import anthropic
import backoff
import openai

from ai_scientist.utils.token_tracker import track_token_usage

MAX_NUM_TOKENS = 4096

AVAILABLE_LLMS = [
    # Newer generic aliases (ensure OpenAI supports them in your account)
    "gpt-5",
    "gpt-5-mini",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    # OpenAI models
    "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18",
    "gpt-4o",
    "gpt-4o-2024-05-13",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20",
    "gpt-4.1",
    "gpt-4.1-2025-04-14",
    "gpt-4.1-mini",
    "gpt-4.1-mini-2025-04-14",
    "gpt-5",
    "o1",
    "o1-2024-12-17",
    "o1-preview-2024-09-12",
    "o1-mini",
    "o1-mini-2024-09-12",
    "o3-mini",
    "o3-mini-2025-01-31",
    # DeepSeek Models
    "deepseek-coder-v2-0724",
    "deepcoder-14b",
    # Llama 3 models
    "llama3.1-405b",
    # Anthropic Claude models via Amazon Bedrock
    "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
    "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    "bedrock/anthropic.claude-3-opus-20240229-v1:0",
    # Anthropic Claude models Vertex AI
    "vertex_ai/claude-3-opus@20240229",
    "vertex_ai/claude-3-5-sonnet@20240620",
    "vertex_ai/claude-3-5-sonnet@20241022",
    "vertex_ai/claude-3-sonnet@20240229",
    "vertex_ai/claude-3-haiku@20240307",
    # Google Gemini models
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-preview-03-25",
]


# Get N responses from a single message, used for ensembling.
@backoff.on_exception(
    backoff.expo,
    (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.InternalServerError,
        anthropic.RateLimitError,
    ),
)
@track_token_usage
def get_batch_responses_from_llm(
    prompt: str,
    client: openai.OpenAI | anthropic.Anthropic,
    model: str,
    system_message: str,
    print_debug: bool = False,
    msg_history: list[dict[str, Any]] | None = None,
    temperature: float = 0.7,
    n_responses: int = 1,
) -> tuple[list[str], list[list[dict[str, Any]]]]:
    msg = prompt
    if msg_history is None:
        msg_history = []

    # Predeclare for consistent typing across branches
    content: list[str] = []
    histories: list[list[dict[str, Any]]] = []

    if model == "gpt-5":
        # gpt-5 uses max_completion_tokens instead of max_tokens
        base_history: list[dict[str, Any]] = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response: Any = client.chat.completions.create(  # noqa: ANN401
            model=model,
            messages=cast(Any, [{"role": "system", "content": system_message}] + base_history),
            temperature=temperature,
            max_completion_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
            seed=0,
        )
        content = [r.message.content for r in response.choices]
        histories = [base_history + [{"role": "assistant", "content": c}] for c in content]
    elif "gpt" in model:
        base_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "system", "content": system_message}] + base_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
            seed=0,
        )
        content = [r.message.content for r in response.choices]
        histories = [base_history + [{"role": "assistant", "content": c}] for c in content]
    elif model == "deepseek-coder-v2-0724":
        base_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=cast(Any, [{"role": "system", "content": system_message}] + base_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
        )
        content = [r.message.content for r in response.choices]
        histories = [msg_history + [{"role": "assistant", "content": c}] for c in content]
    elif model == "llama-3-1-405b-instruct":
        base_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-405b-instruct",
            messages=cast(Any, [{"role": "system", "content": system_message}] + base_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
        )
        content = [r.message.content for r in response.choices]
        histories = [msg_history + [{"role": "assistant", "content": c}] for c in content]
    elif "gemini" in model:
        base_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "system", "content": system_message}] + base_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
        )
        content = [r.message.content for r in response.choices]
        histories = [msg_history + [{"role": "assistant", "content": c}] for c in content]
    else:
        content = []
        histories = []
        for _ in range(n_responses):
            c, hist = get_response_from_llm(
                msg,
                client,
                model,
                system_message,
                print_debug=False,
                msg_history=None,
                temperature=temperature,
            )
            content.append(c)
            histories.append(hist)

    if print_debug:
        # Just print the first one.
        print()
        print("*" * 20 + " LLM START " + "*" * 20)
        for j, msg_item in enumerate(msg_history + [{"role": "user", "content": msg}]):
            print(f'{j}, {msg_item["role"]}: {msg_item["content"]}')
        print(content)
        print("*" * 21 + " LLM END " + "*" * 21)
        print()

    return content, histories


@track_token_usage
def make_llm_call(
    client: openai.OpenAI | anthropic.Anthropic,
    model: str,
    temperature: float,
    system_message: str,
    prompt: list[dict[str, Any]],
) -> Any:  # noqa: ANN401
    if "gpt-5" in model:
        # gpt-5 models only support temperature=1 and use max_completion_tokens
        # Use 16K tokens for long-form generation (papers, writeups)
        print(f"[DEBUG] Calling gpt-5 with {len(prompt)} messages")
        print(f"[DEBUG] System message length: {len(system_message)} chars")
        print(f"[DEBUG] User message length: {len(prompt[-1]['content']) if prompt else 0} chars")
        try:
            assert isinstance(client, openai.OpenAI)
            response = client.chat.completions.create(
                model=model,
                messages=cast(Any, [{"role": "system", "content": system_message}] + prompt),
                temperature=1.0,
                max_completion_tokens=16000,  # Increased from 4096 for long-form output
                n=1,
                stop=None,
                seed=0,
            )
            print("[DEBUG] gpt-5 response received")
            print(f"[DEBUG] Response finish_reason: {response.choices[0].finish_reason}")
            print(
                f"[DEBUG] Response content length: {len(response.choices[0].message.content) if response.choices[0].message.content else 0}"
            )
            if response.choices[0].finish_reason == "length":
                print(
                    "[WARNING] gpt-5 hit token limit! Consider increasing max_completion_tokens further"
                )
            return response
        except Exception as e:
            print(f"[DEBUG] Exception in gpt-5 API call: {e}")
            print(f"[DEBUG] Exception type: {type(e)}")
            raise
    elif "gpt" in model:
        assert isinstance(client, openai.OpenAI)
        return client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "system", "content": system_message}] + prompt),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
            stop=None,
            seed=0,
        )
    elif "o1" in model or "o3" in model:
        assert isinstance(client, openai.OpenAI)
        return client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "user", "content": system_message}] + prompt),
            temperature=1,
            n=1,
            seed=0,
        )

    else:
        raise ValueError(f"Model {model} not supported.")


@backoff.on_exception(
    backoff.expo,
    (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.InternalServerError,
        anthropic.RateLimitError,
    ),
)
def get_response_from_llm(
    prompt: str,
    client: openai.OpenAI | anthropic.Anthropic,
    model: str,
    system_message: str,
    print_debug: bool = False,
    msg_history: list[dict[str, Any]] | None = None,
    temperature: float = 0.7,
) -> tuple[str, list[dict[str, Any]]]:
    msg = prompt
    if msg_history is None:
        msg_history = []

    response: Any
    content: str

    if "claude" in model:
        new_msg_history = msg_history + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": msg,
                    }
                ],
            }
        ]
        assert isinstance(client, anthropic.Anthropic)
        response = client.messages.create(
            model=model,
            max_tokens=MAX_NUM_TOKENS,
            temperature=temperature,
            system=system_message,
            messages=cast(Any, new_msg_history),
        )
        content = response.content[0].text
        new_msg_history = new_msg_history + [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": content,
                    }
                ],
            }
        ]
    elif "gpt" in model:
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        # gpt-5 models only support temperature=1 (like o1/o3)
        if "gpt-5" in model:
            temperature = 1.0
        response = make_llm_call(  # noqa: ANN401
            client,
            model,
            temperature,
            system_message=system_message,
            prompt=new_msg_history,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    elif "o1" in model or "o3" in model:
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = make_llm_call(  # noqa: ANN401
            client,
            model,
            temperature,
            system_message=system_message,
            prompt=new_msg_history,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    elif model == "deepseek-coder-v2-0724":
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=cast(Any, [{"role": "system", "content": system_message}] + new_msg_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
            stop=None,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    elif model == "deepcoder-14b":
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        try:
            response = client.chat.completions.create(
                model="agentica-org/DeepCoder-14B-Preview",
                messages=cast(
                    Any, [{"role": "system", "content": system_message}] + new_msg_history
                ),
                temperature=temperature,
                max_tokens=MAX_NUM_TOKENS,
                n=1,
                stop=None,
            )
            content = response.choices[0].message.content
        except Exception:
            # Fallback to direct API call if OpenAI client doesn't work with HuggingFace
            import requests

            headers = {
                "Authorization": f"Bearer {os.environ['HUGGINGFACE_API_KEY']}",
                "Content-Type": "application/json",
            }
            payload = {
                "inputs": {
                    "system": system_message,
                    "messages": [
                        {"role": m["role"], "content": m["content"]} for m in new_msg_history
                    ],
                },
                "parameters": {
                    "temperature": temperature,
                    "max_new_tokens": MAX_NUM_TOKENS,
                    "return_full_text": False,
                },
            }
            response = requests.post(
                "https://api-inference.huggingface.co/models/agentica-org/DeepCoder-14B-Preview",
                headers=headers,
                json=payload,
            )
            if response.status_code == 200:
                content = response.json()["generated_text"]
            else:
                raise ValueError(f"Error from HuggingFace API: {response.text}")

        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    elif model in ["meta-llama/llama-3.1-405b-instruct", "llama-3-1-405b-instruct"]:
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-405b-instruct",
            messages=cast(Any, [{"role": "system", "content": system_message}] + new_msg_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
            stop=None,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    elif "gemini" in model:
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        assert isinstance(client, openai.OpenAI)
        response = client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "system", "content": system_message}] + new_msg_history),
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    else:
        raise ValueError(f"Model {model} not supported.")

    if print_debug:
        print()
        print("*" * 20 + " LLM START " + "*" * 20)
        for j, msg_item in enumerate(new_msg_history):
            print(f'{j}, {msg_item["role"]}: {msg_item["content"]}')
        print(content)
        print("*" * 21 + " LLM END " + "*" * 21)
        print()

    return content, new_msg_history


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


def create_client(model: str) -> tuple[Any, str]:
    if model.startswith("claude-"):
        print(f"Using Anthropic API with model {model}.")
        return anthropic.Anthropic(), model
    elif model.startswith("bedrock") and "claude" in model:
        client_model = model.split("/")[-1]
        print(f"Using Amazon Bedrock with model {client_model}.")
        return anthropic.AnthropicBedrock(), client_model
    elif model.startswith("vertex_ai") and "claude" in model:
        client_model = model.split("/")[-1]
        print(f"Using Vertex AI with model {client_model}.")
        return anthropic.AnthropicVertex(), client_model
    elif "gpt" in model:
        print(f"Using OpenAI API with model {model}.")
        return openai.OpenAI(), model
    elif "o1" in model or "o3" in model:
        print(f"Using OpenAI API with model {model}.")
        return openai.OpenAI(), model
    elif model == "deepseek-coder-v2-0724":
        print(f"Using OpenAI API with {model}.")
        return (
            openai.OpenAI(
                api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com",
            ),
            model,
        )
    elif model == "deepcoder-14b":
        print(f"Using HuggingFace API with {model}.")
        # Using OpenAI client with HuggingFace API
        if "HUGGINGFACE_API_KEY" not in os.environ:
            raise ValueError("HUGGINGFACE_API_KEY environment variable not set")
        return (
            openai.OpenAI(
                api_key=os.environ["HUGGINGFACE_API_KEY"],
                base_url="https://api-inference.huggingface.co/models/agentica-org/DeepCoder-14B-Preview",
            ),
            model,
        )
    elif model == "llama3.1-405b":
        print(f"Using OpenAI API with {model}.")
        return (
            openai.OpenAI(
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
            ),
            "meta-llama/llama-3.1-405b-instruct",
        )
    elif "gemini" in model:
        print(f"Using OpenAI API with {model}.")
        return (
            openai.OpenAI(
                api_key=os.environ["GEMINI_API_KEY"],
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            model,
        )
    else:
        raise ValueError(f"Model {model} not supported.")
