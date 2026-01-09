# Codex Migration (LLM/Interpreter → Codex CLI)

This document describes the migration of the AE-Scientist **treesearch execution pipeline** from an LLM-driven code-generation + local execution harness to a **Codex CLI-driven** agent that can:

- install dependencies
- download data
- write/edit code
- run experiments
- produce metrics + artifacts
- produce plotting + plot-analysis fields required by the UI
- (optionally) perform multi-seed aggregation as a separate Codex run

It also documents what the old code looked like, what was removed, what was added, and what the current system does end-to-end.

> **Scope**
>
> This doc focuses on `research_pipeline/ai_scientist/treesearch/*` (the experiment-search agent), plus the RunPod setup code paths that ensure Codex is present on remote machines.

---

## 1) What the system looked like before

### 1.1 High-level architecture (before)

The search loop was built around **two distinct responsibilities**:

- **LLM agent**: generate *plan + code* (and sometimes additional code like plotting)
- **Execution harness**: run code in a controlled environment and capture outputs

Concretely, the pipeline used:

- `research_pipeline/ai_scientist/treesearch/codegen_agent.py`
  - A `MinimalAgent` that built prompts (with datasets/GPU hints, etc.)
  - Called the LLM for plan/code and for follow-up iteration
  - Produced Python code strings and sometimes plot code strings

- `research_pipeline/ai_scientist/treesearch/interpreter.py`
  - An `Interpreter` that executed the generated code, enforced timeouts, and captured stdout/stderr

- `research_pipeline/ai_scientist/treesearch/worker_process.py`
  - Orchestrated agent ↔ interpreter runs
  - Parsed results and moved artifacts
  - Contained logic for plotting/vlm analysis hooks

### 1.2 Plotting + VLM analysis (before)

Plotting was **its own LLM-driven loop**:

- `research_pipeline/ai_scientist/treesearch/plotting.py`
  - `generate_plotting_code(...)` used an LLM to produce matplotlib code that reads `experiment_data.npy` and writes `.png` files to `./working/`
  - `analyze_plots_with_vlm(...)` ran a VLM analysis and populated:
    - `Node.plot_analyses`
    - `Node.vlm_feedback_summary`
    - `Node.vlm_feedback`
    - `Node.datasets_successfully_tested`
  - The pipeline also used `Node.is_buggy_plots` to gate plot quality and stage skipping

### 1.3 Multi-seed evaluation + aggregation (before)

Multi-seed evaluation had **two parts**:

1) **Per-seed executions**
   - `ParallelAgent._run_multi_seed_evaluation(...)` scheduled N runs of the same node with different seeds.
   - Seeds were typically injected into the Python code string for each run.

2) **Aggregation step**
   - `research_pipeline/ai_scientist/treesearch/multi_seed_evaluation.py`
   - It used an LLM to generate *aggregation plotting code* (e.g., mean ± SEM plots).
   - It executed that aggregation plotting code via `Interpreter`.
   - It created a special node:
     - `Node(is_seed_node=True, is_seed_agg_node=True)`
   - It moved aggregation plots into a dedicated `seed_aggregation_*` results directory.

### 1.4 Stage completion + skip gating (before)

Stages (Stage1–Stage4) contained **completion evaluation + skip gating** logic.

Notable examples from `origin/main`:

- Stage completion checks were often **LLM-based** using `StageCompletionEvaluation`.
- Skip gating included rules like:
  - “do not skip Stage 3 until plots exist”
  - “do not skip if best node is buggy/plot-buggy”

Stage control state was published to the UI via `research_pipeline/ai_scientist/treesearch/stage_control.py`.

---

## 2) What we changed (the migration)

### 2.1 The primary shift

We replaced the “LLM generates code, our harness runs it” model with:

> **Codex CLI owns generation + execution.**

In practical terms:

- Codex is invoked in **non-interactive automation mode**: `codex exec --full-auto --json ...`
- Codex can:
  - install packages (`pip`, `uv`, etc.)
  - download datasets
  - modify files
  - run the final experiment and iterate until it succeeds or time runs out

The local Python harness is responsible for:

- setting up an isolated workspace
- preparing the **inputs** for Codex
- invoking Codex
- validating Codex outputs (contracts)
- moving artifacts into the expected experiment results directories

### 2.2 Deleted / retired components

The following legacy modules were removed as first-class execution components:

- `research_pipeline/ai_scientist/treesearch/codegen_agent.py`
  - The prompt-building and plan/code generation responsibilities were moved into the Codex task file (`codex_task.md`) and input JSON (`codex_input.json`).

