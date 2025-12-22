/**
 * Node Strategy Guide Data
 *
 * This file contains descriptions of how the BFTS algorithm decides which node to explore
 * next in each stage, along with the configuration values that control the behavior.
 *
 * IMPORTANT: Keep config values in sync with research_pipeline/bfts_config_template.yaml (lines 71-75)
 * If you update the YAML, update these values here as well to ensure the UI stays current.
 */

export const SEARCH_CONFIG = {
  num_drafts: 3,
  debug_prob: 0.7,
  max_debug_depth: 5,
} as const;

export interface Phase {
  name: string;
  description: string;
  trigger: string;
  configValues: string[];
  action: string;
  selectionCriteria: string[];
}

export interface StageStrategy {
  title: string;
  goal: string;
  description: string;
  nodeSelectionStrategy: {
    overview: string;
    phases: Phase[];
  };
  exampleFlow: string;
}

export type StageId = "Stage_1" | "Stage_2" | "Stage_3" | "Stage_4";

export const STAGE_STRATEGIES: Record<StageId, StageStrategy> = {
  Stage_1: {
    title: "Stage 1: Baseline Implementation",
    goal: "Develop functional code which can produce a runnable result",
    description:
      "The AI scientist generates initial implementations and iteratively debugs failures to achieve a working baseline. The strategy balances exploration (trying multiple approaches) with exploitation (improving the best solutions found).",
    nodeSelectionStrategy: {
      overview:
        "Stage 1 uses a combination of exploration (drafting new implementations) and exploitation (debugging failures or improving working code). The decision-making process follows three phases that work together to efficiently search the implementation space.",
      phases: [
        {
          name: "Drafting Phase",
          description:
            "Initial new implementations are generated from scratch. This exploration phase ensures the search space is adequately explored before committing to optimization of any single approach.",
          trigger: `When draft_nodes count < ${SEARCH_CONFIG.num_drafts}`,
          configValues: [`num_drafts: ${SEARCH_CONFIG.num_drafts}`],
          action: "Generate a new root node (exploration)",
          selectionCriteria: [
            "Always create new drafts until reaching target count",
            "Ensures sufficient starting points before optimizing",
          ],
        },
        {
          name: "Debugging Phase",
          description:
            "Failed implementations (buggy nodes) are selected for debugging attempts. This is controlled by a probability mechanism that prevents the algorithm from getting stuck optimizing one path while ignoring potentially better alternatives. The depth limit prevents infinite debugging loops.",
          trigger: `When random() < ${SEARCH_CONFIG.debug_prob} (${Math.round(SEARCH_CONFIG.debug_prob * 100)}% of the time)`,
          configValues: [
            `debug_prob: ${SEARCH_CONFIG.debug_prob} (${Math.round(SEARCH_CONFIG.debug_prob * 100)}% chance of debugging)`,
            `max_debug_depth: ${SEARCH_CONFIG.max_debug_depth} (max iterations per node)`,
          ],
          action: "Select a buggy leaf node and attempt fixes",
          selectionCriteria: [
            "Must be a leaf node (not yet processed/has no children)",
            `debug_depth must be ≤ ${SEARCH_CONFIG.max_debug_depth} to prevent infinite loops`,
            "Avoid processing the same tree twice in parallel to maintain diversity",
            "Choose from available buggy nodes randomly",
          ],
        },
        {
          name: "Improvement Phase",
          description:
            "Working implementations are refined and optimized. Uses best-first search to prioritize the most promising implementations while maintaining diversity through parallel processing.",
          trigger: `When ${Math.round((1 - SEARCH_CONFIG.debug_prob) * 100)}% of the time (or no debugging opportunities)`,
          configValues: [],
          action: "Select best performing node and create improvements",
          selectionCriteria: [
            "Choose best node by metric (highest accuracy/lowest loss)",
            "Prioritize unprocessed trees to maintain diversity",
            "Fall back to next-best nodes if best tree already in processing queue",
            "Uses LLM evaluation when multiple candidates have similar metrics",
          ],
        },
      ],
    },
    exampleFlow: `1. Generate ${SEARCH_CONFIG.num_drafts} initial draft implementations (exploration)
2. For each subsequent iteration, either:
   a. (${Math.round(SEARCH_CONFIG.debug_prob * 100)}% chance) Debug a failed implementation (up to ${SEARCH_CONFIG.max_debug_depth} attempts)
   b. (${Math.round((1 - SEARCH_CONFIG.debug_prob) * 100)}% chance) Improve the best working implementation
3. Continue until stage completion criteria are met (working implementation + sufficient exploration)`,
  },

  Stage_2: {
    title: "Stage 2: Baseline Tuning",
    goal: "Improve baseline through hyperparameter optimization",
    description:
      "The AI scientist systematically explores hyperparameter variations of the best Stage 1 implementation. Stage 2 always processes the best Stage 1 node but may generate different types of child nodes (Hyperparameter Tuning, Improve, or Seed nodes) depending on parent state and evaluation progress. This ensures the stage handles failures gracefully while prioritizing hyperparameter optimization.",
    nodeSelectionStrategy: {
      overview:
        "Stage 2 always selects the best Stage 1 node for processing. However, it creates different node types based on parent node state. When a parent is working (not buggy), it creates Hyperparameter Tuning nodes that propose new parameter ideas. When a parent node is buggy, it creates Improve nodes to fix the bugs so tuning can continue. After Stage 2 completes, Seed nodes run the best solution with different random seeds to validate that improvements generalize.",
      phases: [
        {
          name: "Hyperparameter Tuning (Primary)",
          description:
            "Systematic exploration of hyperparameter combinations. When the parent node is working correctly, new hyperparameter ideas are generated (learning rate, batch size, epochs, regularization, etc.). Each iteration proposes new parameter values based on analysis of previous results and measured improvements.",
          trigger: "When parent node is NOT buggy (healthy)",
          configValues: [],
          action: "Generate and apply hyperparameter tuning idea to Stage 1 baseline",
          selectionCriteria: [
            "Always use best_stage1_node as parent",
            "Only create hyperparameter tuning nodes if parent code is working",
            "Propose distinct hyperparameter ideas (avoid repeating previous tries)",
            "Apply tuning to exact Stage 1 code without architecture changes",
            "Evaluate impact on test metrics across datasets",
          ],
        },
        {
          name: "Improve Node (Recovery)",
          description:
            "When the parent node becomes buggy or fails to run, Improve nodes attempt to fix the code. This is a recovery mechanism that allows Stage 2 to overcome bugs and continue with hyperparameter tuning in subsequent iterations. The improvement uses general code refinement rather than hyperparameter-specific logic.",
          trigger: "When parent node IS buggy or exception occurs during execution",
          configValues: [],
          action: "Attempt to fix bugs in parent implementation",
          selectionCriteria: [
            "Created as fallback when hyperparameter tuning fails",
            "Uses general improvement prompt to fix issues",
            "Allows Stage 2 to recover and resume tuning in next iteration",
            "Preserves original algorithm structure while fixing bugs",
          ],
        },
        {
          name: "Seed Nodes (Robustness Validation)",
          description:
            "After Stage 2 completes and a best hyperparameter configuration is found, Seed nodes run the same code with different random initializations. This validates that the performance improvements are robust and not due to luck with a particular random seed. Multiple seed runs provide error bars and statistical confidence.",
          trigger: "After Stage 2 completion during multi-seed evaluation phase",
          configValues: [],
          action: "Run best Stage 2 node code with N different random seeds",
          selectionCriteria: [
            "Run identical code with different random initializations",
            "Aggregate results across seeds to compute mean and confidence intervals",
            "Validate that hyperparameter improvements generalize",
            "Create aggregation node to summarize multi-seed results",
          ],
        },
      ],
    },
    exampleFlow: `1. Select best implementation from Stage 1 (the anchor point)
2. For each iteration, either:
   a. Parent is working → Create HYPERPARAMETER TUNING node
      - Propose new hyperparameter idea
      - Apply to Stage 1 baseline
      - Evaluate and measure improvement
   b. Parent is buggy → Create IMPROVE node
      - Attempt to fix bugs
      - Allow Stage 2 to recover
      - Continue tuning in next iteration
3. After Stage 2 completes:
   a. Create SEED NODES (e.g., 3-5 runs with different random seeds)
   b. Run multi-seed evaluation
   c. Create AGGREGATION NODE with results summary
4. Best hyperparameter configuration now validated across random initializations`,
  },

  Stage_3: {
    title: "Stage 3: Creative Exploration",
    goal: "Explore higher-leverage variants with supporting analysis",
    description:
      "The AI scientist generates creative variants and explores new research directions with empirical validation. Unlike Stage 1's focus on basic functionality, Stage 3 proposes more ambitious changes (new architectures, novel techniques) and backs them up with analysis (plots, ablations, comparisons).",
    nodeSelectionStrategy: {
      overview:
        "Stage 3 returns to exploration/exploitation dynamics similar to Stage 1, but with a focus on higher-leverage conceptual variations rather than basic debugging. The selection strategy emphasizes both performance metrics and analysis quality.",
      phases: [
        {
          name: "Exploration Phase",
          description:
            "New creative variants are explored alongside systematic refinement of working approaches. This phase balances trying new ideas with improving promising directions.",
          trigger: "Standard best-first search with creative variation generation",
          configValues: [
            `num_drafts: ${SEARCH_CONFIG.num_drafts}`,
            `debug_prob: ${SEARCH_CONFIG.debug_prob}`,
          ],
          action: "Explore creative variants with supporting analysis and plots",
          selectionCriteria: [
            "Use best-first tree search over creative variants",
            "Prioritize nodes with supporting plots/analyses",
            "Consider both metrics and VLM (visual language model) feedback on plots",
            "Focus on variants that represent conceptual improvements, not just parameter tweaks",
          ],
        },
      ],
    },
    exampleFlow: `1. Generate initial creative variants (exploration - architecture changes, novel techniques)
2. For each iteration, either:
   a. Debug failed variants (less common in Stage 3)
   b. Improve successful variants with deeper analysis (generate plots, comparisons)
3. Selection based on both metrics and analysis quality (not just accuracy numbers)
4. Continue until strong research ideas are exhausted`,
  },

  Stage_4: {
    title: "Stage 4: Ablation Studies",
    goal: "Run controlled ablations to understand component contributions",
    description:
      "The AI scientist performs controlled ablation studies on the best Stage 3 implementation to isolate the importance of individual components. This provides insight into which parts of the solution are critical versus optional.",
    nodeSelectionStrategy: {
      overview:
        "Stage 4 anchors all work to the best Stage 3 node, systematically removing or modifying specific components to measure their contribution to overall performance. This is a systematic analysis phase, not an exploration phase.",
      phases: [
        {
          name: "Component Ablation",
          description:
            "Each iteration systematically removes or modifies a specific component to measure its performance impact. This helps identify which components are critical versus redundant.",
          trigger: "Always - Stage 4 is dedicated to ablation studies",
          configValues: [],
          action: "Apply ablation variation to best Stage 3 node",
          selectionCriteria: [
            "Always use best_stage3_node as the baseline",
            "Generate ablation variations for different components",
            "Measure performance delta for each ablation",
            "Track which components are most critical to performance",
            "Test statistical significance of results",
          ],
        },
      ],
    },
    exampleFlow: `1. Select best implementation from Stage 3
2. For each component in the implementation:
   - Create variant with that component removed/disabled
   - Run with and without the component
   - Measure performance difference
   - Document importance of the component
3. Provide analysis of which components drive improvements
4. Identify core components vs. nice-to-have optimizations`,
  },
};

export function getStageStrategy(stageId: string): StageStrategy | null {
  const normalizedId = stageId as StageId;
  return STAGE_STRATEGIES[normalizedId] || null;
}
