"""configuration and setup utils"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Hashable, List, Optional, cast

import coolname  # type: ignore[import-untyped]
import rich
import shutup  # type: ignore[import-untyped]
from dataclasses_json import DataClassJsonMixin
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict, Field
from rich.logging import RichHandler
from rich.syntax import Syntax

from ..journal import Journal
from . import copytree, preproc_data, serialize, tree_export

shutup.mute_warnings()
logging.basicConfig(level="WARNING", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
logger = logging.getLogger("ai-scientist")
logger.setLevel(logging.WARNING)


""" these dataclasses are just for type hinting, the actual config is in config.yaml """


class TaskDescription(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(alias="Name")
    title: str = Field(alias="Title")
    short_hypothesis: str = Field(alias="Short Hypothesis")
    related_work: str = Field(alias="Related Work")
    abstract: str = Field(alias="Abstract")
    code: str | None = Field(default=None, alias="Code")
    experiments: str | List[str] | List[Dict[str, str]] = Field(alias="Experiments")
    risk_factors_and_limitations: str | List[str] = Field(alias="Risk Factors and Limitations")

    def as_dict_with_aliases(self) -> Dict[str, object]:
        return self.model_dump(by_alias=True)


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
    desc_file: Path

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


def _load_cfg(path: Path, use_cli_args: bool = False) -> object:
    cfg = OmegaConf.load(path)
    if use_cli_args:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_cli())
    return cfg


def load_cfg(path: Path) -> Config:
    """Load config from .yaml file and CLI args, and set up logging directory."""
    return prep_cfg(_load_cfg(path))


def prep_cfg(cfg: object) -> Config:
    # Merge with structured schema and convert to dataclass instance
    schema = OmegaConf.structured(Config)
    merged = OmegaConf.merge(schema, cfg)
    cfg_obj = cast(Config, OmegaConf.to_object(merged))

    if cfg_obj.data_dir is None:
        raise ValueError("`data_dir` must be provided.")

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


def load_task_desc(cfg: Config) -> TaskDescription:
    """Load task description JSON and return a dict with aliased keys."""

    desc_path = Path(cfg.desc_file)
    if not desc_path.exists():
        raise FileNotFoundError(str(desc_path))

    raw = desc_path.read_text()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Task description JSON must be an object")

    model = TaskDescription.model_validate(data)
    return model


def prep_agent_workspace(cfg: Config) -> None:
    """Setup the agent's workspace and preprocess data if necessary."""
    (cfg.workspace_dir / "input").mkdir(parents=True, exist_ok=True)
    (cfg.workspace_dir / "working").mkdir(parents=True, exist_ok=True)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    copytree(cfg.data_dir, cfg.workspace_dir / "input", use_symlinks=not cfg.copy_data)
    if cfg.preprocess_data:
        preproc_data(cfg.workspace_dir / "input")


def save_run(cfg: Config, journal: Journal, stage_name: str) -> None:
    save_dir = cfg.log_dir / stage_name
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
        tree_export.generate(
            exp_name=cfg.exp_name,
            jou=journal,
            out_path=save_dir / "tree_plot.html",
        )
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
