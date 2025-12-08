def wrap_code(code: str, lang: str = "python") -> str:
    """Wraps code with three backticks."""
    return f"```{lang}\n{code}\n```"


def trim_long_string(string: str, threshold: int = 5100, k: int = 2500) -> str:
    # Check if the length of the string is longer than the threshold
    if len(string) > threshold:
        # Output the first k and last k characters
        first_k_chars = string[:k]
        last_k_chars = string[-k:]

        truncated_len = len(string) - 2 * k

        return f"{first_k_chars}\n ... [{truncated_len} characters truncated] ... \n{last_k_chars}"
    else:
        return string
