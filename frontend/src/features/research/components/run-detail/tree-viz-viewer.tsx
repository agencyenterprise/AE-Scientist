"use client";

import { useMemo, useState } from "react";
import type { ArtifactMetadata, TreeVizItem } from "@/types/research";
import { config } from "@/shared/lib/config";

type TreeVizPayload = TreeVizItem["viz"] & {
  layout: number[][];
  edges: number[][];
  code?: string[];
  plan?: string[];
  analysis?: string[];
  metrics?: Array<{
    metric_names?: Array<{
      metric_name: string;
      lower_is_better?: boolean;
      description?: string;
      data: Array<{ dataset_name?: string; final_value?: number; best_value?: number }>;
    }>;
  } | null>;
  exc_type?: Array<string | null>;
  exc_info?: Array<{ args?: unknown[] } | null>;
  exc_stack?: Array<unknown>;
  plot_plan?: Array<string | null>;
  plot_code?: Array<string | null>;
  plot_analyses?: Array<
    Array<{ plot_path?: string; analysis?: string; key_findings?: string[] } | null>
  >;
  vlm_feedback_summary?: Array<string | string[] | null>;
  datasets_successfully_tested?: Array<string[] | null>;
  exec_time?: Array<number | string | null>;
  exec_time_feedback?: Array<string | null>;
  is_best_node?: Array<boolean>;
};

interface Props {
  viz: TreeVizItem;
  artifacts: ArtifactMetadata[];
  conversationId: number | null;
  runId: string;
}

const NODE_SIZE = 14;
const BLUE = "#1a73e8";
const GRAY = "#6b7280";

export function TreeVizViewer({ viz, artifacts, conversationId, runId }: Props) {
  const payload = viz.viz as TreeVizPayload;
  const [selected, setSelected] = useState<number>(0);

  const nodes = useMemo(() => {
    return (payload.layout || []).map((coords, idx) => ({
      id: idx,
      x: coords[0],
      y: coords[1],
      code: payload.code?.[idx] ?? "",
      plan: payload.plan?.[idx] ?? "",
      analysis: payload.analysis?.[idx] ?? "",
      excType: payload.exc_type?.[idx],
      excInfo: payload.exc_info?.[idx],
      metrics: payload.metrics?.[idx],
      plotPlan: payload.plot_plan?.[idx] ?? "",
      plotCode: payload.plot_code?.[idx] ?? "",
      plotAnalyses: payload.plot_analyses?.[idx] ?? [],
      vlmFeedbackSummary: payload.vlm_feedback_summary?.[idx] ?? "",
      datasetsTested: payload.datasets_successfully_tested?.[idx] ?? [],
      execTime: payload.exec_time?.[idx],
      execTimeFeedback: payload.exec_time_feedback?.[idx] ?? "",
      isBest: payload.is_best_node?.[idx] ?? false,
    }));
  }, [payload]);

  const edges = payload.edges || [];

  const selectedNode = nodes[selected];
  const plotFiles = payload.plots ?? [];
  const plotPaths = payload.plot_paths ?? [];
  const plotsForNode = selectedNode ? plotFiles[selected] ?? plotPaths[selected] ?? [] : [];
  const plotList = Array.isArray(plotsForNode) ? plotsForNode : plotsForNode ? [plotsForNode] : [];

  const plotUrls = useMemo(() => {
    if (!conversationId) return [];
    const baseUrl = config.apiUrl.replace(/\/$/, "");
    return plotList
      .map(p => {
        const filename = p?.toString().split("/").pop();
        if (!filename) return null;
        const artifact = artifacts.find(a => a.filename === filename);
        if (!artifact) return null;
        const downloadPath = artifact.download_path || "";
        const normalizedPath =
          downloadPath.startsWith("/api") && baseUrl.endsWith("/api")
            ? downloadPath.slice(4)
            : downloadPath;
        return `${baseUrl}${normalizedPath}`;
      })
      .filter((u): u is string => Boolean(u));
  }, [artifacts, conversationId, plotList]);

  return (
    <div className="flex w-full gap-4">
      <div className="relative w-1/2 border border-slate-700 bg-slate-900">
        <svg viewBox="0 0 100 100" className="w-full h-[320px]">
          {edges.map(([parent, child], idx) => {
            const p = nodes[parent];
            const c = nodes[child];
            if (!p || !c) return null;
            const px = p.x * 90 + 5;
            const py = p.y * 90 + 5;
            const cx = c.x * 90 + 5;
            const cy = c.y * 90 + 5;
            return (
              <line
                key={idx}
                x1={px}
                y1={py}
                x2={cx}
                y2={cy}
                stroke="#cbd5e1"
                strokeWidth={0.6}
              />
            );
          })}
          {nodes.map(node => {
            const isSelected = node.id === selected;
            const color = node.excType ? GRAY : node.isBest ? "#10b981" : BLUE;
            const cx = node.x * 90 + 5;
            const cy = node.y * 90 + 5;
            return (
              <g
                key={node.id}
                onClick={() => setSelected(node.id)}
                className="cursor-pointer"
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={NODE_SIZE / 3}
                  fill={color}
                  stroke={isSelected ? "#fbbf24" : "#0f172a"}
                  strokeWidth={isSelected ? 1.2 : 0.6}
                />
              </g>
            );
          })}
        </svg>
      </div>
      <div className="w-1/2 rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-100 max-h-[600px] overflow-y-auto">
        {selectedNode ? (
          <>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-base font-semibold">Node {selectedNode.id}</h3>
              {selectedNode.excType ? (
                <span className="text-xs text-red-300">Abandoned</span>
              ) : selectedNode.isBest ? (
                <span className="text-xs text-emerald-300">Best</span>
              ) : (
                <span className="text-xs text-emerald-300">Succeeded</span>
              )}
            </div>
            <div className="space-y-2">
              <Section label="Plan" value={selectedNode.plan} />
              <Section label="Analysis" value={selectedNode.analysis} />
              <MetricsSection metrics={selectedNode.metrics} />
              <ExecSection execTime={selectedNode.execTime} feedback={selectedNode.execTimeFeedback} />
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

function Section({ label, value, isMono = false }: { label: string; value: string; isMono?: boolean }) {
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
  if (!value) return null;
  const [open, setOpen] = useState(false);
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
        <div className={`mt-1 whitespace-pre-wrap ${isMono ? "font-mono text-xs" : ""}`}>{value}</div>
      )}
    </div>
  );
}

function MetricsSection({ metrics }: { metrics: TreeVizPayload["metrics"][number] }) {
  if (!metrics || !metrics.metric_names || metrics.metric_names.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-300">Metrics</div>
      {metrics.metric_names.map(metric => (
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
              {(metric.data || []).map((d, idx) => (
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

function ExecSection({ execTime, feedback }: { execTime: number | string | null | undefined; feedback: string }) {
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
  analyses: TreeVizPayload["plot_analyses"][number] | undefined;
}) {
  if (!analyses || analyses.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-300">Plot Analyses</div>
      {analyses.map((analysis, idx) => {
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
