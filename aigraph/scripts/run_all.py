import json
from pathlib import Path
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliApp, CliImplicitFlag, CliPositionalArg

from pydantic import BaseModel

from aigraph import utils, log
from aigraph.agents import ablation, baseline, plotting, tuning, writeup

task = utils.Task.model_validate(
    {
        "Name": "rare_token_persistence",
        "Title": "Rare Token Persistence: Measuring Retention of Rare Tokens in Small Language Models",
        "Short Hypothesis": "Language models remember and reproduce rare tokens more reliably than common ones, even after additional fine-tuning on unrelated data. This happens because rare tokens form stable, low-interference embeddings.",
        "Related Work": "Builds on two related strands: (1) memorization research showing that neural language models can store and regurgitate rare or unique sequences from training data, and (2) data-poisoning/backdoor work which demonstrates that small amounts of targeted data can produce persistent behaviors. Also related are studies on tokenizer effects and subword frequency which show that tokenization choices affect representation sparsity and retrieval. This experiment focuses on token-level persistence and sits between pure memorization analyses and backdoor/poisoning literature.",
        "Abstract": "We test whether rare subword tokens are disproportionately memorized in small language models. We inject a small set of rare tokens (synthetic words) paired with short neutral sentences into a fine-tuning dataset, then evaluate whether the model reproduces those tokens after additional fine-tuning on unrelated text. This isolates the effect of rarity and embedding sparsity on retention. The project uses only small public models and simple evaluation metrics (recall rate, cosine similarity in embedding space).",
        "Experiments": [
            "E1: Identify 10 rare tokens from the model's tokenizer vocabulary (low frequency in corpus).",
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
    # inputs
    cwd: Path
    task: utils.Task

    state_baseline: baseline.State | None = None
    state_tuning: tuning.State | None = None
    state_ablation: ablation.State | None = None
    state_plotting: plotting.State | None = None
    state_writeup: writeup.State | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


async def node_baseline(state: State, runtime: Runtime[Context]) -> State:
    baseline_state = baseline.State(
        cwd=state.cwd,
        task=state.task,
    )
    baseline_context = baseline.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = baseline.build()
    result = await graph.ainvoke(
        input=baseline_state,
        context=baseline_context,
    )

    state.state_baseline = baseline.State.model_validate(result)

    return state


async def node_tuning(state: State, runtime: Runtime[Context]) -> State:
    assert state.state_baseline
    assert state.state_baseline.experiment_code

    tuning_state = tuning.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_baseline.experiment_code,
    )
    tuning_context = tuning.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = tuning.build()
    result = await graph.ainvoke(
        input=tuning_state,
        context=tuning_context,
    )

    state.state_tuning = tuning.State.model_validate(result)

    return state


async def node_ablation(state: State, runtime: Runtime[Context]) -> State:
    assert state.state_tuning
    assert state.state_tuning.tuning_code

    ablation_state = ablation.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_tuning.tuning_code,
    )
    ablation_context = ablation.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = ablation.build()
    result = await graph.ainvoke(
        input=ablation_state,
        context=ablation_context,
    )

    state.state_ablation = ablation.State.model_validate(result)

    return state


async def node_plotting(state: State, runtime: Runtime[Context]) -> State:
    assert state.state_ablation
    assert state.state_ablation.ablation_code

    plotting_state = plotting.State(
        cwd=state.cwd,
        task=state.task,
        code=state.state_ablation.ablation_code,
    )
    plotting_context = plotting.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = plotting.build()
    result = await graph.ainvoke(
        input=plotting_state,
        context=plotting_context,
    )
    state.state_plotting = plotting.State.model_validate(result)

    return state


async def node_writeup(state: State, runtime: Runtime[Context]) -> State:
    assert state.state_plotting
    assert state.state_ablation
    assert state.state_ablation.ablation_code
    assert state.state_ablation.parser_code

    writeup_state = writeup.State(
        cwd=state.cwd,
        task=state.task,
        experiment_code=state.state_ablation.ablation_code,
        parser_code=state.state_ablation.parser_code,
        plots=list(state.state_plotting.plots),
    )
    writeup_context = writeup.Context(
        model=runtime.context.model,
        temperature=runtime.context.temperature,
    )

    graph = writeup.build()
    result = await graph.ainvoke(
        input=writeup_state,
        context=writeup_context,
    )

    state.state_writeup = writeup.State.model_validate(result)

    return state


def build() -> CompiledStateGraph[State, Context, State, State]:
    builder = StateGraph(state_schema=State, context_schema=Context)

    # Add nodes
    builder.add_node("node_baseline", node_baseline)
    builder.add_node("node_tuning", node_tuning)
    builder.add_node("node_ablation", node_ablation)
    builder.add_node("node_plotting", node_plotting)
    builder.add_node("node_writeup", node_writeup)

    # Add edges
    builder.add_edge(START, "node_baseline")
    builder.add_edge("node_baseline", "node_tuning")
    builder.add_edge("node_tuning", "node_ablation")
    builder.add_edge("node_ablation", "node_plotting")
    builder.add_edge("node_plotting", "node_writeup")
    builder.add_edge("node_writeup", END)

    return builder.compile(name="graph_all")  # type: ignore


class Args(BaseSettings):
    cwd: CliPositionalArg[Path]

    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    verbose: Annotated[
        CliImplicitFlag[bool], Field(validation_alias=AliasChoices("verbose", "v"))
    ] = False

    async def cli_cmd(self) -> None:
        if self.verbose:
            log.init()

        config = RunnableConfig(callbacks=[CallbackHandler()])
        state = State(cwd=self.cwd, task=task)
        context = Context(model=self.model, temperature=self.temperature)

        graph = build()
        result = await graph.ainvoke(input=state, context=context, config=config)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    CliApp.run(Args)
