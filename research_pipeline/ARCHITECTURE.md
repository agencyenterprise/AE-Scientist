## Architecture

This document describes the runtime architecture of the AI Scientist BFTS experiment system.

### Overview

- The system orchestrates research experiments as a staged tree search (Breadth-First Tree Search).
- Each main stage consists of substages (iterations). Stages are: baseline, tuning, plotting, ablation.
- Work is executed in parallel worker processes with optional GPU assignment.
- LLM/VLM calls are centralized in the `ai_scientist.llm` package.

### Key Modules

- `launch_scientist_bfts.py`
  - CLI entrypoint to run an idea end-to-end.
  - Prepares experiment workspace, edits run config, calls the experiment runner, aggregates plots, persists token tracking, optionally generates writeups and performs review.

- `ai_scientist/treesearch/perform_experiments_bfts_with_agentmanager.py`
  - Runs the experiment using `AgentManager` with a terminal UI.
  - Renders task description, live progress, tree view, and emits structured events for external listeners.

- `ai_scientist/treesearch/agent_manager.py`
  - Orchestrates the staged lifecycle of the experiment.
  - Manages `StageMeta` (metadata) and uses concrete stage classes to evaluate completion and generate goals.
  - Creates a `ParallelAgent` for each substage, runs iterations, persists journals, saves checkpoints, and transitions stages.

- `ai_scientist/treesearch/parallel_agent.py`
  - Executes breadth-first iterations in parallel using `ProcessPoolExecutor` (spawn).
  - Selects nodes (draft/debug/improve) with balanced exploration/exploitation.
  - Submits work to `worker_process.process_node`, collects results, emits progress/log events.
  - Supports multi-seed evaluation.

### Manager–Agent Roles (AgentManager, ParallelAgent, MinimalAgent)

- AgentManager (orchestrator)
  - Instantiation: Created by the experiment runner with `task_desc`, `cfg`, `workspace_dir`, and an `event_callback`.
  - Responsibilities:
    - Owns the staged lifecycle via `StageMeta` and concrete stage classes.
    - Creates/owns a `Journal` per stage and maintains `stage_history` and checkpoints.
    - For each substage, instantiates a short‑lived `ParallelAgent` and calls `agent.step(...)` until completion.
    - Decides when substages and main stages complete (delegates logic to stage classes), then advances to the next stage.
  - Ownership: Long‑lived per run. Holds configuration, journals, and progress state.

- ParallelAgent (parallel executor for one substage)
  - Instantiation: Constructed by `AgentManager` for a specific substage with `task_desc`, `cfg`, the current `Journal`, stage name/slug, carry‑over best nodes, and the `event_callback`.
  - Responsibilities:
    - Manages a `ProcessPoolExecutor` (spawn) and optional `GPUManager` assignment per worker.
    - Selects which nodes to process next (draft/debug/improve/seed eval) and submits work to workers.
    - Collects worker results, reconstructs `Node`s into the substage `Journal`, updates stage state (e.g., tried hyperparams, completed ablations), and emits structured events.
  - Ownership: Short‑lived; exists only for the active substage. Does not persist across substages.

- MinimalAgent (per‑worker, node‑level codegen/analysis)
  - Instantiation: Constructed inside each worker process by `worker_process.process_node` using the `task_desc` and `cfg` passed down by `ParallelAgent`.
  - Responsibilities:
    - Builds prompts and calls the LLM (via `ai_scientist.llm.query`) to: draft/improve/debug code, parse execution outputs, and summarize nodes.
    - Delegates stage‑specific operations to static methods on stage classes (e.g., `Stage1Baseline.draft`, `Stage2Tuning.build_hyperparam_tuning_node`, `Stage3Plotting.generate_plotting_code`).
    - Does not manage multiprocessing, GPUs, or journals.
  - Ownership: Ephemeral; a fresh instance per worker task execution.

