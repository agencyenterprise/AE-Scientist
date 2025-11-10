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

