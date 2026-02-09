"use client";

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { NodeType, BorderStyle, NODE_TYPE_COLORS, BORDER_STYLES } from "@/shared/lib/tree-colors";

export interface ResearchTreeNodeData extends Record<string, unknown> {
  nodeType: NodeType;
  borderStyle: BorderStyle;
  isSelected: boolean;
  label?: string;
  originalNodeId?: number;
  stageId?: string;
}

export interface StageLabelNodeData extends Record<string, unknown> {
  label: string;
  dividerWidth: number; // Width for alignment
}

export interface StageDividerNodeData extends Record<string, unknown> {
  dividerWidth: number;
}

const NODE_SIZE = 28;

interface ResearchTreeNodeProps {
  data: ResearchTreeNodeData;
}

function ResearchTreeNodeComponent({ data }: ResearchTreeNodeProps) {
  const nodeColor = NODE_TYPE_COLORS[data.nodeType].color;
  const borderConfig = BORDER_STYLES[data.borderStyle];
  const selectedBorderConfig = BORDER_STYLES[BorderStyle.Selected];

  const strokeColor = data.isSelected ? selectedBorderConfig.stroke : borderConfig.stroke;
  const strokeWidth = data.isSelected
    ? parseFloat(selectedBorderConfig.strokeWidth) * 2
    : parseFloat(borderConfig.strokeWidth) * 1.5;

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ visibility: "hidden" }} />
      <div
        className="flex items-center justify-center"
        style={{
          width: NODE_SIZE,
          height: NODE_SIZE,
        }}
      >
        <svg width={NODE_SIZE} height={NODE_SIZE} viewBox={`0 0 ${NODE_SIZE} ${NODE_SIZE}`}>
          <circle
            cx={NODE_SIZE / 2}
            cy={NODE_SIZE / 2}
            r={NODE_SIZE / 2 - strokeWidth}
            fill={nodeColor}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
          />
        </svg>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ visibility: "hidden" }} />
    </>
  );
}

export const ResearchTreeNode = memo(ResearchTreeNodeComponent);

// Stage label node for Full Tree view
interface StageLabelNodeProps {
  data: StageLabelNodeData;
}

function StageLabelNodeComponent({ data }: StageLabelNodeProps) {
  return (
    <div className="pointer-events-none select-none" style={{ width: data.dividerWidth }}>
      <span className="text-xs font-semibold text-slate-400 whitespace-nowrap">{data.label}</span>
    </div>
  );
}

export const StageLabelNode = memo(StageLabelNodeComponent);

// Stage divider node - horizontal line between stages
interface StageDividerNodeProps {
  data: StageDividerNodeData;
}

function StageDividerNodeComponent({ data }: StageDividerNodeProps) {
  return (
    <div
      className="border-t border-dashed border-slate-600 pointer-events-none"
      style={{ width: data.dividerWidth }}
    />
  );
}

export const StageDividerNode = memo(StageDividerNodeComponent);
