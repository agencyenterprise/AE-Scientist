import type {
  TreeVizItem,
  StageZone,
  StageZoneMetadata,
  MergedTreeVizPayload,
  MergedTreeViz,
} from "@/types/research";

// Re-export types for consumers that import from this module
export type { StageZoneMetadata, MergedTreeVizPayload, MergedTreeViz };

/**
 * Sort stages in chronological order (stage_1, stage_2, stage_3, stage_4)
 */
function sortStages(items: TreeVizItem[]): TreeVizItem[] {
  const order = ["stage_1", "stage_2", "stage_3", "stage_4"];
  return [...items].sort((a, b) => order.indexOf(a.stage_id) - order.indexOf(b.stage_id));
}

/**
 * Calculate vertical zones for each stage
 * Divides the viewBox into equal zones with padding between stages
 * Uses adaptive padding: 10% for 1-3 stages, 8% for 4+ stages
 */
function calculateStageZones(numStages: number): StageZone[] {
  if (numStages === 0) return [];

  const zoneHeight = 1.0 / numStages;

  // Adaptive padding: more stages = slightly less padding to preserve tree space
  const basePadding = 0.1;
  const padding = numStages >= 4 ? basePadding * 0.8 : basePadding;

  return Array.from({ length: numStages }, (_, i) => ({
    min: i * zoneHeight,
    max: (i + 1) * zoneHeight - padding,
  }));
}

/**
 * Transform layout coordinates to fit within a specific vertical zone
 */
function transformLayoutToZone(
  layout: Array<[number, number]>,
  zone: StageZone
): Array<[number, number]> {
  if (layout.length === 0) return [];

  // Find Y bounds
  const yValues = layout.map(([, y]) => y);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const rangeY = maxY - minY || 1; // Avoid division by zero

  // Transform to zone
  const zoneRange = zone.max - zone.min;

  return layout.map(([x, y]) => {
    const normalizedY = (y - minY) / rangeY; // Normalize to 0-1
    const transformedY = zone.min + normalizedY * zoneRange;
    return [x, transformedY];
  });
}

/**
 * Safely concatenate an optional parallel array
 */
function concatArray<T>(
  merged: T[],
  payload: Record<string, unknown>,
  key: string,
  defaultValue: T
): void {
  const array = payload[key] as T[] | undefined;
  if (array && Array.isArray(array)) {
    merged.push(...array);
  } else {
    // If array doesn't exist, fill with default values based on layout length
    const layoutLength = (payload.layout as Array<unknown>)?.length ?? 0;
    merged.push(...Array(layoutLength).fill(defaultValue));
  }
}

/**
 * Merge multiple TreeVizItem objects into a single unified tree
 */