- `research_pipeline/ai_scientist/treesearch/interpreter.py`
  - The experiment code is not executed by our harness anymore; Codex executes it.

- `research_pipeline/ai_scientist/treesearch/plotting.py`
  - Plot generation and plot-analysis fields are now expected to be produced by Codex, and validated by the harness.

- `research_pipeline/ai_scientist/treesearch/multi_seed_evaluation.py`
  - Aggregation is reintroduced as a Codex task (see below), not as an LLM+Interpreter step.

### 2.3 New / rewritten components

#### `CodexCliRunner`

- File: `research_pipeline/ai_scientist/treesearch/codex_cli_runner.py`
- Purpose:
  - Run `codex exec --json` in a subprocess in a dedicated workspace
  - Stream JSONL events to:
    - `codex_events.jsonl`
    - `RunLogEvent` (high-signal)
  - Persist all output to `codex_session.log`
  - Enforce timeouts and support external termination via process-group kill

Key behavior:

- **Success file early-exit**: if `node_result.json` exists and parses as a JSON object, kill Codex and treat the run as successful.
- **Process group termination**: kill the whole process group to stop Codex and children.

#### Process termination utilities

- File: `research_pipeline/ai_scientist/treesearch/process_utils.py`
- Purpose:
  - `terminate_process_group(...)` and `send_signal_to_process_group(...)`
  - Logs warnings on failures rather than being silent best-effort.

#### Codex validation script

- File: `research_pipeline/scripts/validate_codex_cli.py`
- Purpose:
  - Minimal end-to-end proof that Codex can perform tasks non-interactively.
  - Uses the `research_pipeline/.venv` by constructing an env with:
    - `VIRTUAL_ENV`
    - `PATH` prefixed with `.venv/bin`
    - `PIP_REQUIRE_VIRTUALENV=1`
  - Streams:
    - stderr “progress” (optional)
    - stdout JSONL events (optional)

#### Worker refactor: “Codex-only execution”

- File: `research_pipeline/ai_scientist/treesearch/worker_process.py`
- Role:
  - Prepare workspace and working directory (`process_{id}/working`)
  - Create/reuse a per-workspace `.venv` for Codex (and enforce it via env variables)
  - Write:
    - `codex_input.json` (structured context)
    - `codex_task.md` (instructions)
  - Invoke Codex via `CodexCliRunner`
  - Load `node_result.json` and hydrate `Node`
  - Move artifacts (`*.npy`, `*.png`) out of `working/` into the run’s experiment results directory

#### Explicit node-result contract enforcement

The UI and downstream logic rely on fields that were previously produced by plotting/VLM code. In Codex-only mode we enforce that Codex writes the required fields.

We split contract logic into:

- Common pieces: `research_pipeline/ai_scientist/treesearch/node_result_contract.py`
  - `NodeResultContractContext`
  - Common required fields, strict type checks
  - Helper functions (plot analysis validation, etc.)

- Stage-specific rules: `research_pipeline/ai_scientist/treesearch/stages/*`
  - Each stage includes:
    - `codex_node_result_contract_prompt_lines()`
    - `validate_node_result_contract(...)` (stage-specific enforcement)

- Dispatcher: `research_pipeline/ai_scientist/treesearch/stages/node_result_contracts.py`
  - Routes validation based on stage, and also handles seed aggregation validation.

This is necessary because `Journal.good_nodes` selection depends on:

- `is_buggy is False`
- `is_buggy_plots is False`

So if Codex fails to write `is_buggy_plots=false`, the search loop can stall with no “good nodes”.

#### Seed aggregation as a Codex task (Option 3)

To restore the rolled-up seed view without reintroducing LLM+Interpreter aggregation, we add:

- File: `research_pipeline/ai_scientist/treesearch/seed_aggregation.py`
  - Contains explicit instructions for Codex when `codex_input.json.seed_aggregation` is present.
  - Contains additional contract requirements for an aggregation node:
    - `is_seed_node=true`
    - `is_seed_agg_node=true`
    - plot outputs + plot analysis outputs when `is_buggy_plots=false`

Wiring:

- `ParallelAgent._run_multi_seed_evaluation(...)` (file `research_pipeline/ai_scientist/treesearch/parallel_agent.py`)
  - Runs per-seed tasks as before.
  - Then schedules an additional Codex run with `seed_aggregation` payload populated.
  - Appends the resulting aggregation node to the journal.

Contract behavior:

- `NodeResultContractContext.is_seed_aggregation` is set based on whether `seed_aggregation` was provided.
- Non-aggregation runs require `is_seed_agg_node=false`.
- Aggregation runs require `is_seed_agg_node=true`.

#### Stage completion + skip gating restored

