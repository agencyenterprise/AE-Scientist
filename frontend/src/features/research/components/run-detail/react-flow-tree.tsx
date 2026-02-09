"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { getLayoutedElements } from "@/shared/lib/tree-layout";
import {
  ResearchTreeNode,
  StageLabelNode,
  StageDividerNode,
  type ResearchTreeNodeData,
  type StageLabelNodeData,
  type StageDividerNodeData,
} from "./research-tree-node";
import { getNodeType, getBorderStyle } from "@/shared/lib/tree-colors";
import { stageLabel } from "@/shared/lib/stage-utils";

// Custom node types for React Flow
const nodeTypes: NodeTypes = {
  researchNode: ResearchTreeNode,
  stageLabel: StageLabelNode,
  stageDivider: StageDividerNode,
};

interface TreeNode {
  id: number;
  x: number;
  y: number;
  excType?: string | null;
  isBest?: boolean;
  isSeedNode?: boolean;
  isSeedAggNode?: boolean;
  ablationName?: string | null;
  hyperparamName?: string | null;
  originalNodeId?: number;
  stageId?: string;
}

interface Props {
  nodes: TreeNode[];
  edges: Array<[number, number]>;
  selectedNodeId: number;
  onNodeSelect: (nodeId: number) => void;
  onNodeHover?: (nodeId: number | null, position: { x: number; y: number } | null) => void;
}

// Layout constants
const NODE_SIZE = 28;
const MIN_HEIGHT = 300;
const MAX_HEIGHT = 800;
const PADDING = 40; // Padding around the content

