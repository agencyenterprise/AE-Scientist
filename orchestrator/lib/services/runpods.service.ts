/**
 * RunPod Service
 *
 * A robust service for managing RunPod GPU instances with:
 * - Setup script execution
 * - GPU availability retry logic with round-robin fallback
 * - Automatic pod termination using runpodctl
 */

// ============================================================================
// Types and Interfaces
// ============================================================================

export interface SetupScript {
  /** Name/description of the setup script */
  name: string
  /** The bash script content to execute */
  content: string
}

export interface CreatePodOptions {
  /** Name of the repository to clone */
  repoName: string
  /** GitHub organization (default: "agencyenterprise") */
  repoOrg?: string
  /** Branch to checkout (default: "main") */
  repoBranch?: string
  /** RunPod secret name for SSH key (must be base64 encoded) */
  sshKeySecretName: string
  /** Command to run after repository setup */
  startupCommand?: string
  /** List of GPU types to try in order (round-robin fallback) */
  gpuTypes?: string[]
  /** Number of GPUs to allocate */
  gpuCount?: number
  /** Environment variables to pass to the pod */
  env?: Record<string, string>
  /** Setup scripts to execute before repository setup */
  setupScripts?: SetupScript[]
  /** Container disk size in GB (default: 30) */
  containerDiskInGb?: number
  /** Volume size in GB (default: 50) */
  volumeInGb?: number
  /** Docker image to use (default: runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404) */
  imageName?: string
  /** Ports to expose (default: ["22/tcp", "8888/http"]) */
  ports?: string[]
  /** Maximum retry attempts for GPU availability (default: 3) */
  maxRetries?: number
  /** Whether to auto-terminate the pod after completion (default: true) */
  autoTerminate?: boolean
  /** Function to generate the pod name (default: {repoName}-worker-{timestamp}) */
  generatePodName?: (options: CreatePodOptions) => string
}

export interface GpuType {
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

export interface CpuType {
  id: string
  displayName: string
  cores: number
  threadsPerCore: number
  groupId: string
}

export interface Machine {
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

export interface NetworkVolume {
  id: string
  name: string
  size: number
  dataCenterId: string
}

export interface SavingsPlan {
  costPerHr: number
  endTime: string
  gpuTypeId: string
  id: string
  podId: string
  startTime: string
}

export interface PodInfo {
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

export interface ListPodsResponse {
  pods: PodInfo[]
}

export interface CreatePodResponse {
  id: string
  name: string
  imageName: string
  gpuCount: number
  [key: string]: unknown
}

// ============================================================================
// RunPod Service Class
// ============================================================================

class RunPodServiceError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = "RunPodServiceError"
    this.status = status
  }
}

export class RunPodService {
  private readonly apiKey: string
  private readonly baseURL = "https://rest.runpod.io/v1"

  constructor(apiKey: string) {
    if (!apiKey) {
      throw new Error("RunPod API key is required")
    }
    this.apiKey = apiKey
  }

