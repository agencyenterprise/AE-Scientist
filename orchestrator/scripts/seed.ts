import "dotenv/config"
import { randomUUID } from "node:crypto"
import { addMinutes, subHours, subMinutes } from "date-fns"
import { getDb, closeClient } from "@/lib/db/mongo"
import { createHypothesis } from "@/lib/repos/hypotheses.repo"
import { createRun } from "@/lib/repos/runs.repo"
import { createStage } from "@/lib/repos/stages.repo"
import { appendEvent } from "@/lib/repos/events.repo"
import { createArtifact } from "@/lib/repos/artifacts.repo"
import { createValidation } from "@/lib/repos/validations.repo"
import type { Stage } from "@/lib/schemas/stage"
import type { RunStatus } from "@/lib/state/constants"

async function main() {
  await purgeSeededDocuments()

  const hypotheses = await Promise.all([
    createHypothesis({
      _id: randomUUID(),
      title: "Self-Refining RLHF with Sparse Rewards",
      idea: "Prototype a self-improving RLHF loop that protects against sparse reward collapse.",
      ideaJson: {
        Name: "self_refining_rlhf_with_sparse_rewards",
        Title: "Self-Refining RLHF with Sparse Rewards",
        "Short Hypothesis": "Prototype a self-improving RLHF loop that protects against sparse reward collapse.",
        Abstract: "Prototype a self-improving RLHF loop that protects against sparse reward collapse.",
        Experiments: ["Implement self-refining mechanism", "Test on sparse reward environments", "Evaluate stability metrics"],
        "Risk Factors and Limitations": ["Computational overhead", "Convergence guarantees"]
      },
      createdAt: subHours(new Date(), 24),
      createdBy: "seed",
      seed: true
    }),
    createHypothesis({
      _id: randomUUID(),
      title: "Autonomous Agent Literature Miner",
      idea: "Mine recent arXiv papers to generate structured agendas for foundation model research.",
      ideaJson: {
        Name: "autonomous_agent_literature_miner",
        Title: "Autonomous Agent Literature Miner",
        "Short Hypothesis": "Mine recent arXiv papers to generate structured agendas for foundation model research.",
        Abstract: "Mine recent arXiv papers to generate structured agendas for foundation model research.",
        Experiments: ["Implement paper mining system", "Test agenda generation", "Evaluate relevance metrics"],
        "Risk Factors and Limitations": ["API rate limits", "Quality of extracted data"]
      },
      createdAt: subHours(new Date(), 48),
      createdBy: "seed",
      seed: true
    }),
    createHypothesis({
      _id: randomUUID(),
      title: "GPU Scheduling via LLM Planner",
      idea: "Use an LLM planner to predict GPU allocation for long-running research experiments.",
      ideaJson: {
        Name: "gpu_scheduling_via_llm_planner",
        Title: "GPU Scheduling via LLM Planner",
        "Short Hypothesis": "Use an LLM planner to predict GPU allocation for long-running research experiments.",
        Abstract: "Use an LLM planner to predict GPU allocation for long-running research experiments.",
        Experiments: ["Implement LLM-based scheduler", "Test on real workloads", "Compare with baseline schedulers"],
        "Risk Factors and Limitations": ["Prediction accuracy", "Real-time performance"]
      },
      createdAt: subHours(new Date(), 12),
      createdBy: "seed",
      seed: true
    })
  ])

  const [h1, h2, h3] = hypotheses

  await Promise.all([
    seedRun({
      hypothesisId: h1._id,
      status: "RUNNING",
      currentStage: { name: "Stage_2", progress: 0.6 },
      createdOffsetMinutes: 180,
      events: 5
    }),
    seedRun({
      hypothesisId: h1._id,
      status: "AWAITING_HUMAN",
      currentStage: { name: "Stage_4", progress: 1 },
      createdOffsetMinutes: 360,
      includeAutoValidation: true,
      includeArtifact: true
    }),
    seedRun({
      hypothesisId: h2._id,
      status: "HUMAN_VALIDATED",
      createdOffsetMinutes: 720,
      includeAutoValidation: true,
      includeHumanValidation: true,
      includeArtifact: true
    }),
    seedRun({
      hypothesisId: h3._id,
      status: "FAILED",
      createdOffsetMinutes: 90,
      failureReason: "Stage_3 baseline metrics diverged"
    })
  ])

  console.info("Seeded demo data. All records flagged with seed=true.")
  await closeClient()
}

async function purgeSeededDocuments() {
  const db = await getDb()
  const collections = ["runs", "stages", "events", "validations", "artifacts", "hypotheses"]
  for (const name of collections) {
    await db.collection(name).deleteMany({ seed: true })
  }
}

