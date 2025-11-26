#!/usr/bin/env python3
"""
RunPod Creator and Configurator

Creates a RunPod container, validates GPU, clones the repository,
sets up the environment, and runs the installation script.
"""

import base64
import os
import subprocess
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv


class RunPodError(Exception):
    """RunPod API error"""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class RunPodCreator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://rest.runpod.io/v1"
        self.graphql_url = "https://api.runpod.io/graphql"

    def _make_request(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the RunPod REST API"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.request(method=method, url=url, headers=headers, json=data)

        if not response.ok:
            error_text = response.text
            raise RunPodError(
                f"RunPod API error ({response.status_code}): {error_text}",
                status=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def _graphql_request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Make a GraphQL request to RunPod API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            self.graphql_url,
            headers=headers,
            json={"query": query, "variables": variables},
        )

        if not response.ok:
            raise RunPodError(
                f"GraphQL error ({response.status_code}): {response.text}",
                status=response.status_code,
            )

        result: dict[str, Any] = response.json()
        return result

    def get_pod_host_id(self, pod_id: str) -> str | None:
        """Get pod host ID for SSH proxy connection"""
        query = """
            query pod($input: PodFilter!) {
                pod(input: $input) {
                    machine {
                        podHostId
                    }
                }
            }
        """
        variables = {"input": {"podId": pod_id}}

        try:
            result = self._graphql_request(query=query, variables=variables)
            pod_host_id: str | None = (
                result.get("data", {}).get("pod", {}).get("machine", {}).get("podHostId")
            )
            return pod_host_id
        except Exception as e:
            print(f"⚠️  Warning: Failed to get podHostId: {e}")
            return None

    def _attempt_create_pod(
        self,
        name: str,
        image: str,
        gpu_type: str,
        env: dict[str, str],
        docker_cmd: str,
        attempt_number: int,
    ) -> dict[str, Any]:
        """Attempt to create a RunPod pod with a specific GPU type"""
        payload = {
            "name": name,
            "imageName": image,
            "cloudType": "SECURE",
            "gpuCount": 1,
            "gpuTypeIds": [gpu_type],
            "containerDiskInGb": 30,
            "volumeInGb": 50,
            "env": env,
            "ports": ["22/tcp"],
            "dockerStartCmd": ["bash", "-c", docker_cmd],
        }

        print(f"[Attempt {attempt_number}] Creating pod with GPU type: {gpu_type}")
        result = self._make_request(endpoint="/pods", method="POST", data=payload)
        return result

    def create_pod(
        self,
        name: str,
        image: str,
        gpu_types: list[str],
        env: dict[str, str],
        docker_cmd: str,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Create a RunPod pod with GPU availability retry logic"""
        if not gpu_types:
            raise ValueError("At least one GPU type must be specified")

        last_error: Exception | None = None
        max_attempts = max(max_retries, len(gpu_types))

        # Round-robin through GPU types
        for i in range(max_attempts):
            gpu_type = gpu_types[i % len(gpu_types)]
            attempt_number = i + 1

            try:
                pod = self._attempt_create_pod(
                    name=name,
                    image=image,
                    gpu_type=gpu_type,
                    env=env,
                    docker_cmd=docker_cmd,
                    attempt_number=attempt_number,
                )
                print("✅ Pod created successfully!")
                print(f"   Pod ID: {pod['id']}")
                print(f"   Pod name: {pod['name']}")
                print(f"   GPU type: {gpu_type}")
                return pod
            except RunPodError as error:
                last_error = error
                is_unavailable_error = (
                    "no instances currently available" in str(error).lower() or error.status == 500
                )

                if is_unavailable_error and i < max_attempts - 1:
                    print(f"⚠️  GPU type '{gpu_type}' unavailable. Trying next GPU type...")
                    time.sleep(1)
                    continue
                elif not is_unavailable_error:
                    # Different kind of error, throw immediately
                    raise

        # If we get here, all attempts failed
        raise RunPodError(
            f"Failed to create pod after {max_attempts} attempts. "
            f"Tried GPU types: {', '.join(gpu_types)}. "
            f"Last error: {last_error}"
        )

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        """Get pod information"""
        return self._make_request(endpoint=f"/pods/{pod_id}")

    def wait_for_pod_ready(
        self, pod_id: str, poll_interval: int = 5, max_attempts: int = 60
    ) -> dict[str, Any]:
        """Wait for pod to be running with SSH access"""
        print("\n⏳ Waiting for pod to be ready...")

        for attempt in range(1, max_attempts + 1):
            time.sleep(poll_interval)

            try:
                pod = self.get_pod(pod_id=pod_id)
                is_running = pod.get("desiredStatus") == "RUNNING"
                has_public_ip = pod.get("publicIp") is not None
                has_port_mappings = bool(pod.get("portMappings", {}))

                if is_running and has_public_ip and has_port_mappings:
                    print(f"✅ Pod is ready! (attempt {attempt}/{max_attempts})")
                    return pod

                print(f"\r   Attempt {attempt}/{max_attempts} - booting pod...", end="")
            except Exception as e:
                print(f"\n⚠️  Error checking pod status: {e}")

        raise RunPodError("Pod did not become ready in time")

    def execute_ssh_command(
        self, host: str, port: int, command: str, ssh_key_path: str
    ) -> tuple[int, str, str]:
        """Execute a command over SSH"""
        ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-i",
            ssh_key_path,
            "-p",
            str(port),
            f"root@{host}",
            command,
        ]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=300)
        return result.returncode, result.stdout, result.stderr


def main() -> None:
    print("🚀 RunPod Creator and Configurator")
    print("=" * 70)

    # Load environment variables from .env file
    load_dotenv()

    # Step 1: Read required environment variables
    print("\n📋 Reading environment variables...")
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        print("❌ ERROR: RUNPOD_API_KEY environment variable is required")
        sys.exit(1)

    github_deploy_key = os.environ.get("GIT_DEPLOY_KEY")
    if not github_deploy_key:
        print("❌ ERROR: GIT_DEPLOY_KEY environment variable is required")
        sys.exit(1)

    # Handle both multi-line and one-liner format (with literal \n)
    github_deploy_key = github_deploy_key.replace("\\n", "\n")

    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    hf_token = os.environ.get("HF_TOKEN", "")

    print("✅ All required environment variables found")

    # Step 2: Encode deploy key as base64 for the pod
    print("\n🔑 Encoding GitHub deploy key...")
    github_deploy_key_b64 = base64.b64encode(github_deploy_key.encode()).decode()
    print("✅ Deploy key encoded")

    # Step 3: Build docker start command (following TypeScript implementation)
    script_parts = ["set -euo pipefail", ""]

    # Validate GPU
    script_parts.append("# === GPU Validation ===")
    script_parts.append('echo "Validating GPU..."')
    script_parts.append('nvidia-smi || { echo "❌ nvidia-smi failed"; exit 1; }')
    script_parts.append('echo "✅ GPU validated"')
    script_parts.append("")

    # Repository setup using external script (matches TypeScript approach)
    script_parts.append("# === Repository Setup ===")
    script_parts.append(
        "curl -fsSL https://raw.githubusercontent.com/agencyenterprise/AE-Scientist-infra/refs/heads/main/setup_repo.sh | bash"
    )
    script_parts.append("")

    # Create .env file with API keys
    script_parts.append("# === Environment Setup ===")
    script_parts.append('echo "Creating .env file..."')
    script_parts.append("cd /workspace/AE-Scientist/research_pipeline")
    script_parts.append("cat > .env << 'EOF'")
    script_parts.append(f"OPENAI_API_KEY={openai_api_key}")
    script_parts.append(f"HF_TOKEN={hf_token}")
    script_parts.append("EOF")
    script_parts.append("")

    # Run installation script
    script_parts.append("# === Installation ===")
    script_parts.append('echo "Running installation script..."')
    script_parts.append("cd /workspace/AE-Scientist")
    script_parts.append("bash install_run_pod.sh")
    script_parts.append("")

    script_parts.append('echo "=== Setup complete ==="')
    script_parts.append("")

    # Run research pipeline
    script_parts.append("# === Starting Research Pipeline ===")
    script_parts.append('echo "Launching research pipeline..."')
    script_parts.append("cd /workspace/AE-Scientist/research_pipeline")
    script_parts.append("source .venv/bin/activate")
    script_parts.append(
        "python launch_scientist_bfts.py bfts_config_gpt-5.yaml 2>&1 | tee -a /workspace/research_pipeline.log"
    )
    script_parts.append(
        'echo "Research pipeline completed. Check /workspace/research_pipeline.log for full output."'
    )

    docker_cmd = "\n".join(script_parts).strip()

    # Step 4: Create RunPod
    creator = RunPodCreator(api_key=runpod_api_key)

    gpu_types = [
        "NVIDIA GeForce RTX 5090",
        "NVIDIA GeForce RTX 3090",
        "NVIDIA RTX A4000",
        "NVIDIA RTX A4500",
        "NVIDIA RTX A5000",
    ]

    pod_name = f"ae-scientist-{int(time.time())}"

    # Build environment variables for the pod (matches TypeScript implementation)
    pod_env = {
        # GitHub deploy key (base64 encoded for the external setup script)
        "GIT_SSH_KEY_B64": github_deploy_key_b64,
        # Repository configuration (used by setup_repo.sh)
        "REPO_NAME": "AE-Scientist",
        "REPO_ORG": "agencyenterprise",
        "REPO_BRANCH": "main",
        "REPO_STARTUP_CMD": "",
        # API keys (will be written to .env file by our script)
        "OPENAI_API_KEY": openai_api_key,
        "HF_TOKEN": hf_token,
    }

    pod = creator.create_pod(
        name=pod_name,
        image="runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
        gpu_types=gpu_types,
        env=pod_env,
        docker_cmd=docker_cmd,
    )

    pod_id = pod["id"]

    # Step 5: Wait for pod to be ready
    ready_pod = creator.wait_for_pod_ready(pod_id=pod_id)

    # Step 6: Get SSH connection details
    print("\n🔍 Fetching SSH connection details...")
    public_ip = ready_pod.get("publicIp")
    ssh_port = ready_pod.get("portMappings", {}).get("22")
    pod_host_id = creator.get_pod_host_id(pod_id=pod_id)

    # Step 7: Output results
    print("\n" + "=" * 70)
    print("🎉 Pod is ready!")
    print("=" * 70)
    print(f"\nPod ID: {pod_id}")
    print(f"Pod Name: {ready_pod.get('name')}")
    print(f"Public IP: {public_ip}")

    if ssh_port and public_ip:
        print("\n📡 SSH Connection:")
        if pod_host_id:
            print("  Via RunPod Proxy (Recommended):")
            print(f"    ssh {pod_host_id}@ssh.runpod.io -i ~/.ssh/id_ed25519")
        print("\n  Via Public IP:")
        print(f"    ssh root@{public_ip} -p {ssh_port} -i ~/.ssh/id_ed25519")
    else:
        print("\n⚠️  SSH port not available yet")

    print("\n🌐 RunPod Console:")
    print("   https://www.runpod.io/console/pods")

    print("\n⚠️  Remember to manually terminate the pod when done!")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
