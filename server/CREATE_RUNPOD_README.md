# RunPod Creator Script

Python script to create and configure a RunPod GPU instance with the AE-Scientist repository.

## Usage

Create a `.env` file in the project root with the required variables (see `server/env.example.runpod` for reference):

**Multi-line format:**
```bash
RUNPOD_API_KEY=your_runpod_api_key
GIT_DEPLOY_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your deploy key...
-----END OPENSSH PRIVATE KEY-----
OPENAI_API_KEY=your_openai_api_key
HF_TOKEN=your_huggingface_token
```

**One-liner format (with `\n` for newlines):**
```bash
RUNPOD_API_KEY=your_runpod_api_key
GIT_DEPLOY_KEY=-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----
OPENAI_API_KEY=your_openai_api_key
HF_TOKEN=your_huggingface_token
```

Then run the script:

```bash
python server/create_runpod.py
```

The script automatically loads variables from `.env` using `python-dotenv`.

## What it does

1. **Validates environment variables**: Ensures `RUNPOD_API_KEY` and `GIT_DEPLOY_KEY` are set
2. **Creates a RunPod**: Provisions a GPU pod with the PyTorch image
3. **Validates GPU**: Runs `nvidia-smi` to ensure GPU is available
4. **Clones repository**: Uses the external `setup_repo.sh` script (same as TypeScript implementation) to clone the AE-Scientist repo into `/workspace`
5. **Creates .env file**: Writes environment variables to `/workspace/AE-Scientist/research_pipeline/.env`
6. **Runs installation**: Executes `bash install_run_pod.sh` to set up dependencies and create virtual environment
7. **Starts research pipeline**: Activates the venv and runs `python launch_scientist_bfts.py bfts_config_gpt-5.yaml` with output logged to `/workspace/research_pipeline.log`
8. **Outputs SSH command**: Provides the SSH connection details

**Note**: This implementation follows the same approach as `orchestrator/create_runpod.ts`, using the external setup script from `AE-Scientist-infra` repository to avoid breaking SSH access.

## Required Environment Variables (in .env file)

- `RUNPOD_API_KEY` - Your RunPod API key (required)
- `GIT_DEPLOY_KEY` - GitHub deploy key for private repo access (required, supports both multi-line and one-liner with `\n`)
- `OPENAI_API_KEY` - OpenAI API key (optional, written to pod's .env)
- `HF_TOKEN` - HuggingFace token (optional, written to pod's .env)

**Note**: The script uses `python-dotenv` to automatically load these from a `.env` file in the project root.

## Example Output

```
🚀 RunPod Creator and Configurator
======================================================================

📋 Reading environment variables...
✅ All required environment variables found (loaded from .env)

🔑 Setting up GitHub deploy key...
✅ Deploy key saved to /Users/you/.ssh/ae_scientist_deploy_key

Creating pod 'ae-scientist-1732653421'...
✅ Pod created: abc123xyz

⏳ Waiting for pod to be ready...
✅ Pod is ready! (attempt 12/60)

🔍 Fetching SSH connection details...

======================================================================
🎉 Pod is ready!
======================================================================

Pod ID: abc123xyz
Pod Name: ae-scientist-1732653421
Public IP: 1.2.3.4

📡 SSH Connection:
  Via RunPod Proxy (Recommended):
    ssh abc123xyz-abc123@ssh.runpod.io -i ~/.ssh/id_ed25519

  Via Public IP:
    ssh root@1.2.3.4 -p 12345 -i ~/.ssh/id_ed25519

🌐 RunPod Console:
   https://www.runpod.io/console/pods

🚀 Research pipeline starting automatically...
   Output is being logged to: /workspace/research_pipeline.log
   
   To monitor progress, SSH into the pod and run:
   $ tail -f /workspace/research_pipeline.log

======================================================================
```

## Notes

- Create your `.env` file in the project root (same directory as this script)
- The `GIT_DEPLOY_KEY` supports both formats:
  - Multi-line: Paste the key with actual line breaks
  - One-liner: Use `\n` for newlines (the script automatically converts `\n` to actual newlines)
- The script tries multiple GPU types in order: RTX A4000, RTX A4500, GeForce RTX 3090, RTX A5000
- The pod will automatically start the research pipeline with `bfts_config_gpt-5.yaml`
- All output is logged to `/workspace/research_pipeline.log` on the pod
- You can SSH into the pod while it's running to monitor progress:
  ```bash
  # Tail the log file to watch in real-time
  tail -f /workspace/research_pipeline.log
  ```
- The pod will terminate automatically when the research pipeline completes
- All setup and execution is performed inside the pod's docker start command

