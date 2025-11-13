"""
End-to-end launcher for the BFTS experiment workflow.

Steps:
- Parse CLI args and load config file
- Load the idea from config's desc_file and merge dataset reference code
- Run experiments via AgentManager (draft/debug/improve/tune/plot/ablate)
- Collect artifacts and aggregate plots
- Optionally generate the paper writeup
- Optionally perform paper review (text and images/captions/reference)
- Clean up spawned worker processes
"""

import argparse
import copy
import json
import os
import os.path as osp
import re
import shutil
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psutil
import yaml
from omegaconf import OmegaConf

from ai_scientist.llm import create_client, token_tracker
from ai_scientist.perform_icbinb_writeup import gather_citations
from ai_scientist.perform_icbinb_writeup import perform_writeup as perform_icbinb_writeup
from ai_scientist.perform_llm_review import load_paper, perform_review
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_vlm_review import perform_imgs_cap_ref_review
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_context import build_auto_review_context
from ai_scientist.treesearch.agent_manager import AgentManager
from ai_scientist.treesearch.bfts_utils import idea_to_markdown
from ai_scientist.treesearch.events import BaseEvent
from ai_scientist.treesearch.interpreter import ExecutionResult
from ai_scientist.treesearch.journal import Journal
from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import (
    perform_experiments_bfts,
)
from ai_scientist.treesearch.stages.base import StageMeta
from ai_scientist.treesearch.stages.stage1_baseline import Stage1Baseline
from ai_scientist.treesearch.stages.stage2_tuning import Stage2Tuning
from ai_scientist.treesearch.stages.stage3_plotting import Stage3Plotting
from ai_scientist.treesearch.stages.stage4_ablation import Stage4Ablation
from ai_scientist.treesearch.utils.config import Config, load_task_desc, prep_cfg, save_run
from ai_scientist.treesearch.utils.serialize import load_json as load_json_dc


def save_token_tracker(idea_dir: str) -> None:
    with open(osp.join(idea_dir, "token_tracker.json"), "w") as f:
        json.dump(token_tracker.get_summary(), f)
    with open(osp.join(idea_dir, "token_tracker_interactions.json"), "w") as f:
        json.dump(token_tracker.get_interactions(), f)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI scientist experiments")
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to the YAML configuration file (e.g., bfts_config.yaml)",
    )
    parser.add_argument(
        "--writeup-type",
        type=str,
        default="normal",
        choices=["normal", "icbinb"],
        help="Type of writeup to generate (normal=8 page, icbinb=4 page)",
    )
    parser.add_argument(
        "--writeup-retries",
        type=int,
        default=3,
        help="Number of writeup attempts to try",
    )
    parser.add_argument(
        "--model_agg_plots",
        type=str,
        required=True,
        help="Model to use for plot aggregation",
    )
    parser.add_argument(
        "--model_writeup",
        type=str,
        help="Model to use for writeup (required unless --skip_writeup is set)",
    )
    parser.add_argument(
        "--model_citation",
        type=str,
        help="Model to use for citation gathering (required unless --skip_writeup is set)",
    )
    parser.add_argument(
        "--num_cite_rounds",
        type=int,
        default=20,
        help="Number of citation rounds to perform",
    )
    parser.add_argument(
        "--model_review",
        type=str,
        help="Model to use for review main text and captions (required unless --skip_review or --skip_writeup is set)",
    )
    parser.add_argument(
        "--skip_writeup",
        action="store_true",
        help="If set, skip the writeup process",
    )
    parser.add_argument(
        "--skip_review",
        action="store_true",
        help="If set, skip the review process",
    )
    parser.add_argument(
        "--resume",
        type=str,
        metavar="RUN_NAME_OR_NUMBER",
        help="Resume from a specific run (e.g., 4 or 4-run)",
    )
    args = parser.parse_args()

    # Validate conditional requirements
    cfg_path = Path(args.config_file)
    if not cfg_path.exists():
        parser.error(f"Configuration file not found: {cfg_path}")

    if not args.skip_writeup:
        if args.model_writeup is None:
            parser.error("--model_writeup is required when writeup is not skipped")
        if args.model_citation is None:
            parser.error("--model_citation is required when writeup is not skipped")

    if not args.skip_review and not args.skip_writeup:
        if args.model_review is None:
            parser.error(
                "--model_review is required when review is not skipped and writeup is not skipped"
            )

    return args


