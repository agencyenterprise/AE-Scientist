# AE-Scientist


## Setup (Local)

1. Clone repository and cd into it
```bash
git clone https://github.com/agencyenterprise/AE-Scientist.git
cd AE-Scientist
```

2. Install dependencies
```bash
uv sync --extra gpu
```

3. Activate the virtual environment
```bash
source .venv/bin/activate
```

## Setup (RunPod)

1. Clone repository and cd into it
```bash
git clone https://github.com/agencyenterprise/AE-Scientist.git
cd AE-Scientist
```

2. Create a new virtual environment with access to system-wide packages
```bash
uv venv --system-site-packages
```

This is important because RunPod provides images with pytorch and other gpu-related packages, 
some of these packages may conflict with the packages listed in pyproject.toml.

In order to use the pre-installed packages, we need to create a virtual environment with access to system-wide packages.

3. Activate the virtual environment
```bash
source .venv/bin/activate
```

4. Install dependencies
```bash
uv sync
```

## Environment Variables

Before running experiments, you need to configure API keys and tokens.

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:

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

### Run Stage 1 Only (Initial Implementation)

To run only Stage 1 of the experiment pipeline (useful for testing or debugging):

```bash
python launch_stage1_only.py <config_file>
```

**Example:**
```bash
python launch_stage1_only.py bfts_config.yaml
```

**Available config files:**
- `bfts_config.yaml` - Default configuration
- `bfts_config_gpt-5.yaml` - GPT-5 model configuration
- `bfts_config_claude-haiku.yaml` - Claude Haiku configuration

**What Stage 1 does:**
- Loads research idea from `desc_file` (specified in config)
- Creates initial experiment implementations
- Generates plots from experimental results
- Uses Vision Language Model (VLM) to validate plot quality
- Runs multi-seed evaluation on successful implementations
- Saves results to `workspace_dir` (specified in config)

**Output:**
- Experiment artifacts saved to: `workspaces/<exp_name>/`
- Logs saved to: `workspaces/logs/<exp_name>/`
- Plots saved to: `workspaces/logs/<exp_name>/experiment_results/`
- Best implementation code: `workspaces/logs/<exp_name>/stage_*/best_solution_*.py`

## Creating a RunPod Container for Experiments

**Note:** This is only necessary if you want to run experiments on RunPod.

Requirement: make sure you have a RUNPOD_API_KEY environment variable set.

1. Open orchestrator and install dependencies
```bash
cd orchestrator
pnpm install
```

2. Call the create_runpod.ts script
```bash
./create_runpod.ts --gpu-count 3 --branch main --gpu-types "NVIDIA GeForce RTX 5090"

# Or from the root
./orchestrator/create_runpod.ts --gpu-count 3 --branch my-branch --gpu-types "NVIDIA GeForce RTX 5090"

# Use a custom pod name
./orchestrator/create_runpod.ts --gpu-count 3 --branch main --gpu-types "NVIDIA GeForce RTX 5090" --pod-name "my-pod-name"
./orchestrator/create_runpod.ts --gpu-count 3 --branch main --gpu-types "NVIDIA GeForce RTX 5090" -n "my-pod-name"
```


### Run Full End-to-End Pipeline

To run the complete BFTS experiment workflow including all stages, plot aggregation, paper writeup, and review:

```bash
python launch_scientist_bfts.py \
  --load_ideas <ideas_json_file> \
  --model_agg_plots <model_name> \
  --model_writeup <model_name> \
  --model_citation <model_name> \
  --model_review <model_name>
```

**Required Arguments:**
- `--load_ideas`: Path to a JSON file containing pregenerated research ideas
- `--model_agg_plots`: Model to use for plot aggregation (e.g., `gpt-5`)
- `--model_writeup`: Model to use for paper writeup (e.g., `gpt-5`) - required unless `--skip_writeup` is set
- `--model_citation`: Model to use for citation gathering (e.g., `gpt-5`) - required unless `--skip_writeup` is set
- `--model_review`: Model to use for paper review (e.g., `gpt-5`) - required unless `--skip_review` or `--skip_writeup` is set

**Optional Arguments:**
- `--writeup-type`: Type of writeup to generate (`normal` for 8-page or `icbinb` for 4-page, default: `icbinb`)
- `--load_code`: If set, load a Python file with same name as ideas file but `.py` extension
- `--idea_idx`: Index of the idea to run from the ideas JSON file (default: `0`)
- `--add_dataset_ref`: If set, add a HuggingFace dataset reference to the idea
- `--writeup-retries`: Number of writeup attempts to try (default: `3`)
- `--attempt_id`: Attempt ID for distinguishing same idea in parallel runs (default: `0`)
- `--num_cite_rounds`: Number of citation rounds to perform (default: `20`)
- `--skip_writeup`: Skip the writeup process (also skips review)
- `--skip_review`: Skip the review process (writeup must still run)

**Example - Full Pipeline:**
```bash
python launch_scientist_bfts.py \
  --load_ideas idea_example.json \
  --model_agg_plots gpt-5 \
  --model_writeup gpt-5 \
  --model_citation gpt-5 \
  --model_review gpt-5
```

**Example - Skip Writeup (Experiments Only):**
```bash
python launch_scientist_bfts.py \
  --load_ideas idea_example.json \
  --skip_writeup \
  --model_agg_plots gpt-5
```

**Example - Skip Review (Experiments + Writeup):**
```bash
python launch_scientist_bfts.py \
  --load_ideas idea_example.json \
  --skip_review \
  --model_agg_plots gpt-5 \
  --model_writeup gpt-5 \
  --model_citation gpt-5
```

**What the Full Pipeline Does:**
1. **Loads research idea** from JSON file (and optionally code)
2. **Creates experiment workspace** in `experiments/<timestamp>_<idea_name>_attempt_<id>/`
3. **Runs all BFTS stages** via AgentManager:
   - Stage 1: Initial implementation
   - Stage 2: Baseline tuning
   - Stage 3: Creative research (plotting)
   - Stage 4: Ablation studies
4. **Aggregates plots** across runs using the specified model
5. **Copies best solutions** to experiment root directory
6. **Generates paper writeup** (normal or ICBINB format) using the specified model
7. **Gathers citations** using the specified citation model
8. **Performs paper review** (text and images/captions/references) using the specified review model

**Output:**
- Experiment directory: `experiments/<timestamp>_<idea_name>_attempt_<id>/`
- Experiment logs: `experiments/.../logs/0-run/`
- Best solution code: `experiments/.../best_code_stage_*.py`
- Paper PDF: `experiments/.../*.pdf`
- Review results: `experiments/.../review_text.txt` and `review_img_cap_ref.json`
- Token usage: `experiments/.../token_tracker.json`

