import logging
import shutil
from pathlib import Path

from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel

from aigraph import utils
from aigraph.agents import writeup_prompts as prompts

logger = logging.getLogger(__name__)


class State(BaseModel):
    # inputs
    cwd: Path
    task: utils.Task

    experiment_code: str
    parser_code: str
    images: list[str] = []

    latex_dir: Path | None = None
    latex_content: str | None = None
    latex_bibtex: str | None = None


class Context(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0

    @property
    def llm(self) -> BaseChatModel:
        return init_chat_model(model=self.model, temperature=self.temperature)


async def node_writeup_setup_writeup(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_writeup_setup_writeup")

    src = utils.DATA_DIR / "latex"
    dst = state.cwd / "latex" 

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    state.latex_dir = dst

    logger.info("Finished node_writeup_setup_writeup")
    return state


async def node_writeup_generate_writeup(state: State, runtime: Runtime[Context]) -> State:
    logger.info("Starting node_writeup_generate_writeup")

    class Schema(BaseModel):
        content: str
        bibtex: str
    
    system = prompts.build_writeup_system_message(
        task=state.task, 
        pages=5,
    )

    prompt = prompts.build_writeup_prompt(
        code_experiment=state.experiment_code, 
        code_parser=state.parser_code, 
        images=state.images,
    )

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ]

    llms = runtime.context.llm.with_structured_output(Schema)
    response: Schema = await llms.ainvoke(messages)  # type: ignore
    state.latex_content = response.content
    state.latex_bibtex = response.bibtex

    logger.debug(f"latex_content: {state.latex_content[:32]!r}")
    logger.debug(f"latex_bibtex: {state.latex_bibtex[:32]!r}")
    
    logger.info("Finished node_writeup_generate_writeup")
    return state
