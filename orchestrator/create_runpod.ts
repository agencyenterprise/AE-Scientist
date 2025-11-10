#!/usr/bin/env npx tsx
/**
 * Simple RunPod Container Creator
 *
 * Creates a RunPod container and outputs the SSH connection command.
 * Usage: tsx create_runpod.ts [--no-auto-terminate] [--gpu-type "NVIDIA RTX A4000"]
 */

import dotenv from "dotenv"
import path from "node:path"
import { fileURLToPath } from "node:url"

dotenv.config({
  path: path.resolve(fileURLToPath(import.meta.url), "..", "..", ".env")
})

// ============================================================================
// Configuration
// ============================================================================

const CONFIG = {
  // RunPod API
  apiKey: process.env.RUNPOD_API_KEY!,
  baseURL: "https://rest.runpod.io/v1",

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
  maxPollAttempts: 60 // 5 minutes max wait
}

// ============================================================================
// Types
// ============================================================================

interface GpuType {
  id: string
  count: number
  displayName: string
  securePrice: number
  communityPrice: number
  oneMonthPrice: number
  threeMonthPrice: number
  sixMonthPrice: number
  oneWeekPrice: number
  communitySpotPrice: number
  secureSpotPrice: number
}

interface CpuType {
  id: string
  displayName: string
  cores: number
  threadsPerCore: number
  groupId: string
}

interface Machine {
  minPodGpuCount: number
  gpuTypeId: string
  gpuType: GpuType
  cpuCount: number
  cpuTypeId: string
  cpuType: CpuType
  location: string
  dataCenterId: string
  diskThroughputMBps: number
  maxDownloadSpeedMbps: number
  maxUploadSpeedMbps: number
  supportPublicIp: boolean
  secureCloud: boolean
  maintenanceStart?: string
  maintenanceEnd?: string
  maintenanceNote?: string
  note?: string
  costPerHr: number
  currentPricePerGpu: number
  gpuAvailable: number
  gpuDisplayName: string
}

interface NetworkVolume {
  id: string
  name: string
  size: number
  dataCenterId: string
}

interface SavingsPlan {
  costPerHr: number
  endTime: string
  gpuTypeId: string
  id: string
  podId: string
  startTime: string
}

interface PodInfo {
  id: string
  name: string
  desiredStatus: "RUNNING" | "EXITED" | "TERMINATED"
  adjustedCostPerHr: number
  aiApiId: string | null
  consumerUserId: string
  containerDiskInGb: number
  containerRegistryAuthId: string | null
  costPerHr: string
  cpuFlavorId?: string
  dockerEntrypoint?: string[]
  dockerStartCmd?: string[]
  endpointId: string | null
  env: Record<string, string>
  gpu?: GpuType
  image: string
  interruptible: boolean
  lastStartedAt: string
  lastStatusChange: string
  locked: boolean
  machine?: Machine
  machineId: string
  memoryInGb: number
  networkVolume?: NetworkVolume
  portMappings: Record<string, number>
  ports: string[]
  publicIp: string | null
  savingsPlans?: SavingsPlan[]
  slsVersion?: number
  templateId: string | null
  vcpuCount: number
  volumeEncrypted: boolean
  volumeInGb: number
  volumeMountPath: string
}

interface CreatePodResponse {
  id: string
  name: string
  imageName: string
  gpuCount: number
  [key: string]: unknown
}

// ============================================================================
// API Functions
// ============================================================================

