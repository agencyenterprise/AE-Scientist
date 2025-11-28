# AE-Scientist - Research Pipeline

Automated AI scientist for running multi-stage experiments and generating research papers.

## Overview

The research pipeline implements a Best-First Tree Search (BFTS) approach to automated scientific experimentation:
- Generates and evaluates experimental implementations
- Runs multi-seed evaluations for statistical significance
- Performs ablation studies to validate contributions
- Aggregates results and generates LaTeX papers with citations
- Supports both local and GPU-accelerated (RunPod) execution

## Setup (Local)

From the repository root:

```bash
# Install dependencies
cd research_pipeline
uv sync --extra gpu

# Activate the virtual environment
source .venv/bin/activate
```

Or use the Makefile from the root directory:

```bash
make install-research
```

## Setup (RunPod)

For GPU-accelerated experiments on RunPod:

1. **Create a new virtual environment with access to system-wide packages**
```bash
uv venv --system-site-packages
```

RunPod provides images with PyTorch and other GPU-related packages. Some of these packages may conflict with the packages listed in pyproject.toml. To use the pre-installed packages, create a virtual environment with access to system-wide packages.

2. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   cd research_pipeline
   uv sync
   ```

4. **Install LaTeX packages** (required for paper generation):
   ```bash
   apt-get update && apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-bibtex-extra biber poppler-utils chktex
   ```

### Quick Setup Script

Alternatively, use the provided setup script from the repository root:

```bash
bash install_run_pod.sh
```

This script:
- Creates a virtual environment with system packages
- Activates it
- Installs dependencies
- Installs LaTeX packages

## Environment Variables

Configure API keys and tokens before running experiments.

1. **Copy the example environment file**:
   ```bash
   cd research_pipeline
   cp .env.example .env
   ```

2. **Edit `.env`** and add your API keys:

### Required Variables

```bash
# OpenAI API key (required for LLM queries)
OPENAI_API_KEY=sk-your-openai-key

# HuggingFace token (required for downloading datasets and models)
# Get your token from: https://huggingface.co/settings/tokens
HUGGINGFACE_HUB_TOKEN=hf_your_token
HUGGINGFACE_API_KEY=hf_your_token
HF_TOKEN=hf_your_token
```

**Note:** The three HuggingFace variables should all have the same value - they're used by different libraries.

### Optional Variables

```bash
# Custom OpenAI-compatible endpoint (e.g., local LLM server, RunPod)
# Only set this if NOT using the default OpenAI API
OPENAI_BASE_URL="https://your-custom-endpoint.com/v1"

# Anthropic API key - only required if using Claude models
# (e.g., when using bfts_config_claude-haiku.yaml)
ANTHROPIC_API_KEY=your-anthropic-key
```

**Important:**
- `OPENAI_BASE_URL` should **only** be set if you're using a custom OpenAI-compatible endpoint (like a local LLM server or RunPod inference). Leave it unset to use the default OpenAI API.
- `ANTHROPIC_API_KEY` is **only** required if you plan to use Claude models (e.g., `bfts_config_claude-haiku.yaml`).

## Running Experiments

**Available config files:**
- `bfts_config.yaml` - Default configuration
- `bfts_config_gpt-5.yaml` - GPT-5 model configuration
- `bfts_config_claude-haiku.yaml` - Claude Haiku configuration

### Run Full End-to-End Pipeline

To run the complete BFTS experiment workflow including all stages, plot aggregation, paper writeup, and review:

```bash
python launch_scientist_bfts.py <config_file>
```

**Required Argument:**
- `<config_file>`: Path to the YAML configuration file (e.g., `bfts_config.yaml`)

**Review Configuration:**
- Define the review model and temperature directly in your YAML config:
  ```
  review:
    model: gpt-5
    temperature: 1.0
  ```
- If the `review` section is missing or incomplete, the review stage is skipped even when `--skip_review` is not set.

**Writeup Configuration:**
- Configure all writeup and aggregation settings inside the `writeup` section of your YAML config. Example:
  ```
  writeup:
    model: gpt-5
    plot_model: gpt-5
    citation_model: gpt-5
    temperature: 0.8
    writeup_type: normal
    writeup_retries: 3
    num_cite_rounds: 5
  ```
- `model`: LLM for drafting the paper.
- `plot_model`: LLM used for plot aggregation.
- `citation_model`: LLM used for citation gathering (falls back to `model` when omitted).
- `temperature`: Sampling temperature shared across citation, drafting, and reflection steps.
- `writeup_type`: `normal` for 8-page or `icbinb` for 4-page writeups.
- `writeup_retries`: Maximum number of writeup attempts.
- `num_cite_rounds`: Maximum number of citation gathering rounds.
- Remove the `writeup` block entirely to skip writeup and review.

### Telemetry Configuration (Optional)

To mirror the server's event feed, provide a `telemetry` block in the YAML config:

```
telemetry:
  database_url: ${env:DATABASE_URL,""}
  run_id: ${env:RUN_ID,""}
  webhook_url: ${env:TELEMETRY_WEBHOOK_URL,""}
  webhook_token: ${env:TELEMETRY_WEBHOOK_TOKEN,""}
```

`database_url` + `run_id` enables Postgres persistence; `webhook_url` + `webhook_token` (plus the same `run_id`) enable live callbacks to the server. Leave any of them blank to disable that destination.
Set `webhook_url` to the base endpoint (e.g., `https://your-server/api/research-pipeline/events`); the pipeline appends the specific event path automatically.

**Optional Argument:**
- `--resume RUN_NAME_OR_NUMBER`: Resume from a specific run folder (e.g., `4` or `4-run`); the launcher runs only the next missing stage for that run, or skips stages entirely if summaries exist, then performs aggregation/writeup per config.

**Example - Full Pipeline:**
```bash
python launch_scientist_bfts.py bfts_config_gpt-5.yaml
```

**Example - Resume From Specific Run:**
```bash
# Resume run "4-run" (or pass just 4). If stage 2/3/4 are missing, the launcher will run the next missing stage.
# If all summaries exist under logs/4-run, it will skip stages and perform aggregation/writeup only.
python launch_scientist_bfts.py bfts_config_gpt-5.yaml --resume 1
```

**What the Full Pipeline Does:**
1. **Loads research idea** from the JSON file specified in config's `desc_file`
2. **Runs all BFTS stages** via AgentManager using directories from the provided config:
   - Stage 1: Initial implementation
   - Stage 2: Baseline tuning
   - Stage 3: Creative research (plotting)
   - Stage 4: Ablation studies
3. **Aggregates plots** across runs using the specified model
4. **Generates paper writeup** (normal or ICBINB format) using the specified model
5. **Gathers citations** using the specified citation model
6. **Performs paper review** (text and images/captions/references) using the model defined in the config's `review` section (when present)

**Output:**
- Experiment logs: under the `log_dir` specified in your config (e.g., `workspaces/logs/<run_id>/`)
- Figures: under the parent directory of `log_dir` (e.g., `workspaces/figures/`)
- Paper PDF (if writeup enabled): under the parent directory of `log_dir` (e.g., `workspaces/`)
- Review results (if writeup and review enabled): `review_text.txt` and `review_img_cap_ref.json` 
- Token usage: `token_tracker.json` in the reports base directory

### Notes
- The idea file (`desc_file`) and all directories are taken from your YAML config;
- Logging level is controlled via `log_level` in the YAML config (e.g., `DEBUG`, `INFO`).
