Research Idea Title:
Trojan LoRAs: Measuring the Implantability, Persistence, and Detectability of
Covert Behavioral Backdoors in Shared Fine-Tuning Adapters

Research Idea Details:

Objective:
The explosive growth of LoRA-based fine-tuning has created a vast, largely unaudited
ecosystem of shared adapters (HuggingFace alone hosts hundreds of thousands). This
project investigates whether a malicious actor can implant covert behavioral backdoors
into LoRA adapters that: (1) remain entirely invisible to standard safety benchmarks
and capability evaluations, (2) activate only under semantically-defined trigger
conditions (e.g., specific user demographics, query topics, or conversational contexts)
rather than explicit token triggers, and (3) resist detection via weight-space auditing
tools currently used or proposed by model hubs. We further develop and evaluate a
suite of adapter auditing defenses.

Expected Insights:
We hypothesize the existence of a "stealth-performance Pareto frontier" — adapter
configurations that maximally embed covert behavior while minimally degrading scores
on standard safety suites (MT-Bench, HarmBench, TruthfulQA). We expect semantic
triggers to be dramatically harder to detect than token-level triggers, since they
leave no discrete signature in the weight delta and require behavioral probing rather
than static analysis to surface. On the defense side, we predict that singular value
decomposition analysis of adapter weight deltas will detect structural anomalies in
naive backdoors, but that adversarially-optimized adapters can evade this via
rank-preserving perturbation — forcing defenders toward behavioral red-teaming, which
is expensive and incomplete.

Why It Matters:
Fine-tuning-as-a-service is now a standard enterprise AI deployment pattern. Companies
routinely download and deploy community LoRAs for cost, latency, or capability reasons
without the infrastructure to audit them. Unlike runtime inference-time attacks, a
backdoored LoRA is baked into the model weights, persists across deployments, survives
quantization, and can be distributed at scale through trusted channels (model hubs,
fine-tuning API outputs). The attack surface is the entire open-weights ecosystem.
Current model hub safety reviews rely on behavioral spot-checks — the same evaluations
we demonstrate are insufficient. This work provides the first systematic empirical
measurement of the gap between "passes safety benchmarks" and "is safe," and proposes
auditing methods that could realistically be deployed by Hugging Face, Replicate, or
enterprise model registries.

Methodology Improvements Over Prior Backdoor Work:
Existing LLM backdoor literature focuses on token-level triggers (rare words, special
characters) and full fine-tuning rather than adapter-based attacks. This project
advances the field on five axes: (a) semantic trigger design — backdoors conditioned
on embedding-space proximity rather than exact token matches, enabling context-sensitive
activation that evades trigger-scanning defenses; (b) cross-base-model transferability
experiments testing whether a backdoor implanted into Llama-3-8B transfers when the
LoRA is applied to Llama-3-70B or Mistral-7B; (c) quantization survival analysis
across GGUF Q4/Q8 and GPTQ compression schemes; (d) a realistic adversarial setting
where the implanter has only black-box access to the downstream deployment pipeline;
and (e) open-source release of a LoRA Auditing Toolkit including weight-delta anomaly
detectors, behavioral red-teaming probes, and a standardized backdoor benchmark suite
for future research.