export function mergeTreeVizItems(items: TreeVizItem[]): MergedTreeViz | null {
  if (items.length === 0) return null;

  // Sort stages chronologically
  const sorted = sortStages(items);

  // Calculate vertical zones
  const stageZones = calculateStageZones(sorted.length);

  // Initialize merged payload
  const merged: MergedTreeVizPayload = {
    layout: [],
    edges: [],
    stageIds: [],
    originalNodeIds: [],
    zoneMetadata: [],
    code: [],
    plan: [],
    analysis: [],
    metrics: [],
    exc_type: [],
    exc_info: [],
    exc_stack: [],
    plot_plan: [],
    plot_code: [],
    plot_analyses: [],
    plots: [],
    plot_paths: [],
    vlm_feedback_summary: [],
    datasets_successfully_tested: [],
    exec_time: [],
    exec_time_feedback: [],
    is_best_node: [],
    is_seed_node: [],
    is_seed_agg_node: [],
    ablation_name: [],
    hyperparam_name: [],
  };

  let globalNodeIndex = 0;

  // Track processed stages with their metadata
  const processedStages: Array<{
    stageId: string;
    stageIdx: number;
    globalOffset: number;
    nodeCount: number;
    payload: Record<string, unknown>;
  }> = [];

  // Merge each stage
  for (let stageIdx = 0; stageIdx < sorted.length; stageIdx++) {
    const item = sorted[stageIdx];
    const zone = stageZones[stageIdx];
    if (!item || !zone) continue;

    const payload = item.viz as Record<string, unknown>;

    const layout = payload.layout as Array<[number, number]> | undefined;
    if (!layout || layout.length === 0) {
      // Skip empty stages
      continue;
    }

    // Add zone metadata for this stage
    if (merged.zoneMetadata) {
      merged.zoneMetadata.push({
        stageIndex: stageIdx,
        stageId: item.stage_id,
        zone: zone,
      });
    }

    // Transform layout coordinates to fit in this stage's zone
    const transformedLayout = transformLayoutToZone(layout, zone);

    // Reindex edges to point to global node indices
    const edges = (payload.edges as Array<[number, number]>) || [];
    const offsetEdges = edges.map(
      ([parent, child]) => [parent + globalNodeIndex, child + globalNodeIndex] as [number, number]
    );

    // Merge layout and edges
    merged.layout.push(...transformedLayout);
    merged.edges.push(...offsetEdges);

    // Track stage info for each node
    const nodeCount = layout.length;
    merged.stageIds.push(...Array(nodeCount).fill(item.stage_id));
    merged.originalNodeIds.push(...Array.from({ length: nodeCount }, (_, i) => i));

    // Merge all parallel arrays
    if (merged.code) concatArray(merged.code, payload, "code", "");
    if (merged.plan) concatArray(merged.plan, payload, "plan", "");
    if (merged.analysis) concatArray(merged.analysis, payload, "analysis", "");
    if (merged.metrics) concatArray(merged.metrics, payload, "metrics", null);
    if (merged.exc_type) concatArray(merged.exc_type, payload, "exc_type", null);
    if (merged.exc_info) concatArray(merged.exc_info, payload, "exc_info", null);
    if (merged.exc_stack) concatArray(merged.exc_stack, payload, "exc_stack", null);
    if (merged.plot_plan) concatArray(merged.plot_plan, payload, "plot_plan", null);
    if (merged.plot_code) concatArray(merged.plot_code, payload, "plot_code", null);
    if (merged.plot_analyses) concatArray(merged.plot_analyses, payload, "plot_analyses", null);
    if (merged.plots) concatArray(merged.plots, payload, "plots", null);
    if (merged.plot_paths) concatArray(merged.plot_paths, payload, "plot_paths", null);
    if (merged.vlm_feedback_summary) {
      concatArray(merged.vlm_feedback_summary, payload, "vlm_feedback_summary", null);
    }
    if (merged.datasets_successfully_tested) {
      concatArray(
        merged.datasets_successfully_tested,
        payload,
        "datasets_successfully_tested",
        null
      );
    }
    if (merged.exec_time) concatArray(merged.exec_time, payload, "exec_time", null);
    if (merged.exec_time_feedback) {
      concatArray(merged.exec_time_feedback, payload, "exec_time_feedback", null);
    }
    if (merged.is_best_node) concatArray(merged.is_best_node, payload, "is_best_node", false);
    if (merged.is_seed_node) concatArray(merged.is_seed_node, payload, "is_seed_node", false);
    if (merged.is_seed_agg_node) {
      concatArray(merged.is_seed_agg_node, payload, "is_seed_agg_node", false);
    }
    if (merged.ablation_name) concatArray(merged.ablation_name, payload, "ablation_name", null);
    if (merged.hyperparam_name) {
      concatArray(merged.hyperparam_name, payload, "hyperparam_name", null);
    }

    // Record this stage's metadata for inter-stage connections
    processedStages.push({
      stageId: item.stage_id,
      stageIdx: stageIdx,
      globalOffset: globalNodeIndex,
      nodeCount: nodeCount,
      payload: payload,
    });

    globalNodeIndex += nodeCount;
  }

  // Connect stages: best node of Stage N → root node of Stage N+1
  for (let i = 0; i < processedStages.length - 1; i++) {
    const currentStage = processedStages[i];
    const nextStage = processedStages[i + 1];
    if (!currentStage || !nextStage) continue;

    // Find best node in current stage
    const isBestArray = currentStage.payload.is_best_node as boolean[] | undefined;
    const bestNodeLocalIdx = isBestArray?.findIndex(b => b === true) ?? -1;

    if (bestNodeLocalIdx < 0) continue; // Skip if no best node

    // Find root node in next stage (node with no incoming edges)
    const nextEdges = (nextStage.payload.edges as Array<[number, number]>) || [];
    const hasIncoming = new Set(nextEdges.map(([, child]) => child));

    let rootNodeLocalIdx = -1;
    for (let j = 0; j < nextStage.nodeCount; j++) {
      if (!hasIncoming.has(j)) {
        rootNodeLocalIdx = j;
        break;
      }
    }

    if (rootNodeLocalIdx < 0) continue; // Skip if no root found

    // Add connection edge (global indices)
    const bestNodeGlobal = currentStage.globalOffset + bestNodeLocalIdx;
    const rootNodeGlobal = nextStage.globalOffset + rootNodeLocalIdx;
    merged.edges.push([bestNodeGlobal, rootNodeGlobal]);
  }

  // Return merged tree viz
  const firstItem = sorted[0];
  const lastItem = sorted[sorted.length - 1];
  if (!firstItem || !lastItem) return null;

  return {
    id: -1, // Synthetic ID
    run_id: firstItem.run_id,
    stage_id: "full_tree",
    version: 1,
    viz: merged,
    created_at: firstItem.created_at,
    updated_at: lastItem.updated_at,
  };
}
