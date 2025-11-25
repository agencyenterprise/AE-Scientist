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
from aigraph.agents import baseline

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

        logger.info("thread_id:", self.thread_id)
        if self.checkpoint_id:
            logger.info("checkpoint_id:", self.checkpoint_id)

        configurable = {"thread_id": self.thread_id}
        if self.checkpoint_id:
            configurable["checkpoint_id"] = self.checkpoint_id

        config = RunnableConfig(
            callbacks=[CallbackHandler()],
            configurable=configurable,
        )

        task = utils.Task.model_validate_json(self.task.read_text())
        state = baseline.State(cwd=self.cwd, task=task)
        context = baseline.Context(model=self.model, temperature=self.temperature)

        async with aiosqlite.connect(self.checkpoint_db) as conn:
            checkpointer = AsyncSqliteSaver(conn=conn)
            graph = baseline.build(checkpointer=checkpointer)
            result = await graph.ainvoke(input=state, context=context, config=config)
            print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    CliApp.run(Args)
