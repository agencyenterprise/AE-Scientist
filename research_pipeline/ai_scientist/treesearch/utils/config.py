"""configuration and setup utils"""

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Hashable, List, Optional, cast

import coolname  # type: ignore[import-untyped]
import shutup  # type: ignore[import-untyped]
from dataclasses_json import DataClassJsonMixin
from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict, Field

from ..journal import Journal
from . import serialize, tree_export

shutup.mute_warnings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-scientist")
logger.setLevel(logging.INFO)


def apply_log_level(*, level_name: str) -> None:
    """Apply logging level and formatter globally.

    This overrides any earlier basicConfig/env defaults and ensures consistency
    across main and worker processes.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    logging.getLogger("ai-scientist").setLevel(level)
    # Suppress noisy third-party debug logs the user doesn't want
    try:
        fm_logger = logging.getLogger("matplotlib.font_manager")
        fm_logger.setLevel(logging.WARNING)
        fm_logger.propagate = False
        # Suppress OpenAI client/httpx/httpcore, image loaders, and remote IO verbose logs
        noisy_loggers = [
            "matplotlib",
            "PIL",
            "PIL.PngImagePlugin",
            "openai",
            "openai._base_client",
            "openai._client",
            "httpx",
            "httpcore",
            "urllib3",
            "urllib3.connectionpool",
            "fsspec",
            "fsspec.spec",
            "s3fs",
            "datasets",
            "huggingface_hub",
        ]
        for name in noisy_loggers:
            lgr = logging.getLogger(name)
            # Completely silence debug/info chatter while still allowing critical errors
            if name.startswith("urllib3"):
                lgr.setLevel(logging.ERROR)
            else:
                lgr.setLevel(logging.WARNING)
            lgr.propagate = False
    except Exception:
        pass


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
class StageConfig:
    model: str
    temp: float


@dataclass
class SearchConfig:
    max_debug_depth: int
    debug_prob: float
    num_drafts: int


@dataclass
class AgentConfig:
    steps: int
    stages: dict[str, int]
    k_fold_validation: int

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
    model: str
    plot_model: str
    temperature: float = 1.0
    citation_model: Optional[str] = None
    writeup_type: str = "normal"
    writeup_retries: int = 3
    num_cite_rounds: int = 5


@dataclass
class ReviewConfig:
    model: str
    temperature: float


@dataclass
class Config(Hashable):
    desc_file: Path
    log_dir: Path
    workspace_dir: Path

    exp_name: str
    log_level: str

    exec: ExecConfig
    generate_report: bool
    report: StageConfig
    agent: AgentConfig
    experiment: ExperimentConfig
    writeup: Optional[WriteupConfig] = None
    review: Optional[ReviewConfig] = None


def _get_next_logindex(dir: Path) -> int:
    """Get the next available index for a log directory."""
    max_index = -1
    for p in dir.iterdir():
        try:
            if (current_index := int(p.name.split("-")[0])) > max_index:
                max_index = current_index
        except ValueError:
            pass
    logger.debug(f"max_index: {max_index}")
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

    # Apply logging level from config uniformly
    apply_log_level(level_name=cfg_obj.log_level)

    return cfg_obj


def print_cfg(cfg: Config) -> None:
    try:
        logger.info(OmegaConf.to_yaml(OmegaConf.structured(cfg)))
    except Exception:
        # Fallback to a basic print if structured conversion fails
        logger.info(str(cfg))


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

    # Persist the original idea file alongside inputs for traceability
    try:
        idea_src = Path(cfg.desc_file)
        idea_dst = cfg.workspace_dir / "input" / "original_idea.json"
        if idea_src.exists():
            shutil.copy2(idea_src, idea_dst)
    except Exception as e:
        logger.warning(f"Warning: failed to copy original idea file: {e}")


def save_run(cfg: Config, journal: Journal, stage_name: str) -> None:
    save_dir = cfg.log_dir / stage_name
    save_dir.mkdir(parents=True, exist_ok=True)

    # save journal
    try:
        # Journal is compatible with serialization utilities; cast for typing
        serialize.dump_json(cast(DataClassJsonMixin, journal), save_dir / "journal.json")
    except Exception as e:
        logger.exception(f"Error saving journal: {e}")
        raise
    # save config
    try:
        OmegaConf.save(config=cfg, f=save_dir / "config.yaml")
    except Exception as e:
        logger.exception(f"Error saving config: {e}")
        raise
    # create the tree + code visualization
    try:
        tree_export.generate(
            exp_name=cfg.exp_name,
            jou=journal,
            out_path=save_dir / "tree_plot.html",
        )
    except Exception as e:
        logger.exception(f"Error generating tree: {e}")
        raise
    # save the best found solution
    try:
        # Prefer good nodes first; only fall back to all nodes if no good nodes exist
        # Use metric-only selection to avoid unnecessary LLM calls for saving
        best_node = journal.get_best_node(only_good=True, use_val_metric_only=True)
        if best_node is None:
            # Fall back to all nodes (including buggy) only if no good nodes exist
            best_node = journal.get_best_node(only_good=False, use_val_metric_only=True)
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
            logger.info("No best node found yet")
    except Exception as e:
        logger.exception(f"Error saving best solution: {e}")