async function seedRun(options: {
  hypothesisId: string
  status: RunStatus
  createdOffsetMinutes: number
  currentStage?: { name: Stage["name"]; progress: number }
  includeAutoValidation?: boolean
  includeHumanValidation?: boolean
  includeArtifact?: boolean
  events?: number
  failureReason?: string
}) {
  const {
    hypothesisId,
    status,
    createdOffsetMinutes,
    currentStage,
    includeAutoValidation,
    includeHumanValidation,
    includeArtifact,
    events = 0,
    failureReason
  } = options

  const createdAt = subMinutes(new Date(), createdOffsetMinutes)
  const runId = randomUUID()
  const stageContext = currentStage ?? (status === "FAILED" ? { name: "Stage_3", progress: 0.4 } : undefined)

  await createRun({
    _id: runId,
    hypothesisId,
    status,
    currentStage: stageContext,
    createdAt,
    updatedAt: createdAt,
    seed: true,
    pod: status === "RUNNING" ? { id: `seed-pod-${runId}`, instanceType: "A100.80" } : undefined
  })

  const stageBlueprint: Array<Stage> = [
    {
      _id: randomUUID(),
      runId,
      index: 0,
      name: "Stage_1",
      status: stageStatus(status, 0, stageContext?.name),
      progress: progressValue(stageContext, "Stage_1"),
      startedAt: createdAt,
      completedAt: completedTimestamp(createdAt, status, 0, stageContext?.name),
      seed: true
    },
    {
      _id: randomUUID(),
      runId,
      index: 1,
      name: "Stage_2",
      status: stageStatus(status, 1, stageContext?.name),
      progress: progressValue(stageContext, "Stage_2"),
      startedAt: addMinutes(createdAt, 45),
      completedAt: completedTimestamp(createdAt, status, 1, stageContext?.name),
      seed: true
    },
    {
      _id: randomUUID(),
      runId,
      index: 2,
      name: "Stage_3",
      status: stageStatus(status, 2, stageContext?.name),
      progress: progressValue(stageContext, "Stage_3"),
      startedAt: addMinutes(createdAt, 90),
      completedAt: completedTimestamp(createdAt, status, 2, stageContext?.name),
      summary: failureReason && status === "FAILED" ? failureReason : undefined,
      seed: true
    },
    {
      _id: randomUUID(),
      runId,
      index: 3,
      name: "Stage_4",
      status: stageStatus(status, 3, stageContext?.name),
      progress: progressValue(stageContext, "Stage_4"),
      startedAt: addMinutes(createdAt, 135),
      completedAt: completedTimestamp(createdAt, status, 3, stageContext?.name),
      seed: true
    }
  ]

  await Promise.all(stageBlueprint.map((stage) => createStage(stage)))

  await Promise.all(
    Array.from({ length: events }).map((_, index) =>
      appendEvent({
        _id: randomUUID(),
        runId,
        timestamp: subMinutes(new Date(), index * 10),
        type: "stage_progress",
        data: {},
        source: "seed",
        message: `Seed progress event ${index + 1}`,
        payload: { step: index + 1 },
        level: "info",
        seed: true
      })
    )
  )

  if (includeArtifact) {
    await createArtifact({
      _id: randomUUID(),
      runId,
      key: `${runId}/report.pdf`,
      uri: `https://example.com/${runId}/report.pdf`,
      size: 1024 * 1024 * 2,
      createdAt: subMinutes(new Date(), 15),
      seed: true
    })
  }

  if (includeAutoValidation) {
    await createValidation({
      _id: randomUUID(),
      runId,
      kind: "auto",
      verdict: "pass",
      rubric: {
        claims_supported: 0.82,
        stats_sane: 0.77,
        novelty: 0.65
      },
      createdAt: subMinutes(new Date(), 20),
      createdBy: "seed",
      seed: true
    })
  }

  if (includeHumanValidation) {
    await createValidation({
      _id: randomUUID(),
      runId,
      kind: "human",
      verdict: "pass",
      notes: "Looks solid for publication.",
      createdAt: subMinutes(new Date(), 5),
      createdBy: "reviewer.seed",
      seed: true
    })
  }
}

function stageStatus(status: RunStatus, index: number, currentStageName?: Stage["name"]) {
  if (status === "FAILED" && currentStageName && stageIndex(currentStageName) === index) {
    return "FAILED"
  }
  if (status === "FAILED" && stageIndex(currentStageName ?? "Stage_1") > index) {
    return "COMPLETED"
  }
  if (status === "RUNNING" && currentStageName && stageIndex(currentStageName) === index) {
    return "RUNNING"
  }
  if (["HUMAN_VALIDATED", "AWAITING_HUMAN", "AUTO_VALIDATING"].includes(status)) {
    return "COMPLETED"
  }
  if (["QUEUED", "SCHEDULED", "STARTING"].includes(status) && index === 0) {
    return "RUNNING"
  }
  return index < stageIndex(currentStageName ?? "Stage_1") ? "COMPLETED" : "PENDING"
}

function progressValue(
  currentStage: { name: Stage["name"]; progress: number } | undefined,
  stage: Stage["name"]
) {
  if (!currentStage) return 1
  if (currentStage.name === stage) return currentStage.progress
  return stageIndex(currentStage.name) > stageIndex(stage) ? 1 : 0
}

function completedTimestamp(
  createdAt: Date,
  status: RunStatus,
  index: number,
  currentStageName?: Stage["name"]
) {
  if (["HUMAN_VALIDATED", "AWAITING_HUMAN", "AUTO_VALIDATING"].includes(status)) {
    return addMinutes(createdAt, (index + 1) * 45)
  }
  if (status === "RUNNING" && currentStageName && stageIndex(currentStageName) > index) {
    return addMinutes(createdAt, (index + 1) * 45)
  }
  if (status === "FAILED" && currentStageName && stageIndex(currentStageName) > index) {
    return addMinutes(createdAt, (index + 1) * 45)
  }
  return undefined
}

function stageIndex(stage: Stage["name"]) {
  return ["Stage_1", "Stage_2", "Stage_3", "Stage_4"].indexOf(stage)
}

main().catch(async (error) => {
  console.error("Failed to seed database", error)
  await closeClient()
  process.exit(1)
})
