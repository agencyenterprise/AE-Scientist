"use client";

import { useEffect, useMemo, useState } from "react";
import type { ArtifactMetadata, TreeVizItem, MergedTreeViz, StageZoneMetadata } from "@/types/research";
import { fetchDownloadUrl } from "@/shared/lib/downloads";
import { stageLabel, FULL_TREE_STAGE_ID } from "@/shared/lib/stage-utils";
import {
  getNodeType,
  getBorderStyle,
  NODE_TYPE_COLORS,
  BORDER_STYLES,
  NODE_TYPE_LONG_DESCRIPTIONS,
  BorderStyle,
} from "@/shared/lib/tree-colors";
import { NodeTypesLegend } from "./NodeTypesLegend";
import { NodeStrategyGuide } from "./NodeStrategyGuide";

type MetricName = {
  metric_name: string;
  lower_is_better?: boolean;
  description?: string;
  data: Array<{ dataset_name?: string; final_value?: number; best_value?: number }>;
};

type MetricEntry = {
  metric_names?: MetricName[];
};

type PlotAnalysis = { plot_path?: string; analysis?: string; key_findings?: string[] };

type TreeVizPayload = TreeVizItem["viz"] & {
  layout: Array<[number, number]>;
  edges: Array<[number, number]>;
  code?: string[];
  plan?: string[];
  analysis?: string[];
  metrics?: Array<MetricEntry | null>;
  exc_type?: Array<string | null>;
  exc_info?: Array<{ args?: unknown[] } | null>;
  exc_stack?: Array<unknown>;
  plot_plan?: Array<string | null>;
  plot_code?: Array<string | null>;
  plot_analyses?: Array<Array<PlotAnalysis | null> | null>;
  plots?: Array<string | string[] | null>;
  plot_paths?: Array<string | string[] | null>;
  vlm_feedback_summary?: Array<string | string[] | null>;
  datasets_successfully_tested?: Array<string[] | null>;
  exec_time?: Array<number | string | null>;
  exec_time_feedback?: Array<string | null>;
  is_best_node?: Array<boolean>;
  is_seed_node?: Array<boolean>;
  is_seed_agg_node?: Array<boolean>;
  ablation_name?: Array<string | null>;
  hyperparam_name?: Array<string | null>;
};

interface Props {
  viz: TreeVizItem | MergedTreeViz;
  artifacts: ArtifactMetadata[];
  stageId: string;
  bestNodeId?: number | null;
}

// =============================================================================
// SVG VISUALIZATION CONSTANTS
// =============================================================================

// Node appearance
const NODE_SIZE = 14;

// ViewBox sizing - calibrated for good aspect ratio and readability
const SINGLE_STAGE_VIEWBOX_HEIGHT = 100;
const ADDITIONAL_HEIGHT_PER_STAGE = 33; // ~1.33x scaling per stage
const VIEWBOX_TO_PIXELS_RATIO = 5; // viewBox 100 → 500px

// Full Tree stage separator layout (in viewBox units)
const LABEL_OFFSET_FROM_TOP = -7.0; // First stage: offset above zone top (prevents node overlap)
const LABEL_OFFSET_FROM_DIVIDER = 7.0; // Other stages: offset below divider
const DIVIDER_OFFSET = 2.0; // Offset from calculated position
const LABEL_BG_HEIGHT = 5;
const LABEL_BG_PADDING_TOP = 3.5;


