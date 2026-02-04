"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type {
  ArtifactMetadata,
  TreeVizItem,
  MergedTreeViz,
  StageZoneMetadata,
} from "@/types/research";
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
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";

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
  codex_task?: string[];
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
  conversationId: number | null;
  runId: string;
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

export function TreeVizViewer({
  viz,
  artifacts,
  conversationId,
  runId,
  stageId,
  bestNodeId,
}: Props) {
  const payload = viz.viz as TreeVizPayload;

  // Determine initial selection: use bestNodeId if available and valid, otherwise default to 0
  const initialSelection = useMemo(() => {
    if (bestNodeId !== null && bestNodeId !== undefined && bestNodeId >= 0) {
      return bestNodeId;
    }

    return 0;
  }, [bestNodeId]);

  const [selected, setSelected] = useState<number>(initialSelection);
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number } | null>(null);
  const treeContainerRef = useRef<HTMLDivElement>(null);

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
      codexTask: payload.codex_task?.[idx] ?? "",
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
  const viewBoxHeight = SINGLE_STAGE_VIEWBOX_HEIGHT + (numStages - 1) * ADDITIONAL_HEIGHT_PER_STAGE;
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
      if (!plotList.length || conversationId === null) {
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
          const artifact = artifacts.find(a => a.filename === filename);
          if (artifact) {
            // Compute download path from available context
            const downloadPath = `/conversations/${conversationId}/idea/research-run/${runId}/artifacts/${artifact.id}/presign`;
            try {
              return await fetchDownloadUrl(downloadPath);
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
  }, [artifacts, plotList, conversationId, runId]);

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

  const selectedNodeType = selectedNode ? getNodeType(selectedNode.id, { nodes, edges }) : null;
  const selectedNodeTypeLabel = selectedNodeType ? NODE_TYPE_COLORS[selectedNodeType].label : "";
  const selectedNodeTypeDescription = selectedNodeType
    ? NODE_TYPE_LONG_DESCRIPTIONS[selectedNodeType]
    : "";
  const hasMetrics = Boolean(selectedNode?.metrics?.metric_names?.length);
  const normalizedAnalysis = selectedNode?.analysis?.trim() ?? "";
  const normalizedPlan = selectedNode?.plan?.trim() ?? "";
  const showReasoning =
    Boolean(normalizedAnalysis) || (Boolean(normalizedPlan) && !selectedNode?.isSeedNode);
  const datasetsTested = (selectedNode?.datasetsTested ?? [])
    .map(dataset => dataset?.trim())
    .filter((dataset): dataset is string => Boolean(dataset));
  const normalizedVlmSummary = useMemo(
    () => normalizeVlmSummary(selectedNode?.vlmFeedbackSummary),
    [selectedNode?.vlmFeedbackSummary]
  );

  return (
    <div className="flex w-full gap-4 min-h-[500px] items-stretch">
      <div className="w-1/2 flex flex-col">
        <div
          ref={treeContainerRef}
          className="relative flex-1 border border-slate-700 bg-slate-900"
        >
          {hoveredNodeId !== null && hoverPosition && nodes[hoveredNodeId] && (
            <NodeHoverTooltip
              position={hoverPosition}
              node={nodes[hoveredNodeId]}
              nodeType={getNodeType(hoveredNodeId, { nodes, edges })}
            />
          )}
          <svg
            viewBox={`0 -8 100 ${viewBoxHeight + 8}`}
            preserveAspectRatio="xMidYMin meet"
            className="w-full"
            style={{ height: `${cssHeight}px` }}
            onMouseLeave={() => {
              setHoveredNodeId(null);
              setHoverPosition(null);
            }}
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
                <g
                  key={node.id}
                  onClick={() => setSelected(node.id)}
                  onMouseEnter={event => {
                    if (!treeContainerRef.current) return;
                    const rect = treeContainerRef.current.getBoundingClientRect();
                    setHoveredNodeId(node.id);
                    setHoverPosition({
                      x: event.clientX - rect.left + 12,
                      y: event.clientY - rect.top + 12,
                    });
                  }}
                  onMouseMove={event => {
                    if (!treeContainerRef.current) return;
                    const rect = treeContainerRef.current.getBoundingClientRect();
                    setHoverPosition({
                      x: event.clientX - rect.left + 12,
                      y: event.clientY - rect.top + 12,
                    });
                  }}
                  onMouseLeave={() => {
                    setHoveredNodeId(null);
                    setHoverPosition(null);
                  }}
                  className="cursor-pointer"
                >
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
      </div>
      <div className="w-1/2 relative">
        <div className="absolute inset-0 rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-100 overflow-y-auto">
          {selectedNode ? (
            <>
              <div className="space-y-3">
                <InfoCard title="Overview">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold text-slate-100">
                        {selectedNode.stageId ? stageLabel(selectedNode.stageId) : "Node Details"}
                      </div>
                      <div className="text-xs text-slate-400">
                        Node {selectedNode.originalNodeId ?? selectedNode.id}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {selectedNode.isSeedAggNode && <Badge tone="info">Seed Aggregate</Badge>}
                      {selectedNode.isSeedNode && <Badge tone="neutral">Seed</Badge>}
                      {selectedNode.excType ? (
                        <Badge tone="danger">Abandoned</Badge>
                      ) : selectedNode.isBest ? (
                        <Badge tone="success">Best</Badge>
                      ) : (
                        <Badge tone="successMuted">Succeeded</Badge>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
                    {selectedNode.ablationName && (
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-200">
                        Ablation: {selectedNode.ablationName}
                      </span>
                    )}
                    {selectedNode.hyperparamName && (
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-200">
                        Hyperparam: {selectedNode.hyperparamName}
                      </span>
                    )}
                  </div>
                  {(selectedNode.execTime !== null && selectedNode.execTime !== undefined) ||
                  selectedNode.execTimeFeedback ? (
                    <div className="mt-2 text-xs text-slate-400">
                      {selectedNode.execTime !== null && selectedNode.execTime !== undefined && (
                        <div>
                          Execution time:{" "}
                          <span className="text-slate-300">
                            {formatExecutionTime(selectedNode.execTime)}
                          </span>
                        </div>
                      )}
                      {selectedNode.execTimeFeedback && (
                        <div className="text-slate-300">{selectedNode.execTimeFeedback}</div>
                      )}
                    </div>
                  ) : null}
                </InfoCard>

                {selectedNode.excType && (
                  <InfoCard title="Exception" tone="danger">
                    <div className="text-sm text-red-100">{selectedNode.excType}</div>
                    {selectedNode.excInfo && selectedNode.excInfo.args && (
                      <div className="mt-1 text-xs text-red-200">
                        {String(selectedNode.excInfo.args[0])}
                      </div>
                    )}
                  </InfoCard>
                )}

                <InfoCard title="Node Type">
                  <div className="text-sm font-semibold text-slate-100">
                    {selectedNodeTypeLabel}
                  </div>
                  <div className="mt-1 text-xs text-slate-300 whitespace-pre-wrap">
                    {selectedNodeTypeDescription}
                  </div>
                </InfoCard>

                {showReasoning && (
                  <InfoCard title="Reasoning" collapsible>
                    <TextBlock label="Analysis" value={normalizedAnalysis} variant="analysis" />
                    {selectedNode.isSeedNode ? null : (
                      <TextBlock label="Plan" value={normalizedPlan} variant="plan" />
                    )}
                  </InfoCard>
                )}

                {hasMetrics && (
                  <InfoCard title="Metrics" collapsible>
                    <MetricsSection metrics={selectedNode.metrics} />
                  </InfoCard>
                )}

                {datasetsTested.length > 0 && (
                  <InfoCard title="Datasets Tested" collapsible>
                    <ul className="list-disc pl-4 text-xs text-slate-200">
                      {datasetsTested.map(ds => (
                        <li key={ds}>{ds}</li>
                      ))}
                    </ul>
                  </InfoCard>
                )}

                {plotUrls.length > 0 && (
                  <InfoCard title="Plots" collapsible>
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
                  </InfoCard>
                )}

                {selectedNode.plotAnalyses && selectedNode.plotAnalyses.length > 0 && (
                  <InfoCard title="Plot Analyses" collapsible>
                    <PlotAnalysesSection analyses={selectedNode.plotAnalyses} />
                  </InfoCard>
                )}

                {normalizedVlmSummary.length > 0 && (
                  <InfoCard title="VLM Feedback" collapsible>
                    <VlmSection lines={normalizedVlmSummary} />
                  </InfoCard>
                )}

                <InfoCard title="Sources" collapsible>
                  <div className="space-y-2">
                    <CollapsibleSection
                      label="Plot Plan"
                      value={selectedNode.plotPlan}
                      copyLabel="Copy plot plan"
                    />
                    <CollapsibleSection
                      label="Plot Code"
                      value={selectedNode.plotCode}
                      isMono
                      copyLabel="Copy plot code"
                    />
                    <CollapsibleSection
                      label="Coding Agent Task"
                      value={selectedNode.codexTask}
                      isMono
                      copyLabel="Copy coding agent task"
                    />
                    <CollapsibleSection
                      label="Final Code"
                      value={selectedNode.code}
                      isMono
                      copyLabel="Copy code"
                    />
                  </div>
                </InfoCard>
              </div>
            </>
          ) : (
            <p className="text-slate-300">Select a node to inspect details.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoCard({
  title,
  children,
  tone = "default",
  size = "default",
  collapsible = false,
  defaultOpen = true,
}: {
  title: string;
  children: ReactNode;
  tone?: "default" | "danger";
  size?: "default" | "compact";
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const toneClasses =
    tone === "danger" ? "border-red-900/60 bg-red-950/40" : "border-slate-700 bg-slate-900/60";
  const sizeClasses = size === "compact" ? "p-2" : "p-3";
  return (
    <div className={`rounded-lg border ${sizeClasses} ${toneClasses}`}>
      <div className="flex items-center justify-between gap-2">
        {collapsible ? (
          <button
            type="button"
            className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 hover:text-slate-100 transition-colors flex items-center gap-2"
            onClick={() => setOpen(prev => !prev)}
          >
            {open ? "▾" : "▸"} {title}
          </button>
        ) : (
          <CardTitle>{title}</CardTitle>
        )}
      </div>
      {(!collapsible || open) && <div className="mt-2">{children}</div>}
    </div>
  );
}

function CardTitle({ children }: { children: string }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
      {children}
    </div>
  );
}

function Badge({
  children,
  tone = "neutral",
}: {
  children: string;
  tone?: "neutral" | "info" | "success" | "successMuted" | "danger";
}) {
  const toneClasses = {
    neutral: "bg-slate-800 text-slate-200",
    info: "bg-indigo-900/60 text-indigo-200",
    success: "bg-emerald-900/60 text-emerald-200",
    successMuted: "bg-emerald-900/40 text-emerald-200",
    danger: "bg-red-900/60 text-red-200",
  };
  return <span className={`rounded px-2 py-0.5 text-xs ${toneClasses[tone]}`}>{children}</span>;
}

function TextBlock({
  label,
  value,
  variant = "analysis",
}: {
  label: string;
  value: string;
  variant?: "analysis" | "plan";
}) {
  if (!value) return null;
  const labelClass =
    variant === "plan"
      ? "text-xs font-semibold text-slate-300"
      : "text-[11px] font-semibold uppercase tracking-wide text-slate-400";
  const bodyClass =
    variant === "plan"
      ? "whitespace-pre-wrap text-sm text-slate-100 border-l border-slate-700 pl-3"
      : "whitespace-pre-wrap text-sm text-slate-100";
  return (
    <div className="space-y-1">
      <div className={labelClass}>{label}</div>
      <div className={bodyClass}>{value}</div>
    </div>
  );
}

function CollapsibleSection({
  label,
  value,
  isMono = false,
  copyText,
  copyLabel,
}: {
  label: string;
  value: string;
  isMono?: boolean;
  copyText?: string;
  copyLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  if (!value) return null;
  const effectiveCopyText = copyText ?? value;
  const canCopy = Boolean(copyLabel) && Boolean(effectiveCopyText.trim());
  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 flex items-center gap-2 hover:text-slate-100 transition-colors"
          onClick={() => setOpen(prev => !prev)}
        >
          {open ? "▾" : "▸"} {label}
        </button>
        {canCopy && <CopyToClipboardButton text={effectiveCopyText} label={copyLabel ?? ""} />}
      </div>
      {open &&
        (isMono ? (
          <div className="mt-2 rounded-lg border border-slate-700 bg-slate-950 overflow-hidden">
            <pre className="p-3 text-xs font-mono text-slate-200 overflow-x-auto max-h-[400px] overflow-y-auto leading-relaxed">
              <code>{value}</code>
            </pre>
          </div>
        ) : (
          <div className="mt-2 whitespace-pre-wrap text-sm text-slate-100">{value}</div>
        ))}
    </div>
  );
}

function formatMetricValue(value: number | string | undefined): string {
  if (value === undefined || value === null) return "n/a";
  const numericValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numericValue)) return String(value);
  if (Number.isInteger(numericValue)) return numericValue.toString();
  // Format to reasonable precision, removing trailing zeros
  const formatted = numericValue.toPrecision(4);
  return parseFloat(formatted).toString();
}

function formatExecutionTime(value: number | string): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    const rounded = Number.isInteger(value) ? value.toString() : value.toFixed(2);
    return `${rounded.replace(/\.00$/, "")} s`;
  }
  const parsed = Number.parseFloat(String(value));
  if (Number.isFinite(parsed)) {
    const rounded = Number.isInteger(parsed) ? parsed.toString() : parsed.toFixed(2);
    return `${rounded.replace(/\.00$/, "")} s`;
  }
  return `${value}`;
}

function sortMetricData(data: MetricName["data"]) {
  return [...data].sort((a, b) => {
    const aName = a.dataset_name?.toLowerCase() ?? "default";
    const bName = b.dataset_name?.toLowerCase() ?? "default";
    if (aName === "default" && bName !== "default") return -1;
    if (bName === "default" && aName !== "default") return 1;
    return aName.localeCompare(bName);
  });
}

function MetricsSection({ metrics }: { metrics: MetricEntry | null | undefined }) {
  if (!metrics || !metrics.metric_names || metrics.metric_names.length === 0) return null;
  return (
    <div className="space-y-3">
      {metrics.metric_names.map((metric: MetricName) => (
        <div
          key={metric.metric_name}
          className="rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-xs"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-slate-100">{metric.metric_name}</div>
              {metric.description && (
                <div className="mt-1 text-[11px] text-slate-400">{metric.description}</div>
              )}
            </div>
            {metric.lower_is_better !== undefined && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                {metric.lower_is_better ? "Lower is better" : "Higher is better"}
              </span>
            )}
          </div>
          <div className="mt-2 grid grid-cols-[1fr_auto_auto] gap-3 text-[10px] uppercase tracking-wide text-slate-500">
            <div>Dataset</div>
            <div className="text-right">Final</div>
            <div className="text-right">Best</div>
          </div>
          <div className="mt-1 space-y-1.5">
            {sortMetricData(metric.data || []).map((d: MetricName["data"][number], idx: number) => {
              const isBestValue =
                d.final_value !== undefined &&
                d.best_value !== undefined &&
                d.final_value === d.best_value;
              return (
                <div
                  key={`${d.dataset_name ?? "default"}-${idx}`}
                  className="grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-slate-800 py-1 last:border-0"
                >
                  <span className="text-slate-300">{d.dataset_name || "default"}</span>
                  <div
                    className={`text-right font-mono ${
                      isBestValue ? "text-emerald-400 font-semibold" : "text-slate-100"
                    }`}
                  >
                    {formatMetricValue(d.final_value)}
                  </div>
                  <div className="text-right font-mono text-slate-400">
                    {formatMetricValue(d.best_value)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
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
      {analyses.map((analysis: PlotAnalysis | null, idx: number) => {
        if (!analysis) return null;
        return (
          <div
            key={idx}
            className="rounded border border-slate-700 bg-slate-900/50 p-2 text-xs text-slate-200"
          >
            {analysis.plot_path && (
              <div className="text-[11px] font-semibold text-slate-300">{analysis.plot_path}</div>
            )}
            {analysis.analysis && (
              <div className="mt-1 text-sm text-slate-100">{analysis.analysis}</div>
            )}
            {analysis.key_findings && analysis.key_findings.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-slate-300">
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

function normalizeVlmSummary(summary: string | string[] | null | undefined) {
  if (!summary) return [];
  const raw = Array.isArray(summary) ? summary : [summary];
  return raw
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
}

function VlmSection({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <div>
      <ul className="list-disc pl-4 text-xs text-slate-200">
        {lines.map(line => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

const TOOLTIP_CIRCLE_SIZE = 12;

interface HoverNode {
  id: number;
  originalNodeId: number;
  stageId: string;
  excType?: string | null;
  isBest?: boolean;
  isSeedNode?: boolean;
  isSeedAggNode?: boolean;
}

function NodeHoverTooltip({
  position,
  node,
  nodeType,
}: {
  position: { x: number; y: number };
  node: HoverNode;
  nodeType: ReturnType<typeof getNodeType>;
}) {
  const config = NODE_TYPE_COLORS[nodeType];
  const borderStyle = getBorderStyle(node);
  const borderConfig = BORDER_STYLES[borderStyle];

  // Determine status label
  let statusLabel = "Succeeded";
  let statusColor = "text-slate-300";
  if (node.excType) {
    statusLabel = "Abandoned";
    statusColor = "text-red-300";
  } else if (node.isBest) {
    statusLabel = "Best";
    statusColor = "text-emerald-300";
  }

  return (
    <div
      className="pointer-events-none absolute z-10 rounded-lg border border-slate-700 bg-slate-900/95 p-2.5 text-xs text-slate-200 shadow-lg backdrop-blur-sm"
      style={{ left: position.x, top: position.y }}
    >
      <div className="flex items-center gap-2">
        <svg
          width={TOOLTIP_CIRCLE_SIZE + 4}
          height={TOOLTIP_CIRCLE_SIZE + 4}
          viewBox={`0 0 ${TOOLTIP_CIRCLE_SIZE + 4} ${TOOLTIP_CIRCLE_SIZE + 4}`}
          className="flex-shrink-0"
        >
          <circle
            cx={(TOOLTIP_CIRCLE_SIZE + 4) / 2}
            cy={(TOOLTIP_CIRCLE_SIZE + 4) / 2}
            r={TOOLTIP_CIRCLE_SIZE / 2}
            fill={config.color}
            stroke={borderConfig.stroke}
            strokeWidth="1.5"
          />
        </svg>
        <div>
          <div className="font-semibold text-slate-100">{config.label}</div>
          <div className="text-[10px] text-slate-400">
            Node {node.originalNodeId} · <span className={statusColor}>{statusLabel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
