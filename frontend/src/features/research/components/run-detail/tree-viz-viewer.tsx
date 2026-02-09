"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ArtifactMetadata, TreeVizItem, MergedTreeViz } from "@/types/research";
import { fetchDownloadUrl } from "@/shared/lib/downloads";
import { stageName } from "@/shared/lib/stage-utils";
import {
  getNodeType,
  getBorderStyle,
  NODE_TYPE_COLORS,
  BORDER_STYLES,
  NODE_TYPE_LONG_DESCRIPTIONS,
} from "@/shared/lib/tree-colors";
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Maximize2 } from "lucide-react";
import { ReactFlowTree } from "./react-flow-tree";
import { Markdown } from "@/shared/components/Markdown";
import "highlight.js/styles/github-dark.css";

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

  // Handle node hover from React Flow
  const handleNodeHover = (nodeId: number | null, position: { x: number; y: number } | null) => {
    setHoveredNodeId(nodeId);
    setHoverPosition(position);
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
    <div className="flex flex-col md:flex-row w-full gap-4 min-h-[400px] md:min-h-[500px] items-stretch">
      <div className="w-full md:w-1/2 min-h-[300px] flex flex-col relative">
        {/* Tooltip rendered outside the overflow-hidden container */}
        {hoveredNodeId !== null && hoverPosition && nodes[hoveredNodeId] && (
          <NodeHoverTooltip
            position={hoverPosition}
            node={nodes[hoveredNodeId]}
            nodeType={getNodeType(hoveredNodeId, { nodes, edges })}
          />
        )}
        <div className="relative flex-1 border border-slate-700 bg-slate-900 rounded-lg overflow-hidden">
          <ReactFlowTree
            nodes={nodes}
            edges={edges}
            selectedNodeId={selected}
            onNodeSelect={setSelected}
            onNodeHover={handleNodeHover}
          />
        </div>
      </div>
      <div className="w-full md:w-1/2 relative min-h-[300px] md:min-h-0">
        <div className="md:absolute md:inset-0 rounded-lg border border-slate-700 bg-slate-800 p-4 text-sm text-slate-100 overflow-y-auto">
          {selectedNode ? (
            <>
              <div className="space-y-4">
                <InfoCard title="Overview">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-slate-50 leading-tight">
                        Node {selectedNode.originalNodeId ?? selectedNode.id}
                      </h3>
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
                    {selectedNode.stageId && (
                      <p className="text-xs text-slate-400">{stageName(selectedNode.stageId)}</p>
                    )}
                  </div>
                  {(selectedNode.ablationName || selectedNode.hyperparamName) && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {selectedNode.ablationName && (
                        <span className="rounded-md bg-slate-700/50 px-2 py-1 text-[11px] font-medium text-slate-200">
                          Ablation: {selectedNode.ablationName}
                        </span>
                      )}
                      {selectedNode.hyperparamName && (
                        <span className="rounded-md bg-slate-700/50 px-2 py-1 text-[11px] font-medium text-slate-200">
                          Hyperparam: {selectedNode.hyperparamName}
                        </span>
                      )}
                    </div>
                  )}
                  {(selectedNode.execTime !== null && selectedNode.execTime !== undefined) ||
                  selectedNode.execTimeFeedback ? (
                    <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-400 space-y-0.5">
                      {selectedNode.execTime !== null && selectedNode.execTime !== undefined && (
                        <div className="flex items-center gap-1.5">
                          <span>Execution time:</span>
                          <span className="font-medium text-slate-200">
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
                    <div className="text-[13px] font-medium text-red-100">
                      {selectedNode.excType}
                    </div>
                    {selectedNode.excInfo && selectedNode.excInfo.args && (
                      <div className="mt-2 text-xs text-red-200/80 leading-relaxed">
                        {String(selectedNode.excInfo.args[0])}
                      </div>
                    )}
                  </InfoCard>
                )}

                <InfoCard title="Node Type">
                  <div className="text-[13px] font-semibold text-slate-100">
                    {selectedNodeTypeLabel}
                  </div>
                  <div className="mt-1.5 text-xs text-slate-400 leading-relaxed">
                    {selectedNodeTypeDescription}
                  </div>
                </InfoCard>

                {showReasoning && (
                  <InfoCard title="Reasoning" collapsible>
                    <div className="space-y-6">
                      <TextBlock label="Analysis" value={normalizedAnalysis} variant="analysis" />
                      {selectedNode.isSeedNode ? null : normalizedPlan ? (
                        <div className="pt-4 mt-2 border-t border-slate-600">
                          <TextBlock label="Plan" value={normalizedPlan} variant="plan" />
                        </div>
                      ) : null}
                    </div>
                  </InfoCard>
                )}

                {hasMetrics && (
                  <InfoCard title="Metrics" collapsible>
                    <MetricsSection metrics={selectedNode.metrics} />
                  </InfoCard>
                )}

                {datasetsTested.length > 0 && (
                  <InfoCard title="Datasets Tested" collapsible>
                    <ul className="list-disc pl-4 text-[13px] text-slate-200 space-y-0.5">
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

                {normalizedVlmSummary.length > 0 && (
                  <InfoCard title="VLM Feedback" collapsible>
                    <VlmSection lines={normalizedVlmSummary} />
                  </InfoCard>
                )}

                <InfoCard title="Sources" collapsible>
                  <div className="space-y-1.5 pl-4">
                    <CollapsibleSection
                      label="Plot Plan"
                      value={selectedNode.plotPlan}
                      copyLabel="Copy plot plan"
                    />
                    <CollapsibleSection
                      label="Plot Code"
                      value={selectedNode.plotCode}
                      renderAs="python"
                      copyLabel="Copy plot code"
                    />
                    <CollapsibleSection
                      label="Coding Agent Task"
                      value={selectedNode.codexTask}
                      renderAs="markdown"
                      copyLabel="Copy coding agent task"
                    />
                    <CollapsibleSection
                      label="Final Code"
                      value={selectedNode.code}
                      renderAs="python"
                      copyLabel="Copy code"
                    />
                  </div>
                </InfoCard>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[200px]">
              <p className="text-sm text-slate-400">Select a node to view details</p>
            </div>
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
    tone === "danger" ? "border-red-900/50 bg-red-950/30" : "border-slate-700/80 bg-slate-900/50";
  const sizeClasses = size === "compact" ? "p-2.5" : "p-3.5";
  return (
    <div className={`rounded-lg border ${sizeClasses} ${toneClasses}`}>
      <div className="flex items-center justify-between gap-2">
        {collapsible ? (
          <button
            type="button"
            className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5"
            onClick={() => setOpen(prev => !prev)}
          >
            <span className="text-[9px]">{open ? "▼" : "▶"}</span>
            <span>{title}</span>
          </button>
        ) : (
          <CardTitle>{title}</CardTitle>
        )}
      </div>
      {(!collapsible || open) && <div className="mt-2.5">{children}</div>}
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
    neutral: "bg-slate-700/60 text-slate-200 border-slate-600/50",
    info: "bg-indigo-900/50 text-indigo-200 border-indigo-700/50",
    success: "bg-emerald-900/50 text-emerald-200 border-emerald-700/50",
    successMuted: "bg-emerald-900/30 text-emerald-300/80 border-emerald-800/30",
    danger: "bg-red-900/50 text-red-200 border-red-700/50",
  };
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${toneClasses[tone]}`}>
      {children}
    </span>
  );
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
  const labelClass = "text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-1.5";
  const bodyClass =
    variant === "plan"
      ? "whitespace-pre-wrap text-[13px] leading-relaxed text-slate-100 border-l-2 border-slate-600 pl-3"
      : "whitespace-pre-wrap text-[13px] leading-relaxed text-slate-200";
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
  renderAs = "plain",
  copyText,
  copyLabel,
}: {
  label: string;
  value: string;
  isMono?: boolean;
  renderAs?: "plain" | "markdown" | "python";
  copyText?: string;
  copyLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Format content for rendering - must be before early return
  const formattedContent = useMemo(() => {
    if (renderAs === "python") {
      return "```python\n" + value + "\n```";
    }
    return value;
  }, [value, renderAs]);

  if (!value) return null;
  const effectiveCopyText = copyText ?? value;
  const canCopy = Boolean(copyLabel) && Boolean(effectiveCopyText.trim());

  const renderContent = (inDialog = false) => {
    if (renderAs === "markdown" || renderAs === "python") {
      return (
        <div
          className={`${inDialog ? "h-full overflow-auto p-4" : "max-h-[400px] overflow-y-auto p-3"} [&_pre]:!bg-transparent [&_pre]:!border-0 [&_pre]:!p-0 [&_pre]:!m-0 [&_code]:text-[12px] [&_p]:text-[13px] [&_p]:text-slate-200 [&_li]:text-[13px] [&_li]:text-slate-200`}
        >
          <Markdown className="text-slate-200">{formattedContent}</Markdown>
        </div>
      );
    }
    // Plain mono text
    return (
      <pre
        className={`${inDialog ? "h-full p-4" : "p-3 pr-10 max-h-[400px]"} text-[12px] font-mono text-slate-200 overflow-y-auto leading-relaxed whitespace-pre-wrap break-words`}
      >
        <code>{value}</code>
      </pre>
    );
  };

  const showExpandButton = isMono || renderAs === "markdown" || renderAs === "python";

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-[12px] font-medium text-slate-300 flex items-center gap-1.5 hover:text-slate-100 transition-colors"
          onClick={() => setOpen(prev => !prev)}
        >
          <span className="text-[9px] text-slate-500">{open ? "▼" : "▶"}</span>
          <span>{label}</span>
        </button>
        {canCopy && <CopyToClipboardButton text={effectiveCopyText} label={copyLabel ?? ""} />}
      </div>
      {open &&
        (showExpandButton ? (
          <div className="mt-2 rounded-lg border border-slate-700/80 bg-slate-950 overflow-hidden relative">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="absolute top-2 right-2 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors z-10"
              title="Expand"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
            {renderContent(false)}
          </div>
        ) : (
          <div className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-slate-200">
            {value}
          </div>
        ))}

      {/* Expanded dialog */}
      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="!w-[98vw] !max-w-[98vw] !h-[95vh] !max-h-[95vh] bg-slate-900 border-slate-700 flex flex-col">
          <DialogHeader className="flex-shrink-0">
            <div className="flex items-center justify-between gap-4 pr-8">
              <DialogTitle className="text-slate-100">{label}</DialogTitle>
              {canCopy && (
                <CopyToClipboardButton text={effectiveCopyText} label={copyLabel ?? ""} />
              )}
            </div>
          </DialogHeader>
          <div className="flex-1 min-h-0 rounded-lg border border-slate-700/80 bg-slate-950 overflow-hidden">
            {renderContent(true)}
          </div>
        </DialogContent>
      </Dialog>
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
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 whitespace-nowrap">
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
      className="pointer-events-none fixed z-50 rounded-lg border border-slate-700 bg-slate-900/95 p-2.5 text-xs text-slate-200 shadow-lg backdrop-blur-sm"
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