export function ReactFlowTree({
  nodes: treeNodes,
  edges: treeEdges,
  selectedNodeId,
  onNodeSelect,
  onNodeHover,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Generate a stable key for the tree based on node count and stage IDs
  // This forces React Flow to remount when switching stages
  const treeKey = useMemo(() => {
    const stageIds = [...new Set(treeNodes.map(n => n.stageId).filter(Boolean))].sort().join(",");
    return `tree-${treeNodes.length}-${stageIds}`;
  }, [treeNodes]);

  // Convert tree data to React Flow format with dagre layout
  const { initialNodes, initialEdges, computedHeight } = useMemo(() => {
    // Create context for node type detection
    const context = {
      nodes: treeNodes,
      edges: treeEdges,
    };

    // Check if we have multiple stages (Full Tree view)
    const stageIds = [...new Set(treeNodes.map(n => n.stageId).filter(Boolean))];
    const isFullTree = stageIds.length > 1;

    // Convert to React Flow edges
    const rfEdges: Edge[] = treeEdges.map(([source, target], idx) => ({
      id: `edge-${idx}`,
      source: String(source),
      target: String(target),
      style: {
        stroke: "#64748b",
        strokeWidth: 1.5,
      },
      type: "default",
    }));

    if (isFullTree) {
      // For Full Tree view, apply dagre to each stage separately, then stack them vertically
      // This preserves dagre's nice layout while keeping stages properly separated

      // Group nodes by stageId
      const nodesByStage = new Map<string, typeof treeNodes>();
      for (const node of treeNodes) {
        const sid = node.stageId ?? "unknown";
        const existing = nodesByStage.get(sid);
        if (existing) {
          existing.push(node);
        } else {
          nodesByStage.set(sid, [node]);
        }
      }

      // Sort stages in order (stage_1, stage_2, etc.)
      const stageOrder = ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5"];
      const sortedStageIds = Array.from(nodesByStage.keys()).sort(
        (a, b) => stageOrder.indexOf(a) - stageOrder.indexOf(b)
      );

      // Build a map from global node ID to local node ID within each stage
      const globalToLocal = new Map<number, { stageId: string; localId: number }>();
      for (const [sid, stageNodes] of nodesByStage) {
        stageNodes.forEach((node, localIdx) => {
          globalToLocal.set(node.id, { stageId: sid, localId: localIdx });
        });
      }

      // Process each stage with dagre, then offset Y positions to stack them
      const allLayoutedNodes: Node<ResearchTreeNodeData>[] = [];
      const stageOffsets = new Map<
        string,
        { yOffset: number; minX: number; maxX: number; minY: number; maxY: number }
      >();
      let currentYOffset = 0;
      const STAGE_GAP = 60; // Gap between stages

      for (const sid of sortedStageIds) {
        const stageNodes = nodesByStage.get(sid);
        if (!stageNodes || stageNodes.length === 0) continue;

        // Get edges within this stage (both nodes must belong to this stage)
        const stageEdges = treeEdges.filter(([source, target]) => {
          const sourceInfo = globalToLocal.get(source);
          const targetInfo = globalToLocal.get(target);
          return sourceInfo?.stageId === sid && targetInfo?.stageId === sid;
        });

        // Create RF nodes for this stage
        const stageRfNodes: Node<ResearchTreeNodeData>[] = stageNodes.map(node => {
          const nodeType = getNodeType(node.id, context);
          const borderStyle = getBorderStyle(node);
          return {
            id: String(node.id),
            type: "researchNode",
            position: { x: 0, y: 0 },
            data: {
              nodeType,
              borderStyle,
              isSelected: node.id === selectedNodeId,
              originalNodeId: node.originalNodeId ?? node.id,
              stageId: node.stageId,
            },
          };
        });

        // Create RF edges for this stage
        const stageRfEdges: Edge[] = stageEdges.map(([source, target], idx) => ({
          id: `stage-edge-${sid}-${idx}`,
          source: String(source),
          target: String(target),
          style: { stroke: "#64748b", strokeWidth: 1.5 },
          type: "default",
        }));

        // Apply dagre to this stage
        const layouted = getLayoutedElements(stageRfNodes, stageRfEdges, {
          direction: "TB",
          nodeWidth: NODE_SIZE,
          nodeHeight: NODE_SIZE,
          nodesep: 30,
          ranksep: 50,
        });

        // Compute bounds for this stage
        let minX = Infinity,
          maxX = -Infinity;
        let minY = Infinity,
          maxY = -Infinity;
        for (const node of layouted.nodes) {
          minX = Math.min(minX, node.position.x);
          maxX = Math.max(maxX, node.position.x);
          minY = Math.min(minY, node.position.y);
          maxY = Math.max(maxY, node.position.y);
        }

        // Offset Y positions to stack below previous stages
        const yAdjustment = currentYOffset - minY;
        for (const node of layouted.nodes) {
          node.position.y += yAdjustment;
          allLayoutedNodes.push(node);
        }

        // Record stage bounds (after adjustment)
        stageOffsets.set(sid, {
          yOffset: currentYOffset,
          minX,
          maxX,
          minY: currentYOffset,
          maxY: currentYOffset + (maxY - minY),
        });

        // Move offset for next stage
        currentYOffset += maxY - minY + STAGE_GAP;
      }

      // Compute overall bounds
      let overallMinX = Infinity,
        overallMaxX = -Infinity;
      let overallMinY = Infinity,
        overallMaxY = -Infinity;
      for (const node of allLayoutedNodes) {
        overallMinX = Math.min(overallMinX, node.position.x);
        overallMaxX = Math.max(overallMaxX, node.position.x);
        overallMinY = Math.min(overallMinY, node.position.y);
        overallMaxY = Math.max(overallMaxY, node.position.y);
      }

      const contentWidth = overallMaxX - overallMinX + NODE_SIZE * 2;
      const dividerWidth = Math.max(contentWidth, 200);
      const nodeHalfSize = NODE_SIZE / 2;

      // Create label and divider nodes
      const labelNodes: Node<StageLabelNodeData>[] = [];
      const dividerNodes: Node<StageDividerNodeData>[] = [];

      sortedStageIds.forEach((sid, idx) => {
        const bounds = stageOffsets.get(sid);
        if (!bounds) return;

        // Label above the stage
        labelNodes.push({
          id: `stage-label-${sid}`,
          type: "stageLabel",
          position: { x: overallMinX - 10, y: bounds.minY - nodeHalfSize - 20 },
          data: { label: stageLabel(sid), dividerWidth },
          selectable: false,
          draggable: false,
        });

        // Divider after the stage (except last)
        if (idx < sortedStageIds.length - 1) {
          const dividerY = bounds.maxY + nodeHalfSize + 15;
          dividerNodes.push({
            id: `stage-divider-${sid}`,
            type: "stageDivider",
            position: { x: overallMinX - 10, y: dividerY },
            data: { dividerWidth },
            selectable: false,
            draggable: false,
          });
        }
      });

      const contentHeight = overallMaxY - overallMinY + NODE_SIZE;
      const calculatedHeight = Math.min(
        Math.max(MIN_HEIGHT, contentHeight + PADDING * 2),
        MAX_HEIGHT
      );

      return {
        initialNodes: [...allLayoutedNodes, ...labelNodes, ...dividerNodes],
        initialEdges: rfEdges,
        computedHeight: calculatedHeight,
      };
    }

    // Single stage view: use dagre for layout
    const rfNodes: Node<ResearchTreeNodeData>[] = treeNodes.map(node => {
      const nodeType = getNodeType(node.id, context);
      const borderStyle = getBorderStyle(node);

      return {
        id: String(node.id),
        type: "researchNode",
        position: { x: 0, y: 0 }, // Will be set by dagre
        data: {
          nodeType,
          borderStyle,
          isSelected: node.id === selectedNodeId,
          originalNodeId: node.originalNodeId ?? node.id,
          stageId: node.stageId,
        },
      };
    });

    // Apply dagre layout with tighter spacing
    const layouted = getLayoutedElements(rfNodes, rfEdges, {
      direction: "TB",
      nodeWidth: NODE_SIZE,
      nodeHeight: NODE_SIZE,
      nodesep: 30, // Horizontal spacing between nodes
      ranksep: 50, // Vertical spacing between levels
    });

    // Compute bounds of the layout
    let minY = Infinity;
    let maxY = -Infinity;
    for (const node of layouted.nodes) {
      minY = Math.min(minY, node.position.y);
      maxY = Math.max(maxY, node.position.y);
    }

    // Calculate height based on actual content + padding
    const contentHeight = maxY - minY + NODE_SIZE;
    const calculatedHeight = Math.min(
      Math.max(MIN_HEIGHT, contentHeight + PADDING * 2),
      MAX_HEIGHT
    );

    return {
      initialNodes: layouted.nodes,
      initialEdges: layouted.edges,
      computedHeight: calculatedHeight,
    };
  }, [treeNodes, treeEdges, selectedNodeId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state when initialNodes/initialEdges change (e.g., when switching stages)
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Handle node click
  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      if (node.type === "stageLabel" || node.type === "stageDivider") return;
      onNodeSelect(Number(node.id));
    },
    [onNodeSelect]
  );

  // Handle node hover - pass viewport coordinates for fixed positioning
  const onNodeMouseEnter: NodeMouseHandler = useCallback(
    (event, node) => {
      if (node.type === "stageLabel" || node.type === "stageDivider") return;
      if (onNodeHover) {
        onNodeHover(Number(node.id), {
          x: event.clientX + 12,
          y: event.clientY + 12,
        });
      }
    },
    [onNodeHover]
  );

  const onNodeMouseLeave: NodeMouseHandler = useCallback(() => {
    if (onNodeHover) {
      onNodeHover(null, null);
    }
  }, [onNodeHover]);

  return (
    <div ref={containerRef} className="w-full" style={{ height: `${computedHeight}px` }}>
      <ReactFlow
        key={treeKey}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.05, minZoom: 0.5, maxZoom: 1.5 }}
        minZoom={0.3}
        maxZoom={2}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={16} size={1} />
        <Controls className="!bg-slate-800 !border-slate-700 !rounded-lg !shadow-lg [&>button]:!bg-slate-800 [&>button]:!border-slate-700 [&>button]:!text-slate-300 [&>button:hover]:!bg-slate-700" />
      </ReactFlow>
    </div>
  );
}
