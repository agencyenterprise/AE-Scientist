#!/usr/bin/env npx tsx
/**
 * Simple RunPod Container Creator
 *
 * Creates a RunPod container and outputs the SSH connection command.
 * Usage: tsx create_runpod.ts [--auto-terminate] [--gpu-types "NVIDIA RTX A4000"] [--branch main]
 */

import { Command } from "commander"
import dotenv from "dotenv"
import path from "node:path"
import { fileURLToPath } from "node:url"
import {
  createRunPodService,
  extractSSHInfo
} from "./lib/services/runpods.service.js"

dotenv.config({
  path: path.resolve(fileURLToPath(import.meta.url), "..", "..", ".env")
})

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
  // Container settings
  repoName: "AE-Scientist",
  repoOrg: "agencyenterprise",
  repoBranch: "main",
  sshKeySecretName: "GIT_SSH_KEY_AE_SCIENTIST_B64",

  // Hardware
  defaultGpuTypes: [
    "NVIDIA RTX A4000",
    "NVIDIA RTX A4500",
    "NVIDIA RTX 3090",
    "NVIDIA RTX A5000"
  ],
  gpuCount: 1,
  containerDiskInGb: 30,
  volumeInGb: 50,

  // Docker
  imageName: "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
  ports: ["22/tcp", "8888/http"],

  // Behavior
  maxRetries: 3,
  pollIntervalMs: 5000,
  maxPollAttempts: 60, // 5 minutes max wait

  // Pass environment variables to the pod
  podEnv: () => ({
    OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
    HUGGINGFACE_HUB_TOKEN: process.env.HUGGINGFACE_HUB_TOKEN ?? "",
    AWS_ACCESS_KEY_ID: process.env.AWS_ACCESS_KEY_ID ?? "",
    HF_TOKEN: process.env.HF_TOKEN ?? ""
  })
}

// ============================================================================
// CLI Setup with Commander
// ============================================================================

const program = new Command()

program
  .name("create-runpod")
  .description("Create a RunPod container with SSH access")
  .option("-n, --pod-name <name>", "Name of the pod")
  .option(
    "--auto-terminate",
    "Auto-terminate the pod after setup completes",
    false
  )
  .option(
    "--gpu-types <types>",
    "Comma-separated list of GPU types to try",
    CONFIG.defaultGpuTypes.join(",")
  )
  .option(
    "--gpu-count <count>",
    "Number of GPUs to allocate",
    CONFIG.gpuCount.toString()
  )
  .option("-b, --branch <branch>", "Git branch to checkout", CONFIG.repoBranch)
  .parse(process.argv)

const options = program.opts()

// ============================================================================
// Main Function
// ============================================================================

async function main() {
  console.log("🚀 RunPod Container Creator")
  console.log("=".repeat(50))

  // Parse options
  const autoTerminate = options.autoTerminate
  const gpuTypes = options.gpuTypes.split(",").map((t: string) => t.trim())
  const branch = options.branch
  const gpuCount = Number.parseInt(options.gpuCount, 10)
  const podName = options.podName
  console.log(`\nConfiguration:`)
  console.log(`  Repository: ${CONFIG.repoOrg}/${CONFIG.repoName}`)
  console.log(`  Branch: ${branch}`)
  console.log(`  GPU Types: ${gpuTypes.join(", ")}`)
  console.log(`  Auto-terminate: ${autoTerminate ? "Yes" : "No"}`)
  if (podName) {
    console.log(`  Pod Name: ${podName}`)
  }

  // Validate API key
  if (!process.env.RUNPOD_API_KEY) {
    throw new Error(
      "RUNPOD_API_KEY environment variable is required. " +
        "Set it in your .env file or export it in your shell."
    )
  }

  // Create service
  const service = createRunPodService()

  // Create pod
  const pod = await service.createWorkerPod({
    repoName: CONFIG.repoName,
    repoOrg: CONFIG.repoOrg,
    repoBranch: branch,
    sshKeySecretName: CONFIG.sshKeySecretName,
    gpuTypes,
    gpuCount,
    containerDiskInGb: CONFIG.containerDiskInGb,
    volumeInGb: CONFIG.volumeInGb,
    imageName: CONFIG.imageName,
    ports: CONFIG.ports,
    maxRetries: CONFIG.maxRetries,
    startupCommand: "tail -f /dev/null # Keep container running",
    autoTerminate,
    env: CONFIG.podEnv(),
    generatePodName: podName ? () => podName : undefined
  })

  // Wait for pod to be ready
  const { pod: readyPod, podHostId } = await service.waitForPodReady(
    pod.id,
    CONFIG.pollIntervalMs,
    CONFIG.maxPollAttempts
  )

  // Fetch SSH connection details
  console.log("\n🔍 Fetching SSH connection details...")

  // Extract SSH info
  const sshInfo = extractSSHInfo(readyPod, podHostId)

  console.log("\n" + "=".repeat(50))
  console.log("🎉 Pod is ready!")
  console.log("=".repeat(50))
  console.log(`\nPod ID: ${readyPod.id}`)
  console.log(`Pod Name: ${readyPod.name}`)
  console.log(`Public IP: ${readyPod.publicIp}`)

  if (sshInfo) {
    console.log(`\n📡 SSH Connection (RunPod Proxy - Recommended):`)
    console.log(`   ${sshInfo.command}`)
    console.log(`\n   Public IP: ${sshInfo.ip}`)
    console.log(`   SSH Port: ${sshInfo.port}`)
  } else {
    console.log("\n⚠️  SSH port not found. Pod may still be initializing.")
  }

  console.log(`\n🌐 RunPod Console:`)
  console.log(`   https://www.runpod.io/console/pods`)

  if (!autoTerminate) {
    console.log(`\n⚠️  Remember to manually terminate the pod when done!`)
  }

  console.log("\n" + "=".repeat(50))
}

// ============================================================================
// Entry Point
// ============================================================================

main()
  .then(() => {
    console.log("\n✅ Done!")
    process.exit(0)
  })
  .catch((error) => {
    console.error("\n❌ Error:", error.message)
    process.exit(1)
  })
