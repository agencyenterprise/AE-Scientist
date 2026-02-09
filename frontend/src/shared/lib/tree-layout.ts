/**
 * Tree layout utility using dagre for automatic node positioning
 */
import dagre from "dagre";
import type { Node, Edge } from "@xyflow/react";

interface LayoutOptions {
  direction?: "TB" | "BT" | "LR" | "RL";
  nodeWidth?: number;
  nodeHeight?: number;
  nodesep?: number;
  ranksep?: number;
}

const DEFAULT_OPTIONS: Required<LayoutOptions> = {
  direction: "TB",
  nodeWidth: 60,
  nodeHeight: 60,
  nodesep: 40,
  ranksep: 80,
};

/**
 * Calculate layout positions for nodes using dagre
 * Returns nodes with updated positions and edges
 */
export function getLayoutedElements<T extends Record<string, unknown>>(
  nodes: Node<T>[],
  edges: Edge[],
  options: LayoutOptions = {}
): { nodes: Node<T>[]; edges: Edge[] } {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const dagreGraph = new dagre.graphlib.Graph();

  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: opts.direction,
    nodesep: opts.nodesep,
    ranksep: opts.ranksep,
  });

  // Add nodes to dagre graph
  nodes.forEach(node => {
    dagreGraph.setNode(node.id, {
      width: opts.nodeWidth,
      height: opts.nodeHeight,
    });
  });

  // Add edges to dagre graph
  edges.forEach(edge => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Calculate layout
  dagre.layout(dagreGraph);

  // Apply calculated positions to nodes
  const layoutedNodes = nodes.map(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - opts.nodeWidth / 2,
        y: nodeWithPosition.y - opts.nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