During migration, stage completion was simplified to “any good node completes the stage” and skip gating was removed. That broke behavior parity.

We restored the `origin/main` behavior in stage scripts:

- `research_pipeline/ai_scientist/treesearch/stages/stage1_baseline.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage2_tuning.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage3_plotting.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage4_ablation.py`

Restored behaviors include:

- LLM-based completion evaluation with caching (`StageCompletionEvaluation`)
- Skip gating, including “do not skip Stage 3 until plots exist”

`AgentManager` publishes skip state via `stage_control.publish_stage_state(...)` so the UI sees the gating status.

---

## 3) What the system does now (current end-to-end behavior)

### 3.1 The core contracts: inputs and outputs

#### Inputs to Codex (`codex_input.json`)

Written by the worker (`worker_process.py`) and includes:

- `research_idea` (task description)
- `evaluation_metric_spec` (run-wide metric schema)
- `memory_summary`
- `stage_identifier`
- `seed_eval` / `seed_value`
- `seed_aggregation` (optional; only for aggregation tasks)
- `environment_context`:
  - GPU specs and recommendations
  - storage capacity/free space
  - dataset inventory:
    - HF cache listing
    - local dataset directory listing
    - S3 listing (bounded for prompt size)
    - S3 download/upload snippets

#### Outputs from Codex

Codex must write:

- `node_result.json`: a dict matching `Node.to_dict` schema (with enforced required fields)
- `runfile.py` (or configured agent file name): the final experiment script
- artifacts in `./working/`:
  - `experiment_data.npy`
  - `.png` plots (for relevant stages/tasks)

The harness then:

- moves artifacts to `logs/<run_name>/experiment_results/experiment_<node_id>_proc_<pid>/`
- populates `Node.plots` and `Node.plot_paths` based on moved `.png` files

### 3.2 Codex execution: generation + execution

Codex is responsible for **both**:

- generating code
- running it and iterating until success

We run Codex with:

- `codex exec --full-auto --sandbox danger-full-access --skip-git-repo-check --json`

The harness does not execute the experiment code itself; it only runs Codex.

### 3.3 Deterministic seeding

For multi-seed eval tasks:

- the harness passes `seed_eval=true` and `seed_value=<seed>`
- Codex is instructed to set deterministic seeds in the final experiment code:
  - `random.seed(seed_value)`
  - `numpy.random.seed(seed_value)`
  - torch seeding when applicable

The harness also enforces that the plan text mentions the seed value when `seed_eval=true`.

### 3.4 Multi-seed evaluation (current)

Multi-seed evaluation now has three conceptual steps:

1) **Per-seed runs**
   - `ParallelAgent._run_multi_seed_evaluation(...)` schedules N worker tasks with:
     - `seed_eval=true`
     - `seed_value=<seed>`
     - `seed_aggregation=None`

2) **Codex seed aggregation run (rolled-up node)**
   - If at least 2 seed runs were produced, the agent schedules an additional worker task where:
     - `seed_eval=false`
     - `seed_aggregation` is populated with metadata about the seed runs (IDs, exp_results_dir, plots, metric, etc.)
   - This causes:
     - the worker to include **seed aggregation instructions** into `codex_task.md`
     - the contract validator to require `is_seed_agg_node=true`
   - Codex should:
     - load the seed runs’ artifacts (e.g., `experiment_data.npy`)
     - compute aggregate statistics (mean/std/sem)
     - write roll-up plots to `./working/`
     - emit an aggregated metric

3) **Artifact collection**
   - The worker moves `.png` and `.npy` files out of `./working` as usual.

### 3.5 Plotting + plot-analysis fields (current)

The current pipeline does not run a separate internal plotting+VLM analysis module.

Instead:

- Codex is expected to:
  - generate plots when the stage/task requires it (write `.png` into `./working/`)
  - populate plot-analysis fields in `node_result.json`:
    - `plot_analyses` (list of dicts; each includes at least `analysis`)
    - `vlm_feedback_summary` (list of strings)
    - `vlm_feedback` (dict)
    - `datasets_successfully_tested` (list of strings)
    - `is_buggy_plots` (bool)

The harness enforces these fields (strict types) and will mark the node buggy if missing.

### 3.6 Stage completion + skip gating (current)

Stage completion and skip gating are implemented in:

- `research_pipeline/ai_scientist/treesearch/stages/stage1_baseline.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage2_tuning.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage3_plotting.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage4_ablation.py`

Behavior:

- Completion evaluation uses LLM-based `StageCompletionEvaluation` where it previously existed (with caching).
- Skip gating is restored, including the “Stage 3 requires plot artifacts” rule.
- `AgentManager` publishes the skip window state through `stage_control.publish_stage_state(...)`.

