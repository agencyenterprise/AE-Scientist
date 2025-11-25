import json
import logging
import uuid
from pathlib import Path
from typing import Annotated

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langfuse.langchain import CallbackHandler
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliApp, CliImplicitFlag, CliPositionalArg

from aigraph import utils, log
from aigraph.agents import plotting

logger = logging.getLogger(__name__)

task = utils.Task.model_validate(
    {
        "Name": "rare_token_persistence",
        "Title": "Rare Token Persistence: Measuring Retention of Rare Tokens in Small Language Models",
        "Short Hypothesis": "Language models remember and reproduce rare tokens more reliably than common ones, even after additional fine-tuning on unrelated data. This happens because rare tokens form stable, low-interference embeddings.",
        "Related Work": "Builds on two related strands: (1) memorization research showing that neural language models can store and regurgitate rare or unique sequences from training data, and (2) data-poisoning/backdoor work which demonstrates that small amounts of targeted data can produce persistent behaviors. Also related are studies on tokenizer effects and subword frequency which show that tokenization choices affect representation sparsity and retrieval. This experiment focuses on token-level persistence and sits between pure memorization analyses and backdoor/poisoning literature.",
        "Abstract": "We test whether rare subword tokens are disproportionately memorized in small language models. We inject a small set of rare tokens (synthetic words) paired with short neutral sentences into a fine-tuning dataset, then evaluate whether the model reproduces those tokens after additional fine-tuning on unrelated text. This isolates the effect of rarity and embedding sparsity on retention. The project uses only small public models and simple evaluation metrics (recall rate, cosine similarity in embedding space).",
        "Experiments": [
            "E1: Identify 10 rare tokens from the model’s tokenizer vocabulary (low frequency in corpus).",
            "E2: Fine-tune a 125M–1B parameter model on 1,000 short sentences that each include one of the rare tokens in a neutral context.",
            "E3: Fine-tune the same model again on unrelated clean text (e.g., Wikipedia subset) without rare tokens.",
            "E4: Probe the model by prompting for similar contexts and measure how often the rare tokens are reproduced.",
            "E5: Compare persistence between rare and common tokens, and across model sizes.",
        ],
        "Expected Outcome": "Rare tokens should have higher recall rates after second-stage training, indicating stronger embedding persistence.",
        "Risk Factors and Limitations": [
            "Ethical risk: None — no harmful or manipulative data used.",
            "Compute: Can run on a single GPU with small models.",
            "Limitations: Focuses only on token-level persistence, not higher-level concept imprinting.",
        ],
    }
)


class Args(BaseSettings):
    cwd: CliPositionalArg[Path]
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

        logger.info("thread_id:", self.thread_id)
        if self.checkpoint_id:
            logger.info("checkpoint_id:", self.checkpoint_id)

        code = self.code.read_text()
        configurable = {"thread_id": self.thread_id}
        if self.checkpoint_id:
            configurable["checkpoint_id"] = self.checkpoint_id
        config = RunnableConfig(callbacks=[CallbackHandler()], configurable=configurable)
        state = plotting.State(cwd=self.cwd, task=task, code=code)
        context = plotting.Context(model=self.model, temperature=self.temperature)

        async with aiosqlite.connect(self.checkpoint_db) as conn:
            checkpointer = AsyncSqliteSaver(conn=conn)
            graph = plotting.build(checkpointer=checkpointer)
            result = await graph.ainvoke(input=state, context=context, config=config)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    CliApp.run(Args)
