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
- Persist token usage and copy best solution scripts to the root
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
from datetime import datetime
from pathlib import Path
from typing import Generator

import psutil
import torch

from ai_scientist.llm import create_client, token_tracker
from ai_scientist.perform_icbinb_writeup import gather_citations
from ai_scientist.perform_icbinb_writeup import perform_writeup as perform_icbinb_writeup
from ai_scientist.perform_llm_review import load_paper, perform_review
from ai_scientist.perform_plotting import aggregate_plots
from ai_scientist.perform_vlm_review import perform_imgs_cap_ref_review
from ai_scientist.perform_writeup import perform_writeup
from ai_scientist.review_context import build_auto_review_context
from ai_scientist.treesearch.bfts_utils import edit_bfts_config_file, idea_to_markdown
from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import (
    perform_experiments_bfts,
)


def print_time() -> None:
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def save_token_tracker(idea_dir: str) -> None:
    with open(osp.join(idea_dir, "token_tracker.json"), "w") as f:
        json.dump(token_tracker.get_summary(), f)
    with open(osp.join(idea_dir, "token_tracker_interactions.json"), "w") as f:
        json.dump(token_tracker.get_interactions(), f)


def copy_best_solutions_to_root(idea_dir: str) -> None:
    """
    Copy the best solution code from each stage to the experiment root directory
    for easy access and reproducibility.
    """
    try:
        idea_path = Path(idea_dir)
        logs_dir = idea_path / "logs" / "0-run"

        if not logs_dir.exists():
            print("⚠️ No logs directory found, skipping best solution copy")
            return

        stage_info = []
        best_solutions_copied = 0

        # Find all stage directories
        stage_dirs = sorted(
            [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("stage_")]
        )

        for stage_dir in stage_dirs:
            # Look for best_solution files
            best_solution_files = list(stage_dir.glob("best_solution_*.py"))
            best_node_id_file = stage_dir / "best_node_id.txt"

            if best_solution_files:
                # Get stage name and number
                stage_name = stage_dir.name

                # Read node ID if available
                node_id = "unknown"
                if best_node_id_file.exists():
                    with open(best_node_id_file, "r") as f:
                        node_id = f.read().strip()

                # Copy the best solution file
                source_file = best_solution_files[0]

                # Create a clean filename based on stage
                # Extract stage number (e.g., stage_3_creative_research_1_first_attempt -> 3)
                stage_num = stage_name.split("_")[1]
                dest_filename = f"best_code_stage_{stage_num}.py"
                dest_path = idea_path / dest_filename

                # Copy the file
                shutil.copy2(source_file, dest_path)
                print(f"✓ Copied {dest_filename} (node: {node_id[:8]}...)")

                best_solutions_copied += 1

                # Store info for README
                stage_info.append(
                    {
                        "stage_num": stage_num,
                        "stage_name": stage_name,
                        "filename": dest_filename,
                        "node_id": node_id,
                        "original_path": str(source_file.relative_to(idea_path)),
                    }
                )

        # Create a README explaining the best solutions
        if stage_info:
            readme_path = idea_path / "BEST_SOLUTIONS_README.md"
            with open(readme_path, "w") as f:
                f.write("# Best Solution Code for Reproducibility\n\n")
                f.write(
                    "This directory contains the best performing code from each experimental stage.\n"
                )
                f.write("Use these files to reproduce the results reported in the paper.\n\n")

                f.write("## Files\n\n")

                stage_descriptions = {
                    "1": "Initial Implementation - First working version of the idea",
                    "2": "Baseline Tuning - Hyperparameter-tuned baseline",
                    "3": "Creative Research - **Main results used in paper**",
                    "4": "Ablation Studies - Variations for comparison",
                }

                for info in sorted(stage_info, key=lambda x: int(x["stage_num"])):
                    desc = stage_descriptions.get(info["stage_num"], "Experimental stage")
                    f.write(f"### `{info['filename']}`\n\n")
                    f.write(f"- **Stage**: {desc}\n")
                    f.write(f"- **Node ID**: `{info['node_id']}`\n")
                    f.write(f"- **Original location**: `{info['original_path']}`\n")
                    f.write(f"- **Stage directory**: `{info['stage_name']}`\n\n")

                f.write("## How to Use\n\n")
                f.write("For reproducing the main paper results, use **`best_code_stage_3.py`** ")
                f.write("(Creative Research stage).\n\n")
                f.write("```bash\n")
                f.write("# Run the best code\n")
                f.write("python best_code_stage_3.py\n")
                f.write("```\n\n")

                f.write("## Selection Process\n\n")
                f.write("The best code for each stage was selected using:\n")
                f.write("- Performance metrics (validation loss, accuracy, etc.)\n")
                f.write("- Training dynamics\n")
                f.write("- Plot quality and experimental evidence\n")
                f.write("- LLM-based evaluation (GPT-5-mini) considering all factors\n\n")

                f.write("See `logs/0-run/<stage_name>/journal.json` for the complete ")
                f.write("experimental history and selection reasoning.\n")

            print("✓ Created BEST_SOLUTIONS_README.md")

        print(f"✓ Copied {best_solutions_copied} best solution file(s) to experiment root")

    except Exception as e:
        print(f"⚠️ Error copying best solutions: {e}")

        traceback.print_exc()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI scientist experiments")
    parser.add_argument(
        "--writeup-type",
        type=str,
        default="icbinb",
        choices=["normal", "icbinb"],
        help="Type of writeup to generate (normal=8 page, icbinb=4 page)",
    )
    parser.add_argument(
        "--load_ideas",
        type=str,
        help="Path to a JSON file containing pregenerated ideas",
    )
    parser.add_argument(
        "--load_code",
        action="store_true",
        help="If set, load a Python file with same name as ideas file but .py extension",
    )
    parser.add_argument(
        "--idea_idx",
        type=int,
        default=0,
        help="Index of the idea to run",
    )
    parser.add_argument(
        "--add_dataset_ref",
        action="store_true",
        help="If set, add a HF dataset reference to the idea",
    )
    parser.add_argument(
        "--writeup-retries",
        type=int,
        default=3,
        help="Number of writeup attempts to try",
    )
    parser.add_argument(
        "--attempt_id",
        type=int,
        default=0,
        help="Attempt ID, used to distinguish same idea in different attempts in parallel runs",
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


def get_available_gpus(gpu_ids: str | None = None) -> list[int]:
    if gpu_ids is not None:
        return [int(gpu_id) for gpu_id in gpu_ids.split(",")]
    return list(range(torch.cuda.device_count()))


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
    os.environ["AI_SCIENTIST_ROOT"] = os.path.dirname(os.path.abspath(__file__))
    print(f"Set AI_SCIENTIST_ROOT to {os.environ['AI_SCIENTIST_ROOT']}")

    # Determine available GPUs (for parallel experiments)
    available_gpus = get_available_gpus()
    print(f"Using GPUs: {available_gpus}")

    # Load pregenerated ideas and select one
    with open(args.load_ideas, "r") as f:
        ideas = json.load(f)
        print(f"Loaded {len(ideas)} pregenerated ideas from {args.load_ideas}")

    idea = ideas[args.idea_idx]

    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    idea_dir = f"experiments/{date}_{idea['Name']}_attempt_{args.attempt_id}"
    print(f"Results will be saved in {idea_dir}")
    os.makedirs(idea_dir, exist_ok=True)

    # Convert idea JSON to markdown (for readability)
    idea_path_md = osp.join(idea_dir, "idea.md")

    # Optionally load a Python module with same name as the JSON idea
    code = None
    if args.load_code:
        code_path = args.load_ideas.rsplit(".", 1)[0] + ".py"
        if os.path.exists(code_path):
            with open(code_path, "r") as f:
                code = f.read()
        else:
            print(f"Warning: Code file {code_path} not found")
    else:
        code_path = None

    idea_to_markdown(ideas[args.idea_idx], idea_path_md, code_path)

    # Optionally merge a dataset reference snippet into the idea/code
    dataset_ref_code = None
    if args.add_dataset_ref:
        dataset_ref_path = "hf_dataset_reference.py"
        if os.path.exists(dataset_ref_path):
            with open(dataset_ref_path, "r") as f:
                dataset_ref_code = f.read()
        else:
            print(f"Warning: Dataset reference file {dataset_ref_path} not found")
            dataset_ref_code = None

    if dataset_ref_code is not None and code is not None:
        added_code: str | None = dataset_ref_code + "\n" + code
    elif dataset_ref_code is not None and code is None:
        added_code = dataset_ref_code
    elif dataset_ref_code is None and code is not None:
        added_code = code
    else:
        added_code = None

    print(added_code)

    # Attach merged code to the idea JSON (if present)
    if added_code is not None:
        ideas[args.idea_idx]["Code"] = added_code

    # Persist the raw idea JSON to disk
    idea_path_json = osp.join(idea_dir, "idea.json")
    with open(idea_path_json, "w") as f:
        json.dump(ideas[args.idea_idx], f, indent=4)

    # Prepare per-idea configuration for AgentManager
    config_path = "bfts_config.yaml"
    idea_config_path = edit_bfts_config_file(
        config_path,
        idea_dir,
        idea_path_json,
    )

    # Execute experiments via AgentManager (BFTS pipeline)
    perform_experiments_bfts(Path(idea_config_path), lambda event: print(event.to_dict()))
    # Collect and relocate experiment results for convenience
    experiment_results_dir = osp.join(idea_dir, "logs/0-run/experiment_results")
    if os.path.exists(experiment_results_dir):
        shutil.copytree(
            experiment_results_dir,
            osp.join(idea_dir, "experiment_results"),
            dirs_exist_ok=True,
        )

    # Aggregate plots across runs
    aggregate_plots(base_folder=idea_dir, model=args.model_agg_plots)

    # Remove the transient aggregated results folder (copied above)
    shutil.rmtree(osp.join(idea_dir, "experiment_results"))

    # Persist token accounting information
    save_token_tracker(idea_dir)

    # Copy best solutions to experiment root for easy access
    # Copy best solution scripts to the experiment root
    print("\n📋 Copying best solutions to experiment root...")
    copy_best_solutions_to_root(idea_dir)

    if not args.skip_writeup:
        # Generate paper writeup (normal or ICBINB)
        writeup_success = False
        citations_text = gather_citations(
            idea_dir,
            num_cite_rounds=args.num_cite_rounds,
            small_model=args.model_citation,
        )
        for attempt in range(args.writeup_retries):
            print(f"Writeup attempt {attempt + 1} of {args.writeup_retries}")
            if args.writeup_type == "normal":
                writeup_success = perform_writeup(
                    base_folder=idea_dir,
                    big_model=args.model_writeup,
                    page_limit=8,
                    citations_text=citations_text,
                )
            else:
                writeup_success = perform_icbinb_writeup(
                    base_folder=idea_dir,
                    big_model=args.model_writeup,
                    page_limit=4,
                    citations_text=citations_text,
                )
            if writeup_success:
                break

        if not writeup_success:
            print("Writeup process did not complete successfully after all retries.")

    # Record tokens after writeup stage as well
    save_token_tracker(idea_dir)

    if not args.skip_review and not args.skip_writeup:
        # Perform paper review (if the generated PDF exists)
        pdf_path = find_pdf_path_for_review(idea_dir)
        if pdf_path and os.path.exists(pdf_path):
            print("Paper found at: ", pdf_path)
            paper_content = load_paper(pdf_path)
            client, client_model = create_client(args.model_review)
            # Build review context from the run outputs
            review_context = build_auto_review_context(idea_dir, None, paper_content or "")
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
            with open(osp.join(idea_dir, "review_text.txt"), "w") as f:
                f.write(json.dumps(review_text, indent=4))
            with open(osp.join(idea_dir, "review_img_cap_ref.json"), "w") as f:
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
            continue

    # Wait briefly for processes to terminate
    gone, alive = psutil.wait_procs(children, timeout=3)

    # If any processes remain, force kill them
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Additional cleanup: find any orphaned processes containing specific keywords
    keywords = ["python", "torch", "mp", "bfts", "experiment"]
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
            continue

    # Finally, terminate the current process
    # current_process.send_signal(signal.SIGTERM)
    # try:
    #     current_process.wait(timeout=3)
    # except psutil.TimeoutExpired:
    #     current_process.kill()

    # exit the program
    sys.exit(0)
