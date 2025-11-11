"""
End-to-end launcher for the BFTS experiment workflow.

Steps:
- Parse CLI args and load the selected idea (and optional code)
- Prepare an isolated experiment workspace
- Optionally merge dataset reference code with user-provided code
- Convert idea JSON to markdown and persist raw JSON
- Create a per-idea configuration for AgentManager (BFTS runner)
- Run experiments via AgentManager (draft/debug/improve/tune/plot/ablate)
- Collect artifacts and aggregate plots
- Optionally generate the paper writeup
- Optionally perform paper review (text and images/captions/reference)
- Clean up spawned worker processes
"""

import argparse
import json
import os
import os.path as osp
import re
import shutil
import signal
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psutil
import yaml

from ai_scientist.llm import create_client, token_tracker
from ai_scientist.perform_icbinb_writeup import gather_citations
from ai_scientist.perform_icbinb_writeup import perform_writeup as perform_icbinb_writeup
from ai_scientist.perform_llm_review import load_paper, perform_review
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_vlm_review import perform_imgs_cap_ref_review
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_context import build_auto_review_context
from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import (
    perform_experiments_bfts,
)


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
        default="icbinb",
        choices=["normal", "icbinb"],
        help="Type of writeup to generate (normal=8 page, icbinb=4 page)",
    )
    parser.add_argument(
        "--load_idea",
        type=str,
        help="Path to a JSON file containing the research idea",
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


def find_pdf_path_for_review(idea_dir: str) -> str | None:
    pdf_files = [f for f in os.listdir(idea_dir) if f.endswith(".pdf")]
    reflection_pdfs = [f for f in pdf_files if "reflection" in f]

    pdf_path = None  # Initialize to avoid UnboundLocalError

    if reflection_pdfs:
        # First check if there's a final version
        final_pdfs = [f for f in reflection_pdfs if "final" in f.lower()]
        if final_pdfs:
            # Use the final version if available
            pdf_path = osp.join(idea_dir, final_pdfs[0])
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
                pdf_path = osp.join(idea_dir, highest_reflection[1])
            else:
                # Fall back to the first reflection PDF if no numbers found
                pdf_path = osp.join(idea_dir, reflection_pdfs[0])
    elif pdf_files:
        # No reflection PDFs, use any PDF
        pdf_path = osp.join(idea_dir, pdf_files[0])

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

    # Determine the idea JSON from config and update it in place with dataset reference
    idea_json_path = str(Path(base_cfg["desc_file"]).resolve())
    with open(idea_json_path, "r") as f:
        idea = json.load(f)
        print(f"Loaded idea from {idea_json_path}")

    # Base folder (next to the idea JSON) to collect artifacts for plotting/writeup
    base_folder = str(Path(idea_json_path).parent.resolve())

    # Execute experiments via AgentManager (BFTS pipeline)
    perform_experiments_bfts(Path(base_config_path), lambda event: print(event.to_dict()))

    # Identify newly created run directory under configured log_dir
    run_dir_path: Path | None = None
    try:
        new_runs = [
            p for p in top_log_dir.iterdir() if p.is_dir() and p.name not in existing_runs_before
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
            aggregate_plots(base_folder=reports_base, model=args.model_agg_plots)
            agg_ok = True
        except Exception as e:
            print(f"Aggregate plots failed: {e}. Skipping writeup.")
            traceback.print_exc()

    # Remove the transient aggregated results folder (copied above)
    shutil.rmtree(osp.join(reports_base, "experiment_results"), ignore_errors=True)

    # Persist token accounting information
    save_token_tracker(reports_base)

    if not args.skip_writeup and should_run_reports and agg_ok:
        # Generate paper writeup (normal or ICBINB)
        writeup_success = False
        citations_text = gather_citations(
            reports_base,
            num_cite_rounds=args.num_cite_rounds,
            small_model=args.model_citation,
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
                    )
                else:
                    writeup_success = perform_icbinb_writeup(
                        base_folder=reports_base,
                        big_model=args.model_writeup,
                        page_limit=4,
                        citations_text=citations_text,
                    )
                if writeup_success:
                    break
        except Exception as e:
            print(f"Writeup failed: {e}")
            traceback.print_exc()

        if not writeup_success:
            print("Writeup process did not complete successfully after all retries.")

    # Record tokens after writeup stage as well
    save_token_tracker(reports_base)

    if not args.skip_review and not args.skip_writeup:
        # Perform paper review (if the generated PDF exists)
        pdf_path = find_pdf_path_for_review(reports_base)
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
            with open(osp.join(reports_base, "review_text.txt"), "w") as f:
                f.write(json.dumps(review_text, indent=4))
            with open(osp.join(reports_base, "review_img_cap_ref.json"), "w") as f:
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

    # First try graceful termination
    for child in children:
        try:
            child.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            traceback.print_exc()
            continue

    # Wait briefly for processes to terminate
    gone, alive = psutil.wait_procs(children, timeout=3)

    # If any processes remain, force kill them
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            traceback.print_exc()
            continue

    # Additional cleanup: find any orphaned processes containing specific keywords
    keywords = ["torch", "mp", "bfts", "experiment"]
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            # Check both process name and command line arguments
            cmdline = " ".join(proc.cmdline()).lower()
            if any(keyword in cmdline for keyword in keywords):
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=3)
                if proc.is_running():
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            traceback.print_exc()
            continue
    sys.exit(0)