export function TreeVizViewer({ viz, artifacts, stageId, bestNodeId }: Props) {
  const payload = viz.viz as TreeVizPayload;

  // Determine initial selection: use bestNodeId if available and valid, otherwise default to 0
  const initialSelection = useMemo(() => {
    if (bestNodeId !== null && bestNodeId !== undefined && bestNodeId >= 0) {
      return bestNodeId;
    }

    return 0;
  }, [bestNodeId]);

  const [selected, setSelected] = useState<number>(initialSelection);

  // Reset selection when the viz or bestNodeId changes (e.g., when switching stages)
  useEffect(() => {
    setSelected(initialSelection);
  }, [initialSelection]);

  const nodes = useMemo(() => {
    return (payload.layout || []).map((coords, idx) => ({
      id: idx,
      stageId: (payload as { stageIds?: string[] }).stageIds?.[idx] ?? stageId,
      originalNodeId: (payload as { originalNodeIds?: number[] }).originalNodeIds?.[idx] ?? idx,
      x: coords?.[0] ?? 0,
      y: coords?.[1] ?? 0,
      code: payload.code?.[idx] ?? "",
      plan: payload.plan?.[idx] ?? "",
      analysis: payload.analysis?.[idx] ?? "",
      excType: payload.exc_type?.[idx],
      excInfo: payload.exc_info?.[idx],
      metrics: payload.metrics?.[idx] ?? null,
      plotPlan: payload.plot_plan?.[idx] ?? "",
      plotCode: payload.plot_code?.[idx] ?? "",
      plotAnalyses: payload.plot_analyses?.[idx] ?? [],
      vlmFeedbackSummary: payload.vlm_feedback_summary?.[idx] ?? "",
      datasetsTested: payload.datasets_successfully_tested?.[idx] ?? [],
      execTime: payload.exec_time?.[idx],
      execTimeFeedback: payload.exec_time_feedback?.[idx] ?? "",
      isBest: payload.is_best_node?.[idx] ?? false,
      isSeedNode: payload.is_seed_node?.[idx] ?? false,
      isSeedAggNode: payload.is_seed_agg_node?.[idx] ?? false,
      ablationName: payload.ablation_name?.[idx],
      hyperparamName: payload.hyperparam_name?.[idx],
    }));
  }, [payload, stageId]);

  const edges: Array<[number, number]> = payload.edges ?? [];

  // Extract zone metadata for Full Tree view
  const zoneMetadata = (payload as { zoneMetadata?: StageZoneMetadata[] }).zoneMetadata ?? [];
  const isFullTree = stageId === FULL_TREE_STAGE_ID;

  // Calculate dynamic viewBox height based on number of stages
  // Full Tree view scales height based on stage count; single stage uses base height
  const numStages = isFullTree ? zoneMetadata.length : 1;
  const viewBoxHeight =
    SINGLE_STAGE_VIEWBOX_HEIGHT + (numStages - 1) * ADDITIONAL_HEIGHT_PER_STAGE;
  const cssHeight = viewBoxHeight * VIEWBOX_TO_PIXELS_RATIO;

  const selectedNode = nodes[selected];
  const plotList = useMemo(() => {
    if (!selectedNode) return [];
    const plotFiles = payload.plots ?? [];
    const plotPaths = payload.plot_paths ?? [];
    const plotsForNode = plotFiles[selected] ?? plotPaths[selected] ?? [];
    if (Array.isArray(plotsForNode)) return plotsForNode;
    if (plotsForNode) return [plotsForNode];
    return [];
  }, [payload, selected, selectedNode]);

  const [plotUrls, setPlotUrls] = useState<string[]>([]);

  useEffect(() => {
    let canceled = false;

    const loadPlotUrls = async () => {
      if (!plotList.length) {
        setPlotUrls([]);
        return;
      }

      const resolved = await Promise.all(
        plotList.map(async p => {
          if (!p) return null;
          const asString = p.toString();
          if (asString.startsWith("http://") || asString.startsWith("https://")) {
            return asString;
          }
          const filename = asString.split("/").pop();
          const artifact =
            artifacts.find(a => a.filename === filename) ||
            artifacts.find(a => a.download_path && a.download_path.endsWith(asString));
          if (artifact?.download_path) {
            try {
              return await fetchDownloadUrl(artifact.download_path);
            } catch {
              return null;
            }
          }
          return null;
        })
      );

      if (!canceled) {
        setPlotUrls(resolved.filter((url): url is string => Boolean(url)));
      }
    };

    loadPlotUrls().catch(() => {
      if (!canceled) {
        setPlotUrls([]);
      }
    });

    return () => {
      canceled = true;
    };
  }, [artifacts, plotList]);

  // Render stage separators (dividers + labels) for Full Tree view
  const renderStageSeparators = () => {
    if (!isFullTree || zoneMetadata.length === 0) return null;

    // Use the same coordinate transformation as nodes to avoid drift
    // Full Tree nodes use: y * (viewBoxHeight - 10) + 5
    const transformY = (y: number) => y * (viewBoxHeight - 10) + 5;

    return (
      <g className="stage-separators">
        {zoneMetadata.map((meta, idx) => {
          const isFirstStage = idx === 0;
          const zoneStartY = transformY(meta.zone.min);

          // Position divider in the middle of the padding gap between stages
          let dividerY = zoneStartY;
          if (!isFirstStage) {
            const prevZone = zoneMetadata[idx - 1]?.zone;
            if (prevZone) {
              // Divider goes in the middle of the gap: between prevZone.max and meta.zone.min
              dividerY = transformY((prevZone.max + meta.zone.min) / 2);
            }
          }

          // Position labels consistently:
          // - First stage: offset from zone start (no divider above)
          // - Other stages: offset below divider line
          const labelY = isFirstStage
            ? zoneStartY + LABEL_OFFSET_FROM_TOP
            : dividerY + LABEL_OFFSET_FROM_DIVIDER;
          const labelText = stageLabel(meta.stageId);

          return (
            <g key={`separator-${meta.stageId}`}>
              {/* Background rectangle behind label to prevent node overlap */}
              <rect
                x={1}
                y={labelY - LABEL_BG_PADDING_TOP}
                width={labelText.length * 2.5}
                height={LABEL_BG_HEIGHT}
                fill="#0f172a"
                opacity={0.9}
                className="select-none"
              />

              {/* Stage label */}
              <text
                x={2}
                y={labelY}
                fontSize="4"
                fill="#64748b"
                fontWeight="600"
                className="select-none"
              >
                {labelText}
              </text>

              {/* Divider line (skip first stage, only draw between stages) */}
              {!isFirstStage && (
                <line
                  x1={0}
                  y1={dividerY + DIVIDER_OFFSET}
                  x2={100}
                  y2={dividerY + DIVIDER_OFFSET}
                  stroke="#64748b"
                  strokeWidth={0.4}
                  strokeDasharray="2,2"
                  opacity={0.6}
                />
              )}
            </g>
          );
        })}
      </g>
    );
  };

  return (
    <div className="flex w-full gap-4">
      <div className="w-1/2 flex flex-col">
        <div className="relative flex-1 border border-slate-700 bg-slate-900 overflow-auto max-h-[700px]">
          <svg
            viewBox={`0 -8 100 ${viewBoxHeight + 8}`}
            preserveAspectRatio="xMidYMin meet"
            className="w-full"
            style={{ height: `${cssHeight}px` }}
          >
            {/* Stage separators (rendered first as background) */}
            {renderStageSeparators()}

            {/* Edges */}
            {edges.map(([parent, child], idx) => {
              const p = nodes[parent];
              const c = nodes[child];
              if (!p || !c) return null;
              const px = p.x * 85 + 7.5;
              // Full Tree uses full viewBox height scaling with small offset to prevent top clipping
              const py = isFullTree
                ? p.y * (viewBoxHeight - 10) + 5
                : p.y * (viewBoxHeight - 15) + 7.5;
              const cx = c.x * 85 + 7.5;
              const cy = isFullTree
                ? c.y * (viewBoxHeight - 10) + 5
                : c.y * (viewBoxHeight - 15) + 7.5;
              return (
                <line
                  key={idx}
                  x1={px}
                  y1={py}
                  x2={cx}
                  y2={cy}
                  stroke="#cbd5e1"
                  strokeWidth={0.48}
                />
              );
            })}
            {nodes.map(node => {
              const isSelected = node.id === selected;
              const nodeType = getNodeType(node.id, { nodes, edges });
              const nodeColor = NODE_TYPE_COLORS[nodeType].color;
              const qualityBorder = getBorderStyle(node);
              const borderConfig = BORDER_STYLES[qualityBorder];
              const selectedBorderConfig = BORDER_STYLES[BorderStyle.Selected];
              const strokeColor = isSelected ? selectedBorderConfig.stroke : borderConfig.stroke;
              const strokeWidth = isSelected
                ? selectedBorderConfig.strokeWidth
                : borderConfig.strokeWidth;
              const cx = node.x * 85 + 7.5;
              // Full Tree uses full viewBox height scaling with small offset to prevent top clipping
              const cy = isFullTree
                ? node.y * (viewBoxHeight - 10) + 5
                : node.y * (viewBoxHeight - 15) + 7.5;
              return (
                <g key={node.id} onClick={() => setSelected(node.id)} className="cursor-pointer">
                  <circle
                    cx={cx}
                    cy={cy}
                    r={NODE_SIZE / 3}
                    fill={nodeColor}
                    stroke={strokeColor}
                    strokeWidth={parseFloat(strokeWidth)}
                  />
                </g>
              );
            })}
          </svg>
        </div>
        <div className="mt-2 flex gap-2">
          <NodeTypesLegend stageId={isFullTree ? undefined : stageId} />
          <NodeStrategyGuide stageId={isFullTree ? undefined : stageId} />
        </div>
      </div>
      <div className="w-1/2 rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-100 max-h-[600px] overflow-y-auto">
        {selectedNode ? (
          <>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-base font-semibold">
                {selectedNode.stageId
                  ? `${stageLabel(selectedNode.stageId)}: Node ${selectedNode.originalNodeId}`
                  : `Node ${selectedNode.id}`}
              </h3>
              {selectedNode.excType ? (
                <span className="text-xs text-red-300">Abandoned</span>
              ) : selectedNode.isBest ? (
                <span className="text-xs text-emerald-300">Best</span>
              ) : (
                <span className="text-xs text-emerald-300">Succeeded</span>
              )}
            </div>
            <div className="space-y-2">
              <NodeTypeSection nodeId={selectedNode.id} nodes={nodes} edges={edges} />
              {selectedNode.isSeedNode ? null : <Section label="Plan" value={selectedNode.plan} />}
              <Section label="Analysis" value={selectedNode.analysis} />
              <MetricsSection metrics={selectedNode.metrics} />
              <ExecSection
                execTime={selectedNode.execTime}
                feedback={selectedNode.execTimeFeedback}
              />
              {selectedNode.datasetsTested && selectedNode.datasetsTested.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-300">Datasets Tested</div>
                  <ul className="list-disc pl-4 text-xs text-slate-200">
                    {selectedNode.datasetsTested.map(ds => (
                      <li key={ds}>{ds}</li>
                    ))}
                  </ul>
                </div>
              )}
              <CollapsibleSection label="Plot Plan" value={selectedNode.plotPlan} />
              <CollapsibleSection label="Plot Code" value={selectedNode.plotCode} isMono />
              <CollapsibleSection label="Code" value={selectedNode.code} isMono />
              {plotUrls.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Plots</div>
                  <div className="grid grid-cols-1 gap-2">
                    {plotUrls.map(url => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        key={url}
                        src={url}
                        alt="Plot"
                        className="w-full rounded border border-slate-700 bg-slate-900"
                      />
                    ))}
                  </div>
                </div>
              )}
              <PlotAnalysesSection analyses={selectedNode.plotAnalyses} />
              <VlmSection summary={selectedNode.vlmFeedbackSummary} />
              {selectedNode.excType && (
                <div className="text-xs text-red-200">
                  <div className="font-semibold">Exception</div>
                  <div>{selectedNode.excType}</div>
                  {selectedNode.excInfo && selectedNode.excInfo.args && (
                    <div className="text-slate-300">{String(selectedNode.excInfo.args[0])}</div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <p className="text-slate-300">Select a node to inspect details.</p>
        )}
      </div>
    </div>
  );
}

interface NodeTypeSectionProps {
  nodeId: number;
  nodes: Array<{
    id: number;
    excType?: string | null;
    isBest?: boolean;
    isSeedNode?: boolean;
    isSeedAggNode?: boolean;
    ablationName?: string | null;
    hyperparamName?: string | null;
  }>;
  edges: Array<[number, number]>;
}

function NodeTypeSection({ nodeId, nodes, edges }: NodeTypeSectionProps) {
  const nodeType = getNodeType(nodeId, { nodes, edges });
  const longDescription = NODE_TYPE_LONG_DESCRIPTIONS[nodeType];
  const label = NODE_TYPE_COLORS[nodeType].label;

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300">Node Type: {label}</div>
      <div className="whitespace-pre-wrap">{longDescription}</div>
    </div>
  );
}

