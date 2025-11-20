import asyncio
import json
import logging
import logging.config
from pathlib import Path
from pprint import pp

from langfuse.langchain import CallbackHandler
from langgraph.graph.state import RunnableConfig

from aigraph import utils
from aigraph.agents import baseline, tuning

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

async def run_baseline() -> dict:
    config = RunnableConfig(callbacks=[CallbackHandler()])
    state = baseline.State(cwd=Path("./tst"), task=task)
    # context = baseline.Context(model="gpt-4o-mini", temperature=0.0)
    context = baseline.Context(model="gpt-5-mini", temperature=0.0)
    graph = baseline.build()
    return await graph.ainvoke(input=state, config=config, context=context)


async def run_tuning(code: str) -> dict:
    config = RunnableConfig(callbacks=[CallbackHandler()])
    state = tuning.State(cwd=Path("./tst"), task=task, code=code)
    # context = tuning.Context(model="gpt-4o-mini", temperature=0.0)
    context = tuning.Context(model="gpt-5-mini", temperature=0.0)
    graph = tuning.build()
    return await graph.ainvoke(input=state, config=config, context=context)


async def main() -> None:
    r_baseline = await run_baseline()
    pp(r_baseline)

    print("=" * 80)

    r_tuning = await run_tuning(r_baseline["code"])
    pp(r_tuning)


if __name__ == "__main__":
    logging.config.dictConfig(
      {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(levelname)s [%(asctime)s] %(name)s - %(message)s",
                },
            },
            "handlers": {
                "stderr": {
                    "class": logging.StreamHandler,
                    "formatter": "standard",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "aigraph": {
                    "handlers": ["stderr"],
                    "level": logging.DEBUG,
                },
            },
        }
    )
    asyncio.run(main())
