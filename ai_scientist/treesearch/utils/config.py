"""configuration and setup utils"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Hashable, Optional, cast

import coolname  # type: ignore[import-untyped]
import rich
import shutup  # type: ignore[import-untyped]
from dataclasses_json import DataClassJsonMixin
from omegaconf import OmegaConf
from rich.logging import RichHandler
from rich.syntax import Syntax

from ..journal import Journal
from . import copytree, preproc_data, serialize, tree_export

shutup.mute_warnings()
logging.basicConfig(level="WARNING", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
logger = logging.getLogger("ai-scientist")
logger.setLevel(logging.WARNING)


""" these dataclasses are just for type hinting, the actual config is in config.yaml """


@dataclass
class ThinkingConfig:
    type: str
    budget_tokens: Optional[int] = None


@dataclass
class StageConfig:
    model: str
    temp: float
    thinking: ThinkingConfig
    betas: str
    max_tokens: Optional[int] = None


@dataclass
class SearchConfig:
    max_debug_depth: int
    debug_prob: float
    num_drafts: int


@dataclass
class DebugConfig:
    stage4: bool


@dataclass
class AgentConfig:
    steps: int
    stages: dict[str, int]
    k_fold_validation: int
    expose_prediction: bool
    data_preview: bool

    code: StageConfig
    feedback: StageConfig
    vlm_feedback: StageConfig

    search: SearchConfig
    num_workers: int
    type: str
    multi_seed_eval: dict[str, int]


@dataclass
class ExecConfig:
    timeout: int
    agent_file_name: str
    format_tb_ipython: bool


@dataclass
class ExperimentConfig:
    num_syn_datasets: int


@dataclass
class WriteupConfig:
    big_model: str
    small_model: str
    plot_model: str


@dataclass
class GPUConfig:
    type: str
    count: int
    vram_gb: int


@dataclass
class ComputeConfig:
    gpu: GPUConfig
    notes: str


@dataclass
class Config(Hashable):
    data_dir: Path
    desc_file: Path | None

    goal: str | None
    eval: str | None

    log_dir: Path
    workspace_dir: Path

    preprocess_data: bool
    copy_data: bool

    exp_name: str

    exec: ExecConfig
    generate_report: bool
    report: StageConfig
    writeup: Optional[WriteupConfig]
    agent: AgentConfig
    experiment: ExperimentConfig
    compute: Optional[ComputeConfig]
    debug: DebugConfig


def _get_next_logindex(dir: Path) -> int:
    """Get the next available index for a log directory."""
    max_index = -1
    for p in dir.iterdir():
        try:
            if (current_index := int(p.name.split("-")[0])) > max_index:
                max_index = current_index
        except ValueError:
            pass
    print("max_index: ", max_index)
    return max_index + 1


def _load_cfg(
    path: Path = Path(__file__).parent / "config.yaml", use_cli_args: bool = False
) -> object:
    cfg = OmegaConf.load(path)
    if use_cli_args:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_cli())
    return cfg


def load_cfg(path: Path = Path(__file__).parent / "config.yaml") -> Config:
    """Load config from .yaml file and CLI args, and set up logging directory."""
    return prep_cfg(_load_cfg(path))


def prep_cfg(cfg: object) -> Config:
    # Merge with structured schema and convert to dataclass instance
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, cfg)
    cfg_obj = cast(Config, OmegaConf.to_object(merged))

    if cfg_obj.data_dir is None:
        raise ValueError("`data_dir` must be provided.")

    if cfg_obj.desc_file is None and cfg_obj.goal is None:
        raise ValueError(
            "You must provide either a description of the task goal (`goal=...`) or a path to a plaintext file containing the description (`desc_file=...`)."
        )

    # Normalize and resolve paths
    data_dir_path = Path(cfg_obj.data_dir)
    if str(data_dir_path).startswith("example_tasks/"):
        data_dir_path = Path(__file__).parent.parent / data_dir_path
    cfg_obj.data_dir = data_dir_path.resolve()

    if cfg_obj.desc_file is not None:
        desc_file_path = Path(cfg_obj.desc_file)
        cfg_obj.desc_file = desc_file_path.resolve()

    top_log_dir = Path(cfg_obj.log_dir).resolve()
    top_log_dir.mkdir(parents=True, exist_ok=True)

    top_workspace_dir = Path(cfg_obj.workspace_dir).resolve()
    top_workspace_dir.mkdir(parents=True, exist_ok=True)

    # generate experiment name and prefix with consecutive index
    ind = max(_get_next_logindex(top_log_dir), _get_next_logindex(top_workspace_dir))
    cfg_obj.exp_name = cfg_obj.exp_name or coolname.generate_slug(3)
    cfg_obj.exp_name = f"{ind}-{cfg_obj.exp_name}"

    cfg_obj.log_dir = (top_log_dir / cfg_obj.exp_name).resolve()
    cfg_obj.workspace_dir = (top_workspace_dir / cfg_obj.exp_name).resolve()

    if cfg_obj.agent.type not in ["parallel", "sequential"]:
        raise ValueError("agent.type must be either 'parallel' or 'sequential'")

    return cfg_obj


def print_cfg(cfg: Config) -> None:
    rich.print(Syntax(OmegaConf.to_yaml(OmegaConf.structured(cfg)), "yaml", theme="paraiso-dark"))


def load_task_desc(cfg: Config) -> str | dict:
    """Load task description from markdown file or config str."""

    # either load the task description from a file
    if cfg.desc_file is not None:
        if not (cfg.goal is None and cfg.eval is None):
            logger.warning("Ignoring goal and eval args because task description file is provided.")

        with open(cfg.desc_file) as f:
            return f.read()

    # or generate it from the goal and eval args
    if cfg.goal is None:
        raise ValueError(
            "`goal` (and optionally `eval`) must be provided if a task description file is not provided."
        )

    task_desc = {"Task goal": cfg.goal}
    if cfg.eval is not None:
        task_desc["Task evaluation"] = cfg.eval
    print(task_desc)
    return task_desc


def prep_agent_workspace(cfg: Config) -> None:
    """Setup the agent's workspace and preprocess data if necessary."""
    (cfg.workspace_dir / "input").mkdir(parents=True, exist_ok=True)
    (cfg.workspace_dir / "working").mkdir(parents=True, exist_ok=True)

    copytree(cfg.data_dir, cfg.workspace_dir / "input", use_symlinks=not cfg.copy_data)
    if cfg.preprocess_data:
        preproc_data(cfg.workspace_dir / "input")


