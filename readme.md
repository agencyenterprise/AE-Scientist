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
```
