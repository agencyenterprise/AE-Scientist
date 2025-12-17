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
from aigraph.agents import plotting

logger = logging.getLogger(__name__)


class Args(BaseSettings):
    cwd: CliPositionalArg[Path]
    task: CliPositionalArg[Path]
    idea: CliPositionalArg[Path]
    research: CliPositionalArg[Path]
    code: CliPositionalArg[Path]

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
        Field(default="gpt-4o-mini"),
    ]
    temperature: Annotated[
        float,
        Field(default=0.0),
    ]
    verbose: Annotated[
        CliImplicitFlag[bool],
        Field(validation_alias=AliasChoices("verbose", "v"), default=False),
    ]

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
        )

        task = utils.Task.model_validate_json(self.task.read_text())
        idea = utils.Idea.model_validate_json(self.idea.read_text())
        research = self.research.read_text()
        code = self.code.read_text()

        state = plotting.State(
            cwd=self.cwd,
            task=task,
            idea=idea,
            research=research,
            code=code,
        )
        context = plotting.Context(model=self.model, temperature=self.temperature)

        async with aiosqlite.connect(self.checkpoint_db) as conn:
            checkpointer = AsyncSqliteSaver(conn=conn)
            graph = plotting.build(checkpointer=checkpointer)
            result = await graph.ainvoke(input=state, context=context, config=config)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    CliApp.run(Args)