def find_pdf_path_for_review(idea_dir: str, run_dir_name: str | None = None) -> str | None:
    # Look under the run-specific logs directory if provided
    search_dir = idea_dir
    if run_dir_name:
        candidate = osp.join(idea_dir, "logs", run_dir_name)
        if os.path.exists(candidate):
            search_dir = candidate
    pdf_files = [f for f in os.listdir(search_dir) if f.endswith(".pdf")]
    reflection_pdfs = [f for f in pdf_files if "reflection" in f]

    pdf_path = None  # Initialize to avoid UnboundLocalError

    if reflection_pdfs:
        # First check if there's a final version
        final_pdfs = [f for f in reflection_pdfs if "final" in f.lower()]
        if final_pdfs:
            # Use the final version if available
            pdf_path = osp.join(search_dir, final_pdfs[0])
        else:
            # Try to find numbered reflections
            reflection_nums = []
            for f in reflection_pdfs:
                match = re.search(r"reflection[_.]?(\d+)", f)
                if match:
                    reflection_nums.append((int(match.group(1)), f))

            if reflection_nums:
                # Get the file with the highest reflection number
                highest_reflection = max(reflection_nums, key=lambda x: x[0])
                pdf_path = osp.join(search_dir, highest_reflection[1])
            else:
                # Fall back to the first reflection PDF if no numbers found
                pdf_path = osp.join(search_dir, reflection_pdfs[0])
    elif pdf_files:
        # No reflection PDFs, use any PDF
        pdf_path = osp.join(search_dir, pdf_files[0])

    return pdf_path


@contextmanager
def redirect_stdout_stderr_to_file(log_file_path: str) -> Generator[None, None, None]:
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log = open(log_file_path, "a")
    sys.stdout = log
    sys.stderr = log
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log.close()