function Section({
  label,
  value,
  isMono = false,
}: {
  label: string;
  value: string;
  isMono?: boolean;
}) {
  if (!value) return null;
  return (
    <div>
      <div className="text-xs font-semibold text-slate-300">{label}</div>
      <div className={`whitespace-pre-wrap ${isMono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  );
}

function CollapsibleSection({
  label,
  value,
  isMono = false,
}: {
  label: string;
  value: string;
  isMono?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!value) return null;
  return (
    <div>
      <button
        type="button"
        className="text-xs font-semibold text-slate-300 flex items-center gap-2"
        onClick={() => setOpen(prev => !prev)}
      >
        {open ? "▾" : "▸"} {label}
      </button>
      {open && (
        <div className={`mt-1 whitespace-pre-wrap ${isMono ? "font-mono text-xs" : ""}`}>
          {value}
        </div>
      )}
    </div>
  );
}

function MetricsSection({ metrics }: { metrics: MetricEntry | null | undefined }) {
  if (!metrics || !metrics.metric_names || metrics.metric_names.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-300">Metrics</div>
      {metrics.metric_names.map((metric: MetricName) => (
        <div key={metric.metric_name} className="rounded border border-slate-700 p-2 text-xs">
          <div className="font-semibold text-slate-100">{metric.metric_name}</div>
          {metric.description && <div className="text-slate-300">{metric.description}</div>}
          <table className="mt-1 w-full text-left text-slate-200">
            <thead>
              <tr className="text-[11px] text-slate-400">
                <th className="pr-2">Dataset</th>
                <th className="pr-2">Final</th>
                <th>Best</th>
              </tr>
            </thead>
            <tbody>
              {(metric.data || []).map((d: MetricName["data"][number], idx: number) => (
                <tr key={idx}>
                  <td className="pr-2">{d.dataset_name || "default"}</td>
                  <td className="pr-2">{d.final_value ?? "n/a"}</td>
                  <td>{d.best_value ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function ExecSection({
  execTime,
  feedback,
}: {
  execTime: number | string | null | undefined;
  feedback: string;
}) {
  if (!execTime && !feedback) return null;
  return (
    <div className="text-xs text-slate-200 space-y-1">
      {execTime !== null && execTime !== undefined && (
        <div>
          <span className="font-semibold text-slate-300">Execution Time:</span> {execTime} s
        </div>
      )}
      {feedback && (
        <div>
          <div className="font-semibold text-slate-300">Execution Feedback</div>
          <div>{feedback}</div>
        </div>
      )}
    </div>
  );
}

function PlotAnalysesSection({
  analyses,
}: {
  analyses: Array<PlotAnalysis | null> | null | undefined;
}) {
  if (!analyses || analyses.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-300">Plot Analyses</div>
      {analyses.map((analysis: PlotAnalysis | null, idx: number) => {
        if (!analysis) return null;
        return (
          <div key={idx} className="rounded border border-slate-700 p-2 text-xs text-slate-200">
            {analysis.plot_path && <div className="font-semibold">{analysis.plot_path}</div>}
            {analysis.analysis && <div>{analysis.analysis}</div>}
            {analysis.key_findings && analysis.key_findings.length > 0 && (
              <ul className="list-disc pl-4 text-slate-300">
                {analysis.key_findings.map(finding => (
                  <li key={finding}>{finding}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

function VlmSection({ summary }: { summary: string | string[] | null | undefined }) {
  if (!summary) return null;
  const raw = Array.isArray(summary) ? summary : [summary];
  const normalized = raw
    .flatMap(entry => {
      if (entry === null || entry === undefined) return [];
      if (Array.isArray(entry)) return entry;
      return [entry];
    })
    .map(entry => (entry === null || entry === undefined ? "" : String(entry).trim()))
    .map(entry => {
      // Strip surrounding square brackets if present (e.g., "['text']" or "[ text ]")
      if (entry.startsWith("[") && entry.endsWith("]")) {
        const inner = entry.slice(1, -1).trim();
        if (inner.startsWith("'") && inner.endsWith("'")) {
          return inner.slice(1, -1).trim();
        }
        if (inner.startsWith('"') && inner.endsWith('"')) {
          return inner.slice(1, -1).trim();
        }
        return inner;
      }
      return entry;
    })
    .filter(line => line.length > 0 && line !== "[]" && line !== "{}");
  if (normalized.length === 0) return null;
  return (
    <div>
      <div className="text-xs font-semibold text-slate-300">VLM Feedback</div>
      <ul className="list-disc pl-4 text-xs text-slate-200">
        {normalized.map(line => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}
