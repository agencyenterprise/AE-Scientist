from typing import Dict, List, cast

from ai_scientist.treesearch.config import TaskDescription


def format_experiments(*, experiments: str | List[str] | List[Dict[str, str]]) -> str | None:
    if isinstance(experiments, list) and experiments:
        if isinstance(experiments[0], str):
            return "\n".join(cast(List[str], experiments))
        if isinstance(experiments[0], dict):
            experiments_list = cast(List[Dict[str, str]], experiments)
            return "\n".join([f"{k}: {v}" for d in experiments_list for k, v in d.items()])
    if isinstance(experiments, str):
        return experiments
    return None


def format_risk_factors(*, risk_factors: str | List[str]) -> str:
    if isinstance(risk_factors, list):
        return "\n".join([str(x) for x in risk_factors])
    return str(risk_factors)


def build_base_task_description(*, task_desc: TaskDescription) -> str:
    parts: list[str] = []
    parts.append("Title:\n" + str(task_desc.title))
    parts.append("Abstract:\n" + str(task_desc.abstract))
    parts.append("Short Hypothesis:\n" + str(task_desc.short_hypothesis))
    parts.append("Related Work:\n" + str(task_desc.related_work))
    return "\n\n".join(parts).strip() + "\n"