  // --------------------------------------------------------------------------
  // Private Helper Methods
  // --------------------------------------------------------------------------

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
        ...options.headers
      }
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorMessage: string
      try {
        const errorJson = JSON.parse(errorText)
        errorMessage = JSON.stringify(errorJson, null, 2)
      } catch {
        errorMessage = errorText
      }
      throw new RunPodServiceError(
        `RunPod API error (${response.status}): ${errorMessage}`,
        response.status
      )
    }

    return response.json() as Promise<T>
  }

  private buildDockerStartCommand(options: CreatePodOptions): string {
    const { setupScripts = [], startupCommand, autoTerminate = true } = options

    const scriptParts: string[] = ["set -euo pipefail", ""]

    // Add setup scripts
    if (setupScripts.length > 0) {
      scriptParts.push("# === Setup Scripts ===")
      setupScripts.forEach((script, index) => {
        scriptParts.push(
          `echo "Running setup script ${index + 1}/${setupScripts.length}: ${script.name}..."`
        )
        scriptParts.push(script.content)
        scriptParts.push("")
      })
    }

    // Add repository setup
    scriptParts.push("# === Repository Setup ===")
    scriptParts.push(
      "curl -fsSL https://raw.githubusercontent.com/agencyenterprise/AE-Scientist-infra/refs/heads/main/setup_repo.sh | bash"
    )
    scriptParts.push("")

    // Add startup command if provided
    if (startupCommand) {
      scriptParts.push("# === Startup Command ===")
      scriptParts.push(`echo "Executing startup command..."`)
      scriptParts.push(startupCommand)
      scriptParts.push("")
    }

    // Add auto-termination
    if (autoTerminate) {
      scriptParts.push("# === Auto-termination ===")
      scriptParts.push(
        'echo "Work complete. Terminating pod $RUNPOD_POD_ID..."'
      )
      // Note: this is the command to terminate the pod using the RunPod CLI
      // You can alternatively run this command from your program directly.
      scriptParts.push("runpodctl remove pod $RUNPOD_POD_ID")
      scriptParts.push('echo "Termination request sent!"')
    }

    return scriptParts.join("\n").trim()
  }

  private async attemptCreatePod(
    options: CreatePodOptions,
    gpuType: string,
    attemptNumber: number
  ): Promise<CreatePodResponse> {
    const {
      repoName,
      repoOrg = "agencyenterprise",
      repoBranch = "main",
      sshKeySecretName,
      startupCommand,
      gpuCount = 1,
      env = {},
      containerDiskInGb = 30,
      volumeInGb = 50,
      imageName = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
      ports = ["22/tcp", "8888/http"],
      generatePodName
    } = options
    const cloudType = "SECURE"
    const generatedName = generatePodName
      ? generatePodName(options)
      : `${repoName}-worker-${Date.now()}`

    const podPayload = {
      name: generatedName,
      imageName,
      cloudType,
      gpuCount,
      gpuTypeIds: [gpuType],
      containerDiskInGb,
      volumeInGb,
      env: {
        // Map the RunPod secret to a generic variable name
        GIT_SSH_KEY_B64: `{{ RUNPOD_SECRET_${sshKeySecretName} }}`,
        // Repository configuration
        REPO_NAME: repoName,
        REPO_ORG: repoOrg,
        REPO_BRANCH: repoBranch,
        REPO_STARTUP_CMD: startupCommand || "",
        // User-provided environment variables
        ...env
      },
      ports,
      dockerStartCmd: ["bash", "-c", this.buildDockerStartCommand(options)]
    }

    console.log(
      `[Attempt ${attemptNumber}] Creating pod with GPU type: ${gpuType}`
    )

    return await this.makeRequest<CreatePodResponse>("/pods", {
      method: "POST",
      body: JSON.stringify(podPayload)
    })
  }

  // --------------------------------------------------------------------------
  // Public API Methods
  // --------------------------------------------------------------------------

  /**
   * List all pods in the account
   */
  async listPods(): Promise<PodInfo[]> {
    const response = await this.makeRequest<ListPodsResponse>("/pods")
    return response.pods || []
  }

  /**
   * Get information about a specific pod
   */
  async getPod(podId: string): Promise<PodInfo> {
    return await this.makeRequest<PodInfo>(`/pods/${podId}`)
  }

  /**
   * Get the pod host ID for SSH proxy connection via GraphQL API
   * This is required for the correct SSH proxy connection format
   */
  async getPodHostId(podId: string): Promise<string | null> {
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

    try {
      const response = await fetch("https://api.runpod.io/graphql", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
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
        console.warn(`⚠️  Failed to fetch podHostId from GraphQL API`)
        return null
      }

      const data = await response.json()
      return data?.data?.pod?.machine?.podHostId || null
    } catch (error) {
      console.warn(`⚠️  Error fetching podHostId:`, error)
      return null
    }
  }

  /**
   * Terminate a pod
   */
  async terminatePod(podId: string): Promise<void> {
    await this.makeRequest<void>(`/pods/${podId}`, {
      method: "DELETE"
    })
  }

  /**
   * Wait for a pod to be ready with SSH access
   *
   * Polls the pod status until it's running with public IP and port mappings.
   * Also fetches the podHostId for SSH proxy connection.
   *
   * @param podId - The ID of the pod to wait for
   * @param pollIntervalMs - Polling interval in milliseconds (default: 5000)
   * @param maxPollAttempts - Maximum number of polling attempts (default: 60)
   * @returns Pod info and podHostId when ready
   * @throws Error if pod doesn't become ready in time
   */
  async waitForPodReady(
    podId: string,
    pollIntervalMs: number = 5000,
    maxPollAttempts: number = 60
  ): Promise<{ pod: PodInfo; podHostId: string }> {
    console.log("\n⏳ Waiting for pod to be ready...")

    for (let attempt = 1; attempt <= maxPollAttempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs))

      try {
        const pod = await this.getPod(podId)
        const isRunning = pod.desiredStatus === "RUNNING"
        const hasPublicIp = pod.publicIp !== null && pod.publicIp !== undefined
        const hasPortMappings = Object.keys(pod.portMappings || {}).length > 0

        if (isRunning && hasPublicIp && hasPortMappings) {
          const podHostId = await this.getPodHostId(podId)
          if (!podHostId) {
            throw new Error("Pod host ID not found after pod became ready")
          }
          console.log(
            `✅ Pod is ready! (attempt ${attempt}/${maxPollAttempts})`
          )
          return {
            pod,
            podHostId
          }
        }

        process.stdout.write(
          `\r   Attempt ${attempt}/${maxPollAttempts} booting pod...`
        )
      } catch (error) {
        console.log(`\n⚠️  Error checking pod status: ${error}`)
      }
    }

    throw new Error("Pod did not become ready in time")
  }

  /**
   * Create a worker pod with GPU availability retry logic
   *
   * This method will attempt to create a pod with the specified GPU types.
   * If a GPU type is unavailable (500 error), it will try the next one in
   * round-robin fashion until one succeeds or max retries is reached.
   */
  async createWorkerPod(options: CreatePodOptions): Promise<CreatePodResponse> {
    const { gpuTypes = ["NVIDIA RTX A4000"], maxRetries = 3 } = options

    if (gpuTypes.length === 0) {
      throw new Error("At least one GPU type must be specified")
    }

    let lastError: Error | null = null
    let attemptCount = 0
    const maxAttempts = Math.max(maxRetries, gpuTypes.length)

    // Round-robin through GPU types
    for (let i = 0; i < maxAttempts; i++) {
      const gpuType = gpuTypes[i % gpuTypes.length]
      attemptCount++

      try {
        const pod = await this.attemptCreatePod(options, gpuType, attemptCount)
        console.log("✅ Pod created successfully!")
        console.log(`   Pod ID: ${pod.id}`)
        console.log(`   Pod name: ${pod.name}`)
        console.log(`   GPU type: ${gpuType}`)
        return pod
      } catch (error) {
        lastError = error as Error
        const errorMessage =
          error instanceof Error ? error.message : String(error)

        // Check if it's a 500 error (likely GPU unavailability)
        const is500Error =
          error instanceof RunPodServiceError && error.status === 500
        const isGpuUnavailableError = errorMessage
          .toLowerCase()
          .includes(`no instances currently available`)

        if (is500Error && isGpuUnavailableError && i < maxAttempts - 1) {
          console.log(`Error: ${errorMessage}`)
          console.warn(
            `⚠️  GPU type "${gpuType}" unavailable (attempt ${attemptCount}/${maxAttempts}). Trying next GPU type...`
          )
          // Add a small delay before retrying
          await new Promise((resolve) => setTimeout(resolve, 1000))
          continue
        } else if (!is500Error || !isGpuUnavailableError) {
          // If it's not a 500 error, throw immediately (it's a different kind of error)
          console.log(`Error: ${errorMessage}`)
          throw error
        }
      }
    }

    // If we get here, all attempts failed
    throw new Error(
      `Failed to create pod after ${attemptCount} attempts. ` +
        `Tried GPU types: ${gpuTypes.join(", ")}. ` +
        `Last error: ${lastError?.message || "Unknown error"}`
    )
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

export interface SSHInfo {
  command: string | null
  port: number
  ip: string
}

/**
 * Extract SSH connection information from a pod
 *
 * @param pod - The pod information
 * @param podHostId - The pod host ID from GraphQL API
 * @returns SSH connection details or null if SSH port not mapped
 */
export function extractSSHInfo(
  pod: PodInfo,
  podHostId: string
): SSHInfo | null {
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

// ============================================================================
// Factory Function
// ============================================================================

/**
 * Create a new RunPod service instance
 */
export function createRunPodService(apiKey?: string): RunPodService {
  const key = apiKey || process.env.RUNPOD_API_KEY
  if (!key) {
    throw new Error(
      "RunPod API key must be provided or set in RUNPOD_API_KEY environment variable"
    )
  }
  return new RunPodService(key)
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Quick function to create a worker pod with minimal configuration
 */
export async function createSimpleWorkerPod(
  repoName: string,
  sshKeySecretName: string,
  startupCommand?: string,
  apiKey?: string
): Promise<CreatePodResponse> {
  const service = createRunPodService(apiKey)
  return service.createWorkerPod({
    repoName,
    sshKeySecretName,
    startupCommand
  })
}