async function makeRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${CONFIG.baseURL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${CONFIG.apiKey}`,
      "Content-Type": "application/json",
      ...options.headers
    }
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.log({
      response,
      errorText
    })
    let errorMessage: string
    try {
      const errorJson = JSON.parse(errorText)
      errorMessage = JSON.stringify(errorJson, null, 2)
    } catch {
      errorMessage = errorText
    }
    throw new Error(`RunPod API error (${response.status}): ${errorMessage}`)
  }

  return response.json() as Promise<T>
}

async function createPod(
  gpuType: string,
  autoTerminate: boolean,
  branch: string
): Promise<CreatePodResponse> {
  const dockerStartCmd = buildDockerStartCommand(autoTerminate)

  const podPayload = {
    name: `${CONFIG.repoName}-${Date.now()}`,
    imageName: CONFIG.imageName,
    cloudType: "SECURE",
    gpuCount: CONFIG.gpuCount,
    gpuTypeIds: [gpuType],
    containerDiskInGb: CONFIG.containerDiskInGb,
    volumeInGb: CONFIG.volumeInGb,
    env: {
      GIT_SSH_KEY_B64: `{{ RUNPOD_SECRET_${CONFIG.sshKeySecretName} }}`,
      REPO_NAME: CONFIG.repoName,
      REPO_ORG: CONFIG.repoOrg,
      REPO_BRANCH: branch,
      REPO_STARTUP_CMD: ""
    },
    ports: CONFIG.ports,
    dockerStartCmd: ["bash", "-c", dockerStartCmd]
  }

  return await makeRequest<CreatePodResponse>("/pods", {
    method: "POST",
    body: JSON.stringify(podPayload)
  })
}

async function getPod(podId: string): Promise<PodInfo> {
  return await makeRequest<PodInfo>(`/pods/${podId}`)
}

async function getPodHostId(podId: string): Promise<string | null> {
  const query = `
    query pod($input: PodFilter!) {
      pod(input: $input) {
        machine {
          podHostId
        }
        __typename
      }
      __typename
    }
  `

  const response = await fetch("https://api.runpod.io/graphql", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${CONFIG.apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      operationName: "pod",
      variables: {
        input: {
          podId
        }
      },
      query
    })
  })

  if (!response.ok) {
    const errorText = await response.text()
    const status = response.status
    console.warn(
      `⚠️  Failed to fetch podHostId from GraphQL API: ${status} ${errorText}`
    )
    return null
  }

  const data = await response.json()
  return data?.data?.pod?.machine?.podHostId as string | null
}

// ============================================================================
// Helper Functions
// ============================================================================

function buildDockerStartCommand(autoTerminate: boolean): string {
  const scriptParts: string[] = [
    "set -euo pipefail",
    "",
    "# === Repository Setup ===",
    "curl -fsSL https://raw.githubusercontent.com/agencyenterprise/AE-Scientist-infra/refs/heads/main/setup_repo.sh | bash",
    "",
    "# === Keep container running ===",
    'echo "Container ready! Keeping alive..."'
  ]

  if (autoTerminate) {
    scriptParts.push("")
    scriptParts.push("# Note: Container will auto-terminate on exit")
  } else {
    scriptParts.push(
      'echo "Container will stay alive until manually terminated"'
    )
    scriptParts.push("# Keep container running indefinitely")
    scriptParts.push("tail -f /dev/null")
  }

  return scriptParts.join("\n").trim()
}

async function waitForPodReady(
  podId: string
): Promise<{ pod: PodInfo; podHostId: string }> {
  console.log("\n⏳ Waiting for pod to be ready...")

  for (let attempt = 1; attempt <= CONFIG.maxPollAttempts; attempt++) {
    await new Promise((resolve) => setTimeout(resolve, CONFIG.pollIntervalMs))

    try {
      const pod = await getPod(podId)
      const isRunning = pod.desiredStatus === "RUNNING"
      const hasPublicIp = pod.publicIp !== null && pod.publicIp !== undefined
      const hasPortMappings = Object.keys(pod.portMappings || {}).length > 0

      if (isRunning && hasPublicIp && hasPortMappings) {
        const podHostId = await getPodHostId(podId)
        if (!podHostId) {
          throw new Error("Pod host ID not found after pod became ready")
        }
        console.log(
          `✅ Pod is ready! (attempt ${attempt}/${CONFIG.maxPollAttempts})`
        )
        return {
          pod,
          podHostId
        }
      }

      process.stdout.write(
        `\r   Attempt ${attempt}/${CONFIG.maxPollAttempts} booting pod...`
      )
    } catch (error) {
      console.log(`\n⚠️  Error checking pod status: ${error}`)
    }
  }

  throw new Error("Pod did not become ready in time")
}

function extractSSHInfo(
  pod: PodInfo,
  podHostId: string
): {
  command: string | null
  port: number
  ip: string
} | null {
  // Check if SSH port (22) is mapped
  const sshPublicPort = pod.portMappings?.["22"]

  if (!sshPublicPort || !pod.publicIp) {
    return null
  }

  // RunPod SSH proxy connection (using podHostId from GraphQL API)
  const command = podHostId
    ? `ssh ${podHostId}@ssh.runpod.io -i ~/.ssh/id_ed25519`
    : null


  return {
    command,
    port: sshPublicPort,
    ip: pod.publicIp
  }
}

async function createPodWithRetry(
  gpuTypes: string[],
  autoTerminate: boolean,
  branch: string
): Promise<CreatePodResponse> {
  let lastError: Error | null = null
  let attemptCount = 0
  const maxAttempts = Math.max(CONFIG.maxRetries, gpuTypes.length)

  for (let i = 0; i < maxAttempts; i++) {
    const gpuType = gpuTypes[i % gpuTypes.length]
    attemptCount++

    try {
      console.log(
        `\n[Attempt ${attemptCount}/${maxAttempts}] Creating pod with GPU: ${gpuType}`
      )
      const pod = await createPod(gpuType, autoTerminate, branch)
      console.log(`✅ Pod created successfully!`)
      console.log(`   Pod ID: ${pod.id}`)
      console.log(`   Pod name: ${pod.name}`)
      console.log(`   GPU type: ${gpuType}`)
      return pod
    } catch (error) {
      lastError = error as Error
      const errorMessage =
        error instanceof Error ? error.message : String(error)

      const isGpuUnavailableError =
        errorMessage
          .toLowerCase()
          .includes("no instances currently available") ||
        errorMessage.includes("500")

      if (isGpuUnavailableError && i < maxAttempts - 1) {
        console.log(
          `⚠️  GPU type "${gpuType}" unavailable. Trying next GPU type...`
        )
        await new Promise((resolve) => setTimeout(resolve, 1000))
        continue
      } else {
        throw error
      }
    }
  }

  throw new Error(
    `Failed to create pod after ${attemptCount} attempts. ` +
      `Tried GPU types: ${gpuTypes.join(", ")}. ` +
      `Last error: ${lastError?.message || "Unknown error"}`
  )
}

// ============================================================================
// Main Function
// ============================================================================

async function main() {
  console.log("🚀 RunPod Container Creator")
  console.log("=".repeat(50))

  // Parse command line arguments
  const args = process.argv.slice(2)
  const autoTerminate = args.includes("--auto-terminate")
  const gpuTypeArg = args.find((arg) => arg.startsWith("--gpu-types="))
  const branch = args.find((arg) => arg.startsWith("--branch="))
    ? args.find((arg) => arg.startsWith("--branch="))?.split("=")[1]
    : CONFIG.repoBranch
  const gpuTypes = gpuTypeArg
    ? gpuTypeArg.split("=")[1].split(",")
    : CONFIG.defaultGpuTypes

  console.log(`\nConfiguration:`)
  console.log(`  Repository: ${CONFIG.repoOrg}/${CONFIG.repoName}`)
  console.log(`  Branch: ${CONFIG.repoBranch}`)
  console.log(`  GPU Types: ${gpuTypes.join(", ")}`)
  console.log(`  Auto-terminate: ${autoTerminate ? "Yes" : "No"}`)

  // Validate API key
  if (!CONFIG.apiKey) {
    throw new Error(
      "RUNPOD_API_KEY environment variable is required. " +
        "Set it in your .env file or export it in your shell."
    )
  }

  // Create pod
  const pod = await createPodWithRetry(gpuTypes, autoTerminate, branch)

  // Wait for pod to be ready
  const { pod: readyPod, podHostId } = await waitForPodReady(pod.id)

  // Fetch podHostId from GraphQL API for SSH proxy connection
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