def save_run(cfg: Config, journal: Journal, stage_name: str | None = None) -> None:
    stage = stage_name if stage_name is not None else "NoStageRun"
    save_dir = cfg.log_dir / stage
    save_dir.mkdir(parents=True, exist_ok=True)

    # save journal
    try:
        # Journal is compatible with serialization utilities; cast for typing
        serialize.dump_json(cast(DataClassJsonMixin, journal), save_dir / "journal.json")
    except Exception as e:
        print(f"Error saving journal: {e}")
        raise
    # save config
    try:
        OmegaConf.save(config=cfg, f=save_dir / "config.yaml")
    except Exception as e:
        print(f"Error saving config: {e}")
        raise
    # create the tree + code visualization
    try:
        tree_export.generate(cfg, journal, save_dir / "tree_plot.html")
    except Exception as e:
        print(f"Error generating tree: {e}")
        raise
    # save the best found solution
    try:
        best_node = journal.get_best_node(only_good=False)
        if best_node is not None:
            for existing_file in save_dir.glob("best_solution_*.py"):
                existing_file.unlink()
            # Create new best solution file
            filename = f"best_solution_{best_node.id}.py"
            with open(save_dir / filename, "w") as f:
                f.write(best_node.code)
            # save best_node.id to a text file
            with open(save_dir / "best_node_id.txt", "w") as f:
                f.write(str(best_node.id))
        else:
            print("No best node found yet")
    except Exception as e:
        print(f"Error saving best solution: {e}")