- Interaction flow (who creates whom)
  1. The runner creates `AgentManager`.
  2. For each substage, `AgentManager` creates `ParallelAgent` and calls `agent.step(...)`.
  3. `ParallelAgent` submits `worker_process.process_node(...)` jobs to the pool.
  4. Each worker creates a `MinimalAgent`, generates/executes code, analyzes results, and returns a serialized `Node`.
  5. `ParallelAgent` restores `Node`s into the `Journal`, emits events, and determines next actions.
  6. `AgentManager` evaluates substage/stage completion and transitions accordingly.

- `ai_scientist/treesearch/stages/*`
  - Stage classes: `Stage1Baseline`, `Stage2Tuning`, `Stage3Plotting`, `Stage4Ablation`.
  - Provide stage defaults (`MAIN_STAGE_SLUG`, `DEFAULT_GOALS`) and static methods for stage-specific operations:
    - Idea generation (e.g., tuning/ablation proposals)
    - Node builders for stage-specific code generation
    - Plotting code generation and VLM analysis
    - Stage/substage completion evaluation

- `ai_scientist/treesearch/stages/base.py`
  - `StageMeta`: metadata for a stage/substage (name, number, slug, substage numbering and name, goals, iteration limits, drafts).
  - `StageContext`: run context for a stage (config, task description, current journal, workspace, event callback, carryover nodes).
  - `Stage`: base class API implemented by concrete stages.

- `ai_scientist/treesearch/worker_process.py`
  - Worker entrypoint running generated code in an interpreter sandbox.
  - Uses `MinimalAgent` to generate plotting code, executes it, collects plots, performs VLM analysis, and returns serialized node results.

- `ai_scientist/llm/*` and `ai_scientist/llm/query/*`
  - Centralized LLM/VLM clients, wrappers, and backend query logic.
  - Stage and manager modules call LLM/VLM through these helpers only.

### Execution Flow

1. Launch script loads the idea, prepares workspace and per-run config, then calls the experiment runner.
2. The runner builds an `AgentManager`, renders a minimal UI, and calls `manager.run()`.
3. `AgentManager` initializes the first `StageMeta` (baseline) and sets up the initial journal.
4. For each substage:
   - Curates the task description based on stage type.
   - Creates a `ParallelAgent` with carryover best nodes from prior completed stages.
   - Delegates completion checks to the concrete `Stage` implementation.
5. When a main stage completes:
   - Optionally runs multi-seed evaluation and plot aggregation for the best node.
   - Transitions to the next main stage by constructing a new `StageMeta`.
6. Journals and checkpoints are saved throughout to the run directory under `logs/`.

### Parallel Execution

- `ParallelAgent` manages a `ProcessPoolExecutor` with spawn context to ensure safe multiprocessing.
- Optional GPUs are assigned per worker via `GPUManager`.
- Node selection balances:
  - Drafting new roots until the desired number of drafts is reached
  - Debugging buggy leaves (probabilistic)
  - Improving best-performing nodes
  - Stage-specific seeding (tuning uses baseline best; ablation uses stage-3 best)

### Stage System

- Stage configuration is carried by `StageMeta`:
  - `name`, `number`, `slug`, `substage_number`, `substage_name`, `goals`, `max_iterations`, `num_drafts`.
- Stage behavior is implemented by concrete classes under `stages/` and accessed via static methods for:
  - Generating ideas and nodes
  - Evaluating completion (substage and main stage)
  - Plot generation and VLM-based feedback
  - Updating per-stage state (e.g., tried hyperparameters, completed ablations)

### LLM Abstraction

- All LLM/VLM calls are routed through `ai_scientist.llm` helpers and `ai_scientist.llm.query` backends.
- This isolates provider-specific details from stage/agent logic.

### Configuration

- The top-level config (`cfg`) controls:
  - Agent models/temperatures, parallelism, executor timeouts
  - Stage iteration limits and number of drafts
  - Workspace, logging, and report generation options

### Artifacts & Logging

- Journals, node summaries, and plot analyses are stored under `logs/<run>/stage_*`.
- Best solutions and aggregated plots are exported to the experiment root for quick inspection.
- Structured events (`ai.run.*`, `ai.experiment.*`) enable external UIs and logs to follow progress.


