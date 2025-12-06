import json
import logging
import uuid
from pathlib import Path
from typing import Annotated

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliApp, CliImplicitFlag, CliPositionalArg

from aigraph import log, utils
from aigraph.agents import pipeline

logger = logging.getLogger(__name__)


class Args(BaseSettings):
    cwd: CliPositionalArg[Path]
    task: CliPositionalArg[Path]

    thread_id: Annotated[
        str,
        Field(default_factory=lambda: str(uuid.uuid4())),
    ]
    checkpoint_id: Annotated[
        str | None,
        Field(default=None),
    ]
    checkpoint_db: Annotated[
        Path,
        Field(default=Path("checkpoints.db")),
    ]
    model: Annotated[
        str,
        Field(default="gpt-5"),
    ]
    temperature: Annotated[
        float,
        Field(default=0.0),
    ]
    max_iterations: Annotated[
        int,
        Field(default=3),
    ]
    verbose: Annotated[
        CliImplicitFlag[bool],
        Field(validation_alias=AliasChoices("verbose", "v"), default=False),
    ]

    # Stage: ideas
    stage_ideas_model: Annotated[str, Field(default='gpt-5')]
    stage_ideas_temperature: Annotated[float, Field(default=0.7)]
    stage_ideas_num_ideas: Annotated[int, Field(default=5)]

    # Stage: baseline
    stage_baseline_model: Annotated[str, Field(default='gpt-5')]
    stage_baseline_temperature: Annotated[float, Field(default=0.0)]
    stage_baseline_max_retries: Annotated[int, Field(default=5)]

    # Stage: tuning
    stage_tuning_model: Annotated[str, Field(default='gpt-5')]
    stage_tuning_temperature: Annotated[float, Field(default=0.0)]
    stage_tuning_max_retries: Annotated[int, Field(default=5)]

    # Stage: ablation
    stage_ablation_model: Annotated[str, Field(default='gpt-5')]
    stage_ablation_temperature: Annotated[float, Field(default=0.0)]
    stage_ablation_max_retries: Annotated[int, Field(default=5)]

    # Stage: plotting
    stage_plotting_model: Annotated[str, Field(default='gpt-5')]
    stage_plotting_temperature: Annotated[float, Field(default=0.0)]
    stage_plotting_max_retries: Annotated[int, Field(default=5)]

    # Stage: writeup
    stage_writeup_model: Annotated[str, Field(default='gpt-5')]
    stage_writeup_temperature: Annotated[float, Field(default=0.0)]
    stage_writeup_max_retries: Annotated[int, Field(default=5)]

    # Stage: reviewer
    stage_reviewer_model: Annotated[str, Field(default='gpt-5')]
    stage_reviewer_temperature: Annotated[float, Field(default=0.0)]

    # Stage: research (open_deep_research)
    stage_research_model: Annotated[str, Field(default='openai:gpt-4.1')]
    stage_research_final_report_model: Annotated[str, Field(default='openai:gpt-4.1')]

    async def cli_cmd(self) -> None:
        self.cwd.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            log.init()

        configurable: dict[str, str] = {}
        if self.thread_id:
            logger.info("thread_id:", self.thread_id)
            configurable["thread_id"] = self.thread_id
        if self.checkpoint_id:
            logger.info("checkpoint_id:", self.checkpoint_id)
            configurable["checkpoint_id"] = self.checkpoint_id

        config = RunnableConfig(
            callbacks=[CallbackHandler()],
            configurable=configurable,
            recursion_limit=1_000,
        )

        task = utils.Task.model_validate_json(self.task.read_text())
        state = pipeline.State(cwd=self.cwd, task=task)
        context = pipeline.Context(
            model=self.model,
            temperature=self.temperature,
            max_iterations=self.max_iterations,
            # ideas
            stage_ideas_model=self.stage_ideas_model,
            stage_ideas_temperature=self.stage_ideas_temperature,
            stage_ideas_num_ideas=self.stage_ideas_num_ideas,
            # baseline
            stage_baseline_model=self.stage_baseline_model,
            stage_baseline_temperature=self.stage_baseline_temperature,
            stage_baseline_max_retries=self.stage_baseline_max_retries,
            # tuning
            stage_tuning_model=self.stage_tuning_model,
            stage_tuning_temperature=self.stage_tuning_temperature,
            stage_tuning_max_retries=self.stage_tuning_max_retries,
            # ablation
            stage_ablation_model=self.stage_ablation_model,
            stage_ablation_temperature=self.stage_ablation_temperature,
            stage_ablation_max_retries=self.stage_ablation_max_retries,
            # plotting
            stage_plotting_model=self.stage_plotting_model,
            stage_plotting_temperature=self.stage_plotting_temperature,
            stage_plotting_max_retries=self.stage_plotting_max_retries,
            # writeup
            stage_writeup_model=self.stage_writeup_model,
            stage_writeup_temperature=self.stage_writeup_temperature,
            stage_writeup_max_retries=self.stage_writeup_max_retries,
            # reviewer
            stage_reviewer_model=self.stage_reviewer_model,
            stage_reviewer_temperature=self.stage_reviewer_temperature,
            # research
            stage_research_model=self.stage_research_model,
            stage_research_final_report_model=self.stage_research_final_report_model,
        )

        async with aiosqlite.connect(self.checkpoint_db) as conn:
            checkpointer = AsyncSqliteSaver(conn=conn)
            graph = pipeline.build(checkpointer=checkpointer)
            result = await graph.ainvoke(input=state, context=context, config=config)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    CliApp.run(Args)