---

## 4) Repository / environment integration

### 4.1 RunPod server-launched installs

When the server launches a RunPod job (`server/app/services/research_pipeline/runpod_manager.py`), the generated remote startup script now includes:

- an explicit “Codex CLI Installation” section
- idempotent behavior:
  - if `codex` is missing:
    - ensure `nodejs` + `npm` are present
    - `npm install -g @openai/codex`
  - print `codex --version`

This ensures Codex is available for the pipeline run.

### 4.2 Manual RunPod setup helper

`configure_pod.sh` contains an explicit Codex install block as part of its “install_run_pod.sh” section:

- installs `nodejs` + `npm` if necessary
- installs `@openai/codex`
- prints `codex --version`

---

## 5) Files added / modified (migration map)

### 5.1 Added

- `research_pipeline/ai_scientist/treesearch/codex_cli_runner.py`
- `research_pipeline/ai_scientist/treesearch/process_utils.py`
- `research_pipeline/scripts/validate_codex_cli.py`
- `research_pipeline/ai_scientist/treesearch/node_result_contract.py`
- `research_pipeline/ai_scientist/treesearch/stages/node_result_contracts.py`
- `research_pipeline/ai_scientist/treesearch/seed_aggregation.py`
- `research_pipeline/bfts_config_no_gpu.yaml`
- `codex_migration.md` (this file)

### 5.2 Modified (core)

- `research_pipeline/ai_scientist/treesearch/worker_process.py`
  - rewired to Codex-only execution
  - writes `codex_input.json` and `codex_task.md`
  - enforces node-result contracts
  - handles seed aggregation tasks

- `research_pipeline/ai_scientist/treesearch/parallel_agent.py`
  - uses Codex worker tasks instead of `MinimalAgent`/`Interpreter`
  - multi-seed eval schedules per-seed runs and then schedules Codex seed aggregation

- `research_pipeline/ai_scientist/treesearch/stages/stage1_baseline.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage2_tuning.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage3_plotting.py`
- `research_pipeline/ai_scientist/treesearch/stages/stage4_ablation.py`
  - restored origin/main completion evaluation and skip gating

- `server/app/services/research_pipeline/runpod_manager.py`
  - ensures `codex` is installed on remote pods

### 5.3 Deleted / no longer used as active execution paths

- `research_pipeline/ai_scientist/treesearch/codegen_agent.py`
- `research_pipeline/ai_scientist/treesearch/interpreter.py`
- `research_pipeline/ai_scientist/treesearch/plotting.py`
- `research_pipeline/ai_scientist/treesearch/multi_seed_evaluation.py`

---

## 6) Operational notes / debugging

### 6.1 Where to look when something fails

Each worker workspace directory includes:

- `codex_task.md`: what we told Codex to do
- `codex_input.json`: structured context
- `codex_session.log`: combined stdout/stderr bytes captured from Codex
- `codex_events.jsonl`: JSONL event stream from `codex exec --json`
- `node_result.json`: the required output (when successful)

### 6.2 Contract failures

If Codex writes an invalid or incomplete `node_result.json`, the worker marks the node buggy and sets `analysis` to:

- a list of contract violations (missing/incorrect fields)

This is intentionally strict because downstream stage gating and UI assume these fields exist with correct types.

### 6.3 Validating Codex independently

Use:

```bash
cd research_pipeline
python scripts/validate_codex_cli.py --timeout 60
```

This validates:

- Codex CLI is runnable
- Codex can create proof files
- JSONL streaming is functioning
- the run respects the `research_pipeline/.venv`

---

## 7) Summary: what the migration achieves

Before:

- The system relied on an LLM to generate code and a local harness to execute it.
- Plotting and seed aggregation were LLM + Interpreter tasks.

Now:

- Codex CLI is the single automation engine for generation + execution.
- Inputs/outputs are file-based (`codex_input.json`, `node_result.json`, artifacts in `working/`).
- The harness enforces strict output contracts for UI/state correctness.
- Multi-seed aggregation is a dedicated Codex task that produces an aggregation node.

---

## 8) Detailed data contracts

This section documents the data contracts that replaced implicit in-process objects.

### 8.1 `codex_input.json` (worker → Codex)

The worker writes `codex_input.json` in the workspace directory (e.g., `workspaces/<run>/process_<id>/codex_input.json`).

At a high level it contains:

- **Run identity**
  - `execution_id`: unique id for the worker run

- **Task**
  - `research_idea`: full task description string (including “Code To Use” when provided)
  - `memory_summary`: optional prior-run notes
  - `stage_identifier`: enum name such as `STAGE1`, `STAGE2`, etc.

