import asyncio
import logging
import logging.config
from pathlib import Path
from pprint import pp
from typing import Any

from langfuse.langchain import CallbackHandler
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph, RunnableConfig
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import ablation, baseline, plotting, tuning

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


class State(BaseModel):
    cwd: Path
    task: utils.Task

    baseline_output: dict[str, Any] | None = None
    tuning_output: dict[str, Any] | None = None
    ablation_output: dict[str, Any] | None = None
    plotting_output: dict[str, Any] | None = None


async def node_baseline(state: State) -> State:
    sub_state = baseline.State(cwd=state.cwd, task=state.task)
    sub_context = baseline.Context(model="gpt-5-mini", temperature=0.0)
    graph = baseline.build()
    state.baseline_output = await graph.ainvoke(input=sub_state, context=sub_context)
    return state


async def node_tuning(state: State) -> State:
    assert state.baseline_output
    code = state.baseline_output["experiment_code"]
    
    sub_state = tuning.State(cwd=state.cwd, task=state.task, code=code)
    sub_context = tuning.Context(model="gpt-5-mini", temperature=0.0)
    
    graph = tuning.build()
    state.tuning_output = await graph.ainvoke(input=sub_state, context=sub_context)
    return state


async def node_ablation(state: State) -> State:
    assert state.tuning_output
    code = state.tuning_output["tuning_code"]
    
    sub_state = ablation.State(cwd=state.cwd, task=state.task, code=code)
    sub_context = ablation.Context(model="gpt-5-mini", temperature=0.0)
    
    graph = ablation.build()
    state.ablation_output = await graph.ainvoke(input=sub_state, context=sub_context)
    return state


async def node_plotting(state: State) -> State:
    assert state.tuning_output
    code = state.tuning_output["tuning_code"]
    
    sub_state = plotting.State(cwd=state.cwd, task=state.task, code=code)
    sub_context = plotting.Context(model="gpt-5-mini", temperature=0.0)
    
    graph = plotting.build()
    state.plotting_output = await graph.ainvoke(input=sub_state, context=sub_context)
    return state


async def main() -> None:
    builder = StateGraph(State)
    builder.add_node("baseline", node_baseline)
    builder.add_node("tuning", node_tuning)
    builder.add_node("ablation", node_ablation)
    builder.add_node("plotting", node_plotting)
    
    builder.add_edge(START, "baseline")
    builder.add_edge("baseline", "tuning")
    builder.add_edge("tuning", "ablation")
    builder.add_edge("ablation", "plotting")
    builder.add_edge("plotting", END)
    
    graph: CompiledStateGraph[State, None, State, State] = builder.compile() # type: ignore
    
    state = State(cwd=Path("./tst"), task=task)
    result = await graph.ainvoke(input=state)
    
    pp(result["baseline_output"])
    print("=" * 80)
    pp(result["tuning_output"])
    print("=" * 80)
    pp(result["ablation_output"])
    print("=" * 80)
    pp(result["plotting_output"])
    print("=" * 80)


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
