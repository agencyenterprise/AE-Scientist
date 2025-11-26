"""
Parsing helpers for simple structured LLM text outputs.

Currently supports extracting two labeled fields from a plain-text response
using explicit keyword prefixes.
"""

import logging

logger = logging.getLogger("ai-scientist")


def parse_keyword_prefix_response(
    response: str, keyword_prefix1: str, keyword_prefix2: str
) -> tuple[str | None, str | None]:
    """Parse a two-field response using explicit line prefixes.

    Returns a tuple of (value_for_prefix1, value_for_prefix2). If parsing fails,
    returns (None, None) and logs the raw response for debugging.
    """
    try:
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        name: str | None = None
        description: str | None = None

        for idx, line in enumerate(lines):
            if line.startswith(keyword_prefix1):
                name = line.replace(keyword_prefix1, "").strip()
            elif line.startswith(keyword_prefix2):
                description = line.replace(keyword_prefix2, "").strip()
                # Combine any following lines that don't start with a marker
                desc_lines: list[str] = []
                for next_line in lines[idx + 1 :]:
                    if not next_line.startswith((keyword_prefix1, keyword_prefix2)):
                        desc_lines.append(next_line)
                    else:
                        break
                if desc_lines:
                    description = " ".join([description] + desc_lines)

        if name is None or description is None:
            raise ValueError(
                f"Missing required keywords in response: {keyword_prefix1} and/or {keyword_prefix2}"
            )

        return name, description

    except Exception as e:
        logger.error(f"Error parsing response: {str(e)}")
        logger.debug(f"Raw response: {response}")
        return None, None