- **Metric definition**
  - `evaluation_metric_spec`: object defined before code generation

- **Seed controls**
  - `seed_eval`: boolean
  - `seed_value`: integer

- **Seed aggregation (only for aggregation runs)**
  - `seed_aggregation`: object or `null`
  - Contents include metadata about seed runs (IDs, exp_results_dir, metrics, plot paths, etc.)

- **Execution environment**
  - `agent_file_name`: final experiment file name (defaults from config)
  - `timeout_seconds`: wall clock timeout for Codex run
  - `gpu_id`: integer or null
  - `environment_context`: structured data:
    - `gpu`: id/spec, recommended device hints
    - `storage`: workspace disk capacity/free space
    - `datasets`: HF cache lines, local dataset lines, S3 listing, S3 helper snippets

### 8.2 `codex_task.md` (worker → Codex)

The worker writes `codex_task.md` containing:

- **Legacy prompt parity block**
  - Stage-specific introductions
  - Dataset context and S3 snippets
  - Metric definition
  - Implementation guidelines and plotting guidelines

- **Strict Node result contract block**
  - Required keys, required types
  - Stage-specific additional constraints
  - Seed constraints when `seed_eval=true`
  - For seed aggregation runs (`seed_aggregation` present): extra instructions and contract requirements

### 8.3 `node_result.json` (Codex → worker)

Codex must write a JSON object compatible with `Node.from_dict(...)` / `Node.to_dict(...)`.

The harness enforces strict types for fields that the UI and gating logic rely on, including:

- `is_buggy_plots`: boolean (never null)
- `plot_analyses`: list (can be empty, but must be present)
- `vlm_feedback_summary`: list of strings (can be empty, but must be present)
- `vlm_feedback`: dict/object (can be empty `{}`, but must be present)
- `datasets_successfully_tested`: list of strings (can be empty, but must be present)

Seed-related fields:

- For per-seed runs: `is_seed_node=true`
- For seed aggregation runs:
  - `is_seed_node=true`
  - `is_seed_agg_node=true`
  - `analysis` must be a non-empty summary of cross-seed variability/stability

---

## 9) Multi-seed aggregation: how to think about it now

The system supports two different “seed semantics”:

### 9.1 Per-seed runs

Per-seed runs represent the same experimental code executed with different deterministic seeds:

- `seed_eval=true`
- `seed_value=<seed>`
- `is_seed_node=true`
- `is_seed_agg_node=false`

### 9.2 Aggregation run

Aggregation is a **separate Codex run** that consumes the per-seed outputs:

- `seed_aggregation` is present in `codex_input.json`
- contract requires:
  - `is_seed_agg_node=true`
  - aggregate plots written into `./working/`

This aggregation run exists so that the UI can show:

- a single rolled-up node
- aggregate metric value
- aggregate plots (mean curves / error bars / combined summaries)

---

## 10) Stage policy: completion vs skipping

Stages implement two separate responsibilities:

1) **Completion evaluation**
   - Determines whether a stage/substage should continue iterating.
2) **Skip gating**
   - Determines whether the operator UI is allowed to skip the stage.

These are defined per-stage under `research_pipeline/ai_scientist/treesearch/stages/`.

Notable restored gating:

- **Stage 3 skip gating requires plot artifacts**
  - if best node has no plots/plot_paths, the stage cannot be skipped

---

## 11) Timeouts, termination, and observability

### 11.1 Timeouts

Codex runs are wall-clock bounded:

- `CodexCliRunner` tracks elapsed time and kills the process group when time exceeds `timeout_seconds`.

### 11.2 Early exit on success file

To avoid Codex staying alive after producing outputs, the runner uses a success-file early-exit:

- if `node_result.json` exists and parses as a JSON object:
  - terminate Codex process group and return

### 11.3 Streaming events (visibility into what Codex is doing)

Because `codex exec --json` produces a JSON Lines stream, the runner:

- writes all events to `codex_events.jsonl`
- emits a subset of high-signal events as `RunLogEvent`:
  - agent messages
  - command executions
  - turn started/completed/failed
  - errors

This produces live visibility without coupling the pipeline to any interactive UI.

---

## 12) UI/export impact

The UI and export tooling read from fields serialized by `Node.to_dict()` and from `tree_export.py` (and the embedded viz template).

As a result:

- Plot analysis fields are required for the “plot/VLM insights” panes to show content.
- `is_buggy_plots` participates in good-node selection and therefore affects:
  - stage completion
  - skip gating
  - best-node selection eligibility

This is why the contract is strict and enforced at the worker boundary.