if __name__ == "__main__":
    # Parse CLI arguments
    args = parse_arguments()

    # Load base config from the provided path (do not override directories)
    base_config_path = str(Path(args.config_file))
    with open(base_config_path, "r") as f:
        base_cfg = yaml.load(f, Loader=yaml.FullLoader)
    top_log_dir = Path(base_cfg["log_dir"]).resolve()
    top_log_dir.mkdir(parents=True, exist_ok=True)
    existing_runs_before = {p.name for p in top_log_dir.iterdir() if p.is_dir()}
    reports_base = str(top_log_dir.parent.resolve())

    # Helper functions for resume flow
    def _select_latest_run_dir(logs_root: Path) -> Path:
        run_dirs = [p for p in logs_root.iterdir() if p.is_dir()]
        if not run_dirs:
            raise FileNotFoundError(f"No run directories found under {logs_root}")
        return max(run_dirs, key=lambda p: p.stat().st_mtime)

    def _select_stage1_dir(run_dir: Path) -> Path:
        stage_dirs = sorted(
            [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_1_")]
        )
        if not stage_dirs:
            raise FileNotFoundError(f"No stage_1_* directory found under {run_dir}")
        return stage_dirs[-1]

    def _select_stage_dir(run_dir: Path, prefix: str) -> Path:
        stage_dirs = sorted(
            [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith(prefix)]
        )
        if not stage_dirs:
            raise FileNotFoundError(f"No {prefix}* directory found under {run_dir}")
        return stage_dirs[-1]

    def _load_cfg_from_run(run_dir: Path) -> Config:
        try:
            stage1_dir = _select_stage1_dir(run_dir)
            cfg_path = stage1_dir / "config.yaml"
        except FileNotFoundError:
            stage_dirs = sorted(
                [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("stage_")]
            )
            if not stage_dirs:
                raise
            cfg_path = stage_dirs[-1] / "config.yaml"
        if not cfg_path.exists():
            raise FileNotFoundError(str(cfg_path))
        raw = OmegaConf.load(str(cfg_path))
        schema = OmegaConf.structured(Config)
        merged = OmegaConf.merge(schema, raw)
        cfg_obj = OmegaConf.to_object(merged)
        assert isinstance(cfg_obj, Config)
        return cfg_obj

    def _load_stage1_journal(stage1_dir: Path) -> tuple[str, Journal]:
        stage_name = stage1_dir.name.replace("stage_", "", 1)
        journal_path = stage1_dir / "journal.json"
        if not journal_path.exists():
            raise FileNotFoundError(str(journal_path))
        journal = load_json_dc(path=journal_path, cls=Journal)
        return stage_name, journal

    def _load_stage_journal(stage_dir: Path) -> tuple[str, Journal]:
        stage_name = stage_dir.name.replace("stage_", "", 1)
        journal_path = stage_dir / "journal.json"
        if not journal_path.exists():
            raise FileNotFoundError(str(journal_path))
        journal = load_json_dc(path=journal_path, cls=Journal)
        return stage_name, journal

    def _stage_exists(run_dir: Path, prefix: str) -> bool:
        try:
            _select_stage_dir(run_dir, prefix)
            return True
        except FileNotFoundError:
            return False

    def _all_summaries_exist(run_dir: Path) -> bool:
        # Summary JSONs expected at run_dir level
        paths = [
            run_dir / "draft_summary.json",
            run_dir / "baseline_summary.json",
            run_dir / "research_summary.json",
            run_dir / "ablation_summary.json",
        ]
        return all(p.exists() for p in paths)

    # Load the idea JSON from config's desc_file and merge dataset reference
    idea_json_path = str(Path(base_cfg["desc_file"]).resolve())
    with open(idea_json_path, "r") as f:
        idea = json.load(f)
        print(f"Loaded idea from {idea_json_path}")

    # Base folder (next to the idea JSON) to collect artifacts for plotting/writeup
    base_folder = str(Path(idea_json_path).parent.resolve())

    # Ensure a markdown version of the idea exists at the reports base for plotting/writeup
    try:
        md_output_path = Path(reports_base) / "research_idea.md"
        idea_to_markdown(data=idea, output_path=str(md_output_path), load_code="")
        print(f"Wrote research idea markdown to {md_output_path}")
    except Exception:
        traceback.print_exc()
        print("Failed to write research_idea.md; continuing without it.")

    # Execute experiments via AgentManager (BFTS pipeline) or resume to Stage 2
    # Track selected resume run directory for later reporting/aggregation
    resume_run_dir: Path | None = None

    if args.resume is not None:
        try:

            def _normalize_run_name(run_arg: str) -> str:
                s = run_arg.strip()
                if s.isdigit():
                    return f"{s}-run"
                if s.startswith("run-") and s[4:].isdigit():
                    return f"{s[4:]}-run"
                return s

            logs_root = Path(base_cfg["log_dir"]).resolve()
            run_name = _normalize_run_name(args.resume)
            run_dir = (logs_root / run_name).resolve()
            if not run_dir.exists():
                raise FileNotFoundError(str(run_dir))
            resume_run_dir = run_dir

            cfg_obj = _load_cfg_from_run(run_dir=run_dir)
            # Apply global logging level from config so DEBUG logs are emitted
            cfg_obj = prep_cfg(cfg=cfg_obj)
            # Decide which stage (if any) to run, or skip to post-processing
            if _all_summaries_exist(run_dir=run_dir):
                # Everything is already summarized for this run; skip stages
                print(
                    "All summary files found; skipping stage execution and proceeding to reports."
                )
            else:
                # Determine which next stage to run based on existing stage artifacts
                s1 = _stage_exists(run_dir=run_dir, prefix="stage_1_")
                s2 = _stage_exists(run_dir=run_dir, prefix="stage_2_")
                s3 = _stage_exists(run_dir=run_dir, prefix="stage_3_")
                s4 = _stage_exists(run_dir=run_dir, prefix="stage_4_")

                next_stage: int | None = None
                if s1 and not s2:
                    next_stage = 2
                elif s2 and not s3:
                    next_stage = 3
                elif s3 and not s4:
                    next_stage = 4
                else:
                    # Either only Stage 1 missing, or all stages present - nothing to run
                    next_stage = None

                if next_stage is not None:
                    # Load task description using the same mechanism as stage launchers
                    fake_config = copy.deepcopy(cfg_obj)
                    fake_config.desc_file = Path(idea_json_path)
                    task_desc = load_task_desc(cfg=fake_config)

                    def on_event(event: BaseEvent) -> None:
                        try:
                            print(event.to_dict())
                        except Exception:
                            traceback.print_exc()

                    manager = AgentManager(
                        task_desc=task_desc,
                        cfg=cfg_obj,
                        workspace_dir=Path(cfg_obj.workspace_dir),
                        event_callback=on_event,
                    )

                    # Seed previous stages' metas and journals
                    if s1:
                        stage1_dir = _select_stage_dir(run_dir=run_dir, prefix="stage_1_")
                        stage1_name, stage1_journal = _load_stage_journal(stage_dir=stage1_dir)
                        stage1_meta = StageMeta(
                            name=stage1_name,
                            number=1,
                            slug=Stage1Baseline.MAIN_STAGE_SLUG,
                            substage_number=1,
                            substage_name="preliminary",
                            goals=Stage1Baseline.DEFAULT_GOALS,
                            max_iterations=manager._get_max_iterations(1),
                            num_drafts=0,
                        )
                        manager.stages.append(stage1_meta)
                        manager.journals[stage1_meta.name] = stage1_journal

                    if s2 or (next_stage and next_stage > 2):
                        # If Stage 2 exists (or we're going to Stage 3/4), seed Stage 2
                        try:
                            stage2_dir = _select_stage_dir(run_dir=run_dir, prefix="stage_2_")
                            stage2_name, stage2_journal = _load_stage_journal(stage_dir=stage2_dir)
                            stage2_meta = StageMeta(
                                name=stage2_name,
                                number=2,
                                slug=Stage2Tuning.MAIN_STAGE_SLUG,
                                substage_number=1,
                                substage_name="first_attempt",
                                goals=Stage2Tuning.DEFAULT_GOALS,
                                max_iterations=manager._get_max_iterations(2),
                                num_drafts=0,
                            )
                            manager.stages.append(stage2_meta)
                            manager.journals[stage2_meta.name] = stage2_journal
                        except FileNotFoundError:
                            # Ok if we're about to run Stage 2
                            pass

                    if s3 or (next_stage and next_stage > 3):
                        # If Stage 3 exists (or we're going to Stage 4), seed Stage 3
                        try:
                            stage3_dir = _select_stage_dir(run_dir=run_dir, prefix="stage_3_")
                            stage3_name, stage3_journal = _load_stage_journal(stage_dir=stage3_dir)
                            stage3_meta = StageMeta(
                                name=stage3_name,
                                number=3,
                                slug=Stage3Plotting.MAIN_STAGE_SLUG,
                                substage_number=1,
                                substage_name="first_attempt",
                                goals=Stage3Plotting.DEFAULT_GOALS,
                                max_iterations=manager._get_max_iterations(3),
                                num_drafts=0,
                            )
                            manager.stages.append(stage3_meta)
                            manager.journals[stage3_meta.name] = stage3_journal
                        except FileNotFoundError:
                            # Ok if we're about to run Stage 3
                            pass

                    # Create next stage meta and journal, then run only that stage
                    if next_stage == 2:
                        next_meta = StageMeta(
                            name="2_" + Stage2Tuning.MAIN_STAGE_SLUG + "_1_first_attempt",
                            number=2,
                            slug=Stage2Tuning.MAIN_STAGE_SLUG,
                            substage_number=1,
                            substage_name="first_attempt",
                            goals=Stage2Tuning.DEFAULT_GOALS,
                            max_iterations=manager._get_max_iterations(2),
                            num_drafts=0,
                        )
                    elif next_stage == 3:
                        next_meta = StageMeta(
                            name="3_" + Stage3Plotting.MAIN_STAGE_SLUG + "_1_first_attempt",
                            number=3,
                            slug=Stage3Plotting.MAIN_STAGE_SLUG,
                            substage_number=1,
                            substage_name="first_attempt",
                            goals=Stage3Plotting.DEFAULT_GOALS,
                            max_iterations=manager._get_max_iterations(3),
                            num_drafts=0,
                        )
                    else:  # next_stage == 4
                        next_meta = StageMeta(
                            name="4_" + Stage4Ablation.MAIN_STAGE_SLUG + "_1_first_attempt",
                            number=4,
                            slug=Stage4Ablation.MAIN_STAGE_SLUG,
                            substage_number=1,
                            substage_name="first_attempt",
                            goals=Stage4Ablation.DEFAULT_GOALS,
                            max_iterations=manager._get_max_iterations(4),
                            num_drafts=0,
                        )

                    manager.stages.append(next_meta)
                    manager.current_stage = next_meta
                    manager.journals[next_meta.name] = Journal(
                        summary_model=cfg_obj.report.model,
                        node_selection_model=cfg_obj.agent.feedback.model,
                        event_callback=on_event,
                    )

                    def step_callback(stage: StageMeta, journal: Journal) -> None:
                        try:
                            save_run(cfg=cfg_obj, journal=journal, stage_name=f"stage_{stage.name}")
                        except Exception:
                            traceback.print_exc()

                    def exec_callback(code: str, is_exec: bool) -> ExecutionResult:
                        return ExecutionResult(term_out=[], exec_time=0.0, exc_type=None)

                    manager.run_stage(
                        initial_substage=next_meta,
                        exec_callback=exec_callback,
                        step_callback=step_callback,
                    )
        except Exception:
            traceback.print_exc()
            print("Resume failed; exiting.")
            sys.exit(1)
    else:
        perform_experiments_bfts(Path(base_config_path), lambda event: print(event.to_dict()))

    # Identify newly created run directory under configured log_dir
    run_dir_path: Path | None = None
    if resume_run_dir is not None:
        run_dir_path = resume_run_dir
    else:
        try:
            new_runs = [
                p
                for p in top_log_dir.iterdir()
                if p.is_dir() and p.name not in existing_runs_before
            ]
            if new_runs:
                run_dir_path = max(new_runs, key=lambda p: p.stat().st_mtime)
            else:
                candidates = [p for p in top_log_dir.iterdir() if p.is_dir()]
                run_dir_path = max(candidates, key=lambda p: p.stat().st_mtime)
        except Exception:
            traceback.print_exc()
            run_dir_path = None

    # (No mirroring) Use configured log_dir as the source of truth for summaries

    # Determine if we should run aggregation/writeup based on presence of best solutions
    should_run_reports = False
    if run_dir_path is not None:
        try:
            has_best = any(run_dir_path.glob("stage_*/best_solution_*.py"))
            if has_best:
                should_run_reports = True
            else:
                print("No best_solution files found; skipping plot aggregation and writeup.")
        except Exception:
            traceback.print_exc()
            print("Could not scan for best_solution files; skipping plot aggregation and writeup.")
            should_run_reports = False

    # Aggregate plots across runs (guarded and resilient)
    agg_ok = False
    if should_run_reports:
        try:
            aggregate_plots(
                base_folder=reports_base,
                model=args.model_agg_plots,
                run_dir_name=run_dir_path.name if run_dir_path is not None else None,
            )
            agg_ok = True
        except Exception as e:
            print(f"Aggregate plots failed: {e}. Skipping writeup.")
            traceback.print_exc()

    # Remove the transient aggregated results folder (copied above)
    shutil.rmtree(osp.join(reports_base, "experiment_results"), ignore_errors=True)

    # Persist token accounting information
    save_token_tracker(run_dir_path.as_posix() if run_dir_path is not None else reports_base)

    if not args.skip_writeup and should_run_reports and agg_ok:
        # Generate paper writeup (normal or ICBINB)
        writeup_success = False
        citations_text = gather_citations(
            base_folder=reports_base,
            num_cite_rounds=args.num_cite_rounds,
            small_model=args.model_citation,
            run_dir_name=run_dir_path.name if run_dir_path is not None else None,
        )
        try:
            for attempt in range(args.writeup_retries):
                print(f"Writeup attempt {attempt + 1} of {args.writeup_retries}")
                if args.writeup_type == "normal":
                    writeup_success = perform_writeup(
                        base_folder=reports_base,
                        big_model=args.model_writeup,
                        page_limit=8,
                        citations_text=citations_text,
                        run_dir_name=run_dir_path.name if run_dir_path is not None else None,
                    )
                else:
                    writeup_success = perform_icbinb_writeup(
                        base_folder=reports_base,
                        big_model=args.model_writeup,
                        page_limit=4,
                        citations_text=citations_text,
                        run_dir_name=run_dir_path.name if run_dir_path is not None else None,
                    )
                if writeup_success:
                    break
        except Exception as e:
            print(f"Writeup failed: {e}")
            traceback.print_exc()

        if not writeup_success:
            print("Writeup process did not complete successfully after all retries.")

    # Record tokens after writeup stage as well
    save_token_tracker(run_dir_path.as_posix() if run_dir_path is not None else reports_base)

    if not args.skip_review and not args.skip_writeup:
        # Perform paper review (if the generated PDF exists)
        pdf_path = find_pdf_path_for_review(
            reports_base, run_dir_path.name if run_dir_path is not None else None
        )
        if pdf_path and os.path.exists(pdf_path):
            print("Paper found at: ", pdf_path)
            paper_content = load_paper(pdf_path)
            client, client_model = create_client(args.model_review)
            # Build review context from the run outputs
            review_context = build_auto_review_context(reports_base, None, paper_content or "")
            # Performs paper review (text/main content)
            review_text = perform_review(
                paper_content,
                client_model,
                client,
                temperature=1.0,
                context=review_context,
                num_reviews_ensemble=3,
                num_reflections=2,
            )
            # Performs images/captions/reference review
            review_img_cap_ref = perform_imgs_cap_ref_review(client, client_model, pdf_path)
            review_out_dir = (
                osp.join(reports_base, "logs", run_dir_path.name)
                if run_dir_path is not None
                else reports_base
            )
            os.makedirs(review_out_dir, exist_ok=True)
            with open(osp.join(review_out_dir, "review_text.txt"), "w") as f:
                f.write(json.dumps(review_text, indent=4))
            with open(osp.join(review_out_dir, "review_img_cap_ref.json"), "w") as f:
                json.dump(review_img_cap_ref, f, indent=4)
            print("Paper review completed.")
        else:
            print("No PDF found for review (writeup likely failed). Skipping review.")

    # Clean up any lingering worker processes to avoid resource leaks
    print("Start cleaning up processes")
    # Kill all mp and torch processes associated with this experiment

    # Get the current process and all its children
    current_process = psutil.Process()
    children = current_process.children(recursive=True)

    # First try graceful termination (tolerant to already-exited processes)
    for child in children:
        try:
            if child.is_running():
                child.terminate()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue

    # Wait briefly for processes to terminate
    try:
        gone, alive = psutil.wait_procs(children, timeout=3)
    except Exception:
        # Be resilient to any unexpected psutil issues here
        gone, alive = [], [p for p in children if p.is_running()]

    # If any processes remain, force kill them
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue

    # Additional cleanup: find any orphaned processes containing specific keywords
    keywords = ["torch", "mp", "bfts", "experiment"]
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            # Check both process name and command line arguments
            cmdline = " ".join(proc.cmdline()).lower()
            if any(keyword in cmdline for keyword in keywords):
                try:
                    if proc.is_running():
                        proc.terminate()
                        proc.wait(timeout=3)
                except (
                    psutil.TimeoutExpired,
                    psutil.NoSuchProcess,
                    psutil.ZombieProcess,
                    psutil.AccessDenied,
                ):
                    # Try a hard kill if graceful termination failed or raced
                    try:
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
                        pass
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, psutil.Error):
            continue
    sys.exit(0)
