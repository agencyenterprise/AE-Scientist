/**
 * Tree visualization color and styling configuration
 * Centralized configuration for node colors and border styles
 */

import { normalizeStageId } from "@/shared/lib/stage-utils";

export enum NodeType {
  Root = "root",
  Debug = "debug",
  Improve = "improve",
  Hyperparam = "hyperparam",
  Ablation = "ablation",
  SeedNode = "seed_node",
}

export enum BorderStyle {
  Normal = "normal",
  Best = "best",
  Failed = "failed",
  Selected = "selected",
}

interface NodeTypeConfig {
  color: string;
  label: string;
}

interface NodeColors {
  [NodeType.Root]: NodeTypeConfig;
  [NodeType.Debug]: NodeTypeConfig;
  [NodeType.Improve]: NodeTypeConfig;
  [NodeType.Hyperparam]: NodeTypeConfig;
  [NodeType.Ablation]: NodeTypeConfig;
  [NodeType.SeedNode]: NodeTypeConfig;
}

interface BorderConfig {
  stroke: string;
  strokeWidth: string;
}

interface BorderStyles {
  [BorderStyle.Normal]: BorderConfig;
  [BorderStyle.Best]: BorderConfig;
  [BorderStyle.Failed]: BorderConfig;
  [BorderStyle.Selected]: BorderConfig;
}

/**
 * Node type colors - consistent across all stages
 * Customize these colors to change how node types appear in the visualization
 */
export const NODE_TYPE_COLORS: NodeColors = {
  [NodeType.Root]: {
    color: "#1E40AF", // Darker blue
    label: "Root Node",
  },
  [NodeType.Debug]: {
    color: "#6366F1", // Indigo - neutral, distinct from failure status
    label: "Debug",
  },
  [NodeType.Improve]: {
    color: "#0284C7", // Sky blue
    label: "Improve",
  },
  [NodeType.Hyperparam]: {
    color: "#A855F7", // Purple
    label: "Hyperparameter Tuning",
  },
  [NodeType.Ablation]: {
    color: "#D97706", // Orange
    label: "Ablation Study",
  },
  [NodeType.SeedNode]: {
    color: "#92400E", // Brown
    label: "Seed Node",
  },
};

/**
 * Border styles - indicate node quality/status
 * Adjust strokeWidth values to make borders more/less prominent in the visualization
 */
export const BORDER_STYLES: BorderStyles = {
  [BorderStyle.Normal]: {
    stroke: "#0f172a",
    strokeWidth: "1.2",
  },
  [BorderStyle.Best]: {
    stroke: "#065F46",
    strokeWidth: "1.2",
  },
  [BorderStyle.Failed]: {
    stroke: "#DC2626",
    strokeWidth: "1.2",
  },
  [BorderStyle.Selected]: {
    stroke: "#fbbf24",
    strokeWidth: "1.2",
  },
};

interface Node {
  excType?: string | null;
  isBest?: boolean;
  isSeedNode?: boolean;
  isSeedAggNode?: boolean;
  ablationName?: string | null;
  hyperparamName?: string | null;
}

interface NodesContext {
  nodes: Array<Node>;
  edges: Array<[number, number]>;
}

/**
 * Infer node type from node properties
 */
export function getNodeType(nodeIdx: number, context: NodesContext): NodeType {
  const node = context.nodes[nodeIdx];
  if (!node) return NodeType.Improve;

  // Check explicit type flags first
  if (node.isSeedNode) return NodeType.SeedNode;
  if (node.ablationName) return NodeType.Ablation;
  if (node.hyperparamName) return NodeType.Hyperparam;

  // Determine Root vs Debug vs Improve from parent relationships
  const parentIdx = context.edges.find(([, child]) => child === nodeIdx)?.[0];

  if (parentIdx === undefined) {
    // No incoming edge = Root node
    return NodeType.Root;
  }

  // Has parent - check if parent is buggy
  const parentNode = context.nodes[parentIdx];
  if (parentNode?.excType) {
    // Parent failed = this node is attempting to debug
    return NodeType.Debug;
  }

  // Parent succeeded = this node is an improvement
  return NodeType.Improve;
}

/**
 * Determine border style based on node quality
 */
export function getBorderStyle(node: Node): BorderStyle {
  if (node.excType) return BorderStyle.Failed;
  if (node.isBest) return BorderStyle.Best;
  return BorderStyle.Normal;
}

/**
 * Get stage-relevant node types
 * Returns only node types that can appear in a given stage
 */
export function getStageRelevantNodeTypes(stageId?: string): NodeType[] {
  if (!stageId) return Object.values(NodeType);

  // Normalize to lowercase format for consistent matching
  const normalized = normalizeStageId(stageId);

  switch (normalized) {
    case "stage_1":
      return [NodeType.Root, NodeType.Debug, NodeType.Improve, NodeType.SeedNode];
    case "stage_2":
      return [
        NodeType.Root,
        NodeType.Debug,
        NodeType.Improve,
        NodeType.Hyperparam,
        NodeType.SeedNode,
      ];
    case "stage_3":
      return [NodeType.Debug, NodeType.Improve, NodeType.SeedNode];
    case "stage_4":
      return [NodeType.Improve, NodeType.Ablation, NodeType.SeedNode];
    default:
      return Object.values(NodeType);
  }
}

/**
 * Get descriptions for each node type (without stage mentions)
 */
export const NODE_TYPE_DESCRIPTIONS: Record<NodeType, string> = {
  [NodeType.Root]: "Initial baseline implementation",
  [NodeType.Debug]: "Attempts to fix bugs in failed implementations",
  [NodeType.Improve]: "Optimizations/refinements of working code",
  [NodeType.Hyperparam]: "Systematic parameter exploration",
  [NodeType.Ablation]: "Component contribution analysis",
  [NodeType.SeedNode]: "Robustness testing with different random seeds",
};

/**
 * Long descriptions for each node type
 * Used in the detail panel to explain what the scientist is trying to do
 */
export const NODE_TYPE_LONG_DESCRIPTIONS: Record<NodeType, string> = {
  [NodeType.Root]:
    "The starting implementation that establishes the baseline. This is the initial attempt to solve the research problem.",
  [NodeType.Debug]:
    "The scientist identified a bug or failure in the parent implementation and generated a fix. These nodes represent debugging attempts to get the code working again.",
  [NodeType.Improve]:
    "The parent implementation succeeded, and this node represents an attempt to improve performance or quality. The scientist applies optimizations while maintaining functionality.",
  [NodeType.Hyperparam]:
    "Systematic exploration of hyperparameter values to find better configurations. The scientist varies parameters within the same general approach.",
  [NodeType.Ablation]:
    "Controlled removal of specific components to understand their individual contributions. The scientist isolates which parts of the code are most important.",
  [NodeType.SeedNode]:
    "Tests the robustness of the parent's implementation by running it with different random seeds. Unlike debug/improve nodes, this reuses the parent code with varied initialization.",
};
