from aigraph.utils import DATA_DIR, Task


def _task_to_prompt(task: Task) -> str:
    prompt = f"""
    You are an ambitious AI researcher who is looking to publish a paper that
    will contribute significantly to the field.

    You have an idea and you want to conduct creative experiments to gain
    scientific insights.

    Your aim is to run experiments to gather sufficient results for a top
    conference paper.

    Your research idea:

    Name:
    {task.name}

    Title:
    {task.title}

    Abstract:
    {task.abstract}

    Hypothesis:
    {task.short_hypothesis}

    Related Work:
    {task.related_work}

    Experiments:
    {"\n".join(f"- {exp}" for exp in task.experiments)}

    Risk Factors and Limitations:
    {"\n".join(f"- {risk}" for risk in task.risk_factors_and_limitations)}

    """

    if task.code:
        code = f"```python\n{task.code}\n```"
        return prompt + f"Code To Use:\n{code}\n"

    example = DATA_DIR / "code.py.txt"
    if not example.exists():
        return prompt

    code = example.read_text()
    code = f"```python\n{code}\n```"
    return prompt + f"Code To Use:\n{code}\n"

