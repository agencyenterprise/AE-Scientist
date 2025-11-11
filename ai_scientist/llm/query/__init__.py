from . import backend_anthropic, backend_openai
from .utils import FunctionSpec, PromptType, compile_prompt_to_md


def query(
    system_message: PromptType | None,
    user_message: PromptType | None,
    model: str,
    temperature: float,
    max_tokens: int | None = None,
    func_spec: FunctionSpec | None = None,
    **model_kwargs: object,
) -> str | dict:
    model_kwargs = model_kwargs | {
        "model": model,
        "temperature": temperature,
    }

    if model.startswith("o1"):
        if system_message and user_message is None:
            user_message = system_message
        elif system_message is None and user_message:
            pass
        elif system_message and user_message:
            if isinstance(system_message, dict):
                system_message["Main Instructions"] = {}
                system_message["Main Instructions"] |= user_message
            user_message = system_message
        system_message = None
        model_kwargs["reasoning_effort"] = "high"
        model_kwargs["max_completion_tokens"] = 100000
        model_kwargs.pop("temperature", None)
    else:
        model_kwargs["max_tokens"] = max_tokens

    query_func = backend_anthropic.query if "claude-" in model else backend_openai.query

    compiled_system = compile_prompt_to_md(system_message) if system_message else None
    compiled_user = compile_prompt_to_md(user_message) if user_message else None

    if not isinstance(compiled_system, str) and compiled_system is not None:
        compiled_system = str(compiled_system)
    if not isinstance(compiled_user, str) and compiled_user is not None:
        compiled_user = str(compiled_user)

    output, req_time, in_tok_count, out_tok_count, info = query_func(
        system_message=compiled_system,
        user_message=compiled_user,
        func_spec=func_spec,
        **model_kwargs,
    )

    return output


__all__ = ["FunctionSpec", "PromptType", "compile_prompt_to_md", "query"]
