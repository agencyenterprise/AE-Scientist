import { randomUUID } from "node:crypto"
import { PaperAnalysisZ, type PaperAnalysis } from "../lib/schemas/analysis"

const polyphaseCFDRAPaperExample: PaperAnalysis = {
  _id: randomUUID(),
  runId: randomUUID(),
  paperId: "polyphase_cfdra_iclr2025",
  paperTitle: "Polyphase CFDRA: Multirate Convolution for Long-Context Learning",
  quantitative: {
    quality: {
      score: 8.1,
      criteria: {
        clarity: 8.5,
        experimentalRigor: 9.0,
        novelty: 7.5,
        reproducibility: 9.5,
        resultSignificance: 6.5,
        writingQuality: 8.0
      },
      rationale: "Paper is well written and rigorously tested, but its practical gains are limited in long-context learning despite high technical fidelity."
    },
    faithfulnessToOriginal: {
      score: 9.8,
      rationale: "The experiment precisely reproduced its design goals — exactness and efficiency — with machine-precision equivalence to the baseline CFDRA."
    },
    innovationIndex: {
      score: 7.0,
      rationale: "Introduces multirate FFT convolution with learned strides, which is novel, but the conceptual step builds directly on CFDRA without expanding modeling capabilities."
    },
    computationalEfficiencyGain: {
      tokensPerSecond: 37000000,
      relativeGainVsBaseline: "1.3x–1.6x depending on stride usage",
      nmseExactness: "4.5e-13–7.5e-13",
      memorySavingsEstimated: "25–60%",
      rationale: "Efficiency improved through multirate FFTs without loss of precision."
    },
    empiricalSuccess: {
      datasetsWithImprovement: 1,
      datasetsTested: 3,
      successRate: 0.33,
      rationale: "Only AG News showed a clear context-length improvement; others failed to extend ECL."
    },
    reliabilityOfConclusion: {
      score: 8.5,
      rationale: "Findings are consistent and transparently reported with numerical cross-validation, even when results were negative."
    },
    reproducibilityScore: {
      codeAvailability: true,
      numericalCheckIncluded: true,
      score: 9.5
    },
    overallScore: 8.0
  },
  qualitative: {
    tradeoffsMade: {
      efficiencyVsMemory: "Chose to prioritize exactness and computational efficiency over achieving guaranteed long-context generalization.",
      complexityVsTrainingSignal: "Simplified multirate implementation led to insufficient long-context supervision.",
      precisionVsFlexibility: "Maintained bit-exactness at the cost of introducing additional FFT overhead complexity.",
      interpretabilityVsScalability: "Preserved interpretability (resonant modes) while scaling to longer sequences; some flexibility sacrificed in training behavior."
    },
    experimentProven: {
      hypothesis: "Multirate polyphase convolution can be implemented exactly and efficiently within the CFDRA framework.",
      proven: true,
      evidence: "Machine-precision NMSE, stable throughput, and preserved optimization landscape confirmed exactness.",
      limitations: "Hypothesis did not extend to effective long-context retention without specialized supervision."
    },
    conclusion: {
      summary: "Polyphase CFDRA delivers numerical exactness and efficiency but fails to automatically extend effective memory. The architecture works perfectly as designed but lacks the training signal to realize its theoretical benefits.",
      implications: "Highlights a broader issue in long-context models: architecture-level improvements don't yield longer memory without explicit long-range objectives.",
      authorsPosition: "A cautionary case study in method engineering — a success in systems design, not in emergent modeling behavior."
    },
    methodologicalNovelty: "First exact implementation of learned per-mode multirate FFT convolution preserving autoregressive state form.",
    recommendations: [
      "Add explicit long-context training objectives or recurrence regularization.",
      "Bias slow modes toward higher strides through stronger priors.",
      "Optimize FFT batching to reduce planning overheads."
    ]
  },
  models: {
    quantitative: "gpt-4.1-mini",
    qualitative: "gpt-4.1-mini"
  },
  createdAt: new Date()
}

async function validateAnalysisSchema() {
  console.log("🔍 Validating Paper Analysis Schema...\n")

  try {
    const validated = PaperAnalysisZ.parse(polyphaseCFDRAPaperExample)
    console.log("✅ Schema validation PASSED\n")
    
    console.log("📊 Quantitative Analysis Structure:")
    console.log("  ✓ quality (score, criteria, rationale)")
    console.log("  ✓ faithfulnessToOriginal")
    console.log("  ✓ innovationIndex")
    console.log("  ✓ computationalEfficiencyGain")
    console.log("  ✓ empiricalSuccess (datasetsWithImprovement, datasetsTested, successRate)")
    console.log("  ✓ reliabilityOfConclusion")
    console.log("  ✓ reproducibilityScore (codeAvailability, numericalCheckIncluded)")
    console.log("  ✓ overallScore\n")
    
    console.log("🧭 Qualitative Analysis Structure:")
    console.log("  ✓ tradeoffsMade (flexible key-value pairs)")
    console.log("  ✓ experimentProven (hypothesis, proven, evidence, limitations)")
    console.log("  ✓ conclusion (summary, implications, authorsPosition)")
    console.log("  ✓ methodologicalNovelty")
    console.log("  ✓ recommendations (array)\n")
    
    console.log("📈 Sample Output (Polyphase CFDRA):")
    console.log(`  Overall Score: ${validated.quantitative.overallScore}`)
    console.log(`  Quality Score: ${validated.quantitative.quality?.score}`)
    console.log(`  Success Rate: ${(validated.quantitative.empiricalSuccess?.successRate ?? 0) * 100}%`)
    console.log(`  Proven: ${validated.qualitative.experimentProven?.proven ? "Yes" : "No"}`)
    console.log(`  Recommendations: ${validated.qualitative.recommendations?.length ?? 0} items\n`)
    
    console.log("✅ All fields match the expected schema from the requirements!")
    return true
  } catch (error) {
    console.error("❌ Schema validation FAILED:")
    console.error(error)
    return false
  }
}

validateAnalysisSchema().then(success => {
  process.exit(success ? 0 : 1)
})

