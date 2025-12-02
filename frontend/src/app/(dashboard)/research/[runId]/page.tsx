"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { formatDistanceToNow, format } from "date-fns";
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Package,
  Download,
  FlaskConical,
  Cpu,
  Calendar,
  Activity,
  FileText,
  Terminal,
  StopCircle,
  Wifi,
  WifiOff,
} from "lucide-react";
import { apiFetch } from "@/shared/lib/api-client";
import { config } from "@/shared/lib/config";
import { useResearchRunSSE } from "@/features/research/hooks/useResearchRunSSE";

// Types from the existing API response
interface ResearchRunInfo {
  run_id: string;
  status: string;
  idea_id: number;
  idea_version_id: number;
  pod_id: string | null;
  pod_name: string | null;
  gpu_type: string | null;
  public_ip: string | null;
  ssh_port: string | null;
  pod_host_id: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  heartbeat_failures: number;
  created_at: string;
  updated_at: string;
  start_deadline_at: string | null;
}

interface StageProgress {
  stage: string;
  iteration: number;
  max_iterations: number;
  progress: number;
  total_nodes: number;
  buggy_nodes: number;
  good_nodes: number;
  best_metric: string | null;
  eta_s: number | null;
  latest_iteration_time_s: number | null;
  created_at: string;
}

interface LogEntry {
  id: number;
  level: string;
  message: string;
  created_at: string;
}

interface NodeEvent {
  id: number;
  stage: string;
  node_id: string | null;
  summary: Record<string, unknown>;
  created_at: string;
}

interface ArtifactMetadata {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
  download_path: string;
}

interface ResearchRunDetails {
  run: ResearchRunInfo;
  stage_progress: StageProgress[];
  logs: LogEntry[];
  experiment_nodes: NodeEvent[];
  artifacts: ArtifactMetadata[];
}

function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-400">
          <CheckCircle2 className="h-5 w-5" />
          Completed
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-2 rounded-full bg-sky-500/15 px-4 py-2 text-sm font-medium text-sky-400">
          <Loader2 className="h-5 w-5 animate-spin" />
          Running
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-2 rounded-full bg-red-500/15 px-4 py-2 text-sm font-medium text-red-400">
          <AlertCircle className="h-5 w-5" />
          Failed
        </span>
      );
    case "pending":
    default:
      return (
        <span className="inline-flex items-center gap-2 rounded-full bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-400">
          <Clock className="h-5 w-5" />
          Pending
        </span>
      );
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}

function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, "PPpp");
  } catch {
    return dateString;
  }
}

function getLogLevelColor(level: string): string {
  switch (level.toLowerCase()) {
    case "error":
      return "text-red-400";
    case "warn":
    case "warning":
      return "text-amber-400";
    case "info":
      return "text-sky-400";
    case "debug":
      return "text-slate-400";
    default:
      return "text-slate-300";
  }
}

export default function ResearchRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;

  const [details, setDetails] = useState<ResearchRunDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [stopPending, setStopPending] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);

  // SSE callback handlers
  const handleInitialData = useCallback((data: ResearchRunDetails) => {
    setDetails(data);
    setLoading(false);
    setError(null);
  }, []);

  const handleStageProgress = useCallback((event: StageProgress) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            stage_progress: [...prev.stage_progress, event],
          }
        : null
    );
  }, []);

  const handleLog = useCallback((event: LogEntry) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            logs: [event, ...prev.logs],
          }
        : null
    );
  }, []);

  const handleArtifact = useCallback((event: ArtifactMetadata) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            artifacts: [...prev.artifacts, event],
          }
        : null
    );
  }, []);

  const handleRunUpdate = useCallback((run: ResearchRunInfo) => {
    setDetails(prev => (prev ? { ...prev, run } : null));
  }, []);

  const handleComplete = useCallback((status: string) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            run: { ...prev.run, status },
          }
        : null
    );
  }, []);

  const handleSSEError = useCallback((errorMsg: string) => {
    // eslint-disable-next-line no-console
    console.error("SSE error:", errorMsg);
  }, []);

  // Use SSE for real-time updates
  const { isConnected, connectionError, reconnect } = useResearchRunSSE({
    runId,
    conversationId,
    enabled:
      !!conversationId &&
      (details?.run.status === "running" || details?.run.status === "pending" || !details),
    onInitialData: handleInitialData,
    onStageProgress: handleStageProgress,
    onLog: handleLog,
    onArtifact: handleArtifact,
    onRunUpdate: handleRunUpdate,
    onComplete: handleComplete,
    onError: handleSSEError,
  });

  // Initial load to get conversation_id (SSE takes over after that)
  useEffect(() => {
    const fetchConversationId = async () => {
      try {
        const runInfo = await apiFetch<{ run_id: string; conversation_id: number }>(
          `/research-runs/${runId}/`
        );
        setConversationId(runInfo.conversation_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load research run");
        setLoading(false);
      }
    };
    fetchConversationId();
  }, [runId]);

  const handleStopRun = async () => {
    if (!conversationId || stopPending) {
      return;
    }
    try {
      setStopError(null);
      setStopPending(true);
      await apiFetch(`/conversations/${conversationId}/idea/research-run/${runId}/stop`, {
        method: "POST",
      });
      // SSE will automatically receive the status update
    } catch (err) {
      setStopError(err instanceof Error ? err.message : "Failed to stop research run");
    } finally {
      setStopPending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (error || !details) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-red-400" />
        <p className="text-lg text-slate-300">{error || "Failed to load details"}</p>
        <button
          onClick={() => router.push("/research")}
          className="text-sm text-emerald-400 hover:text-emerald-300"
        >
          Back to Research Runs
        </button>
      </div>
    );
  }

  const { run, stage_progress, logs, artifacts } = details;
  const latestProgress = stage_progress[stage_progress.length - 1];
  const canStopRun =
    conversationId !== null && (run.status === "running" || run.status === "pending");

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/research")}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-white">{run.run_id}</h1>
            {getStatusBadge(run.status)}
            {canStopRun && (
              <button
                onClick={handleStopRun}
                disabled={stopPending}
                className="inline-flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-200 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {stopPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Stopping...
                  </>
                ) : (
                  <>
                    <StopCircle className="h-4 w-4" />
                    Stop Run
                  </>
                )}
              </button>
            )}
            {/* Connection status indicator */}
            {(run.status === "running" || run.status === "pending") && (
              <>
                {isConnected ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
                    <Wifi className="h-3 w-3" />
                    Live
                  </span>
                ) : connectionError ? (
                  <button
                    onClick={reconnect}
                    className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
                  >
                    <WifiOff className="h-3 w-3" />
                    Reconnect
                  </button>
                ) : null}
              </>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Created {formatRelativeTime(run.created_at)}
          </p>
          {stopError && (
            <p className="mt-2 text-sm text-red-400" role="alert">
              {stopError}
            </p>
          )}
        </div>
      </div>

      {/* Error Message */}
      {run.error_message && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
            <div>
              <h3 className="font-medium text-red-400">Error</h3>
              <p className="mt-1 text-sm text-red-300">{run.error_message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Overview Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
              <FlaskConical className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-slate-400">Current Stage</p>
              <p
                className="break-words font-medium text-white"
                title={latestProgress?.stage || "Pending"}
              >
                {latestProgress?.stage || "Pending"}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-sky-500/15">
              <Activity className="h-5 w-5 text-sky-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-slate-400">Progress</p>
              <p className="font-medium text-white">
                {latestProgress ? `${Math.round(latestProgress.progress * 100)}%` : "-"}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-purple-500/15">
              <Cpu className="h-5 w-5 text-purple-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-slate-400">GPU Type</p>
              <p className="break-words font-medium text-white">{run.gpu_type || "-"}</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
              <Package className="h-5 w-5 text-amber-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-slate-400">Artifacts</p>
              <p className="font-medium text-white">{artifacts.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Details */}
      {latestProgress && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Stage Progress</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs text-slate-400">Iteration</p>
              <p className="text-lg font-medium text-white">
                {latestProgress.iteration} / {latestProgress.max_iterations}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Best Metric</p>
              <p className="text-lg font-medium text-white">{latestProgress.best_metric || "-"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Total Nodes</p>
              <p className="text-lg font-medium text-white">{latestProgress.total_nodes}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Good / Buggy</p>
              <p className="text-lg font-medium text-white">
                <span className="text-emerald-400">{latestProgress.good_nodes}</span>
                {" / "}
                <span className="text-red-400">{latestProgress.buggy_nodes}</span>
              </p>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${Math.round(latestProgress.progress * 100)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Artifacts */}
      {artifacts.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Package className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">Artifacts</h2>
          </div>
          <div className="divide-y divide-slate-800">
            {artifacts.map(artifact => (
              <div
                key={artifact.id}
                className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800">
                    <FileText className="h-5 w-5 text-slate-400" />
                  </div>
                  <div>
                    <p className="font-medium text-white">{artifact.filename}</p>
                    <p className="text-xs text-slate-400">
                      {artifact.artifact_type} &middot; {formatBytes(artifact.file_size)} &middot;{" "}
                      {formatRelativeTime(artifact.created_at)}
                    </p>
                  </div>
                </div>
                <a
                  href={`${config.apiBaseUrl}${artifact.download_path}`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                >
                  <Download className="h-4 w-4" />
                  Download
                </a>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Logs */}
      {logs.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Terminal className="h-5 w-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-white">Logs</h2>
            <span className="text-sm text-slate-400">({logs.length})</span>
          </div>
          <div className="max-h-96 overflow-y-auto rounded-lg bg-slate-950 p-4 font-mono text-sm">
            {logs.slice(0, 100).map(log => (
              <div key={log.id} className="flex gap-3 py-1">
                <span className="flex-shrink-0 text-slate-600">
                  {format(new Date(log.created_at), "HH:mm:ss")}
                </span>
                <span
                  className={`flex-shrink-0 uppercase ${getLogLevelColor(log.level)}`}
                  style={{ width: "50px" }}
                >
                  {log.level}
                </span>
                <span className="text-slate-300">{log.message}</span>
              </div>
            ))}
            {logs.length > 100 && (
              <p className="mt-2 text-slate-500">... and {logs.length - 100} more entries</p>
            )}
          </div>
        </div>
      )}

      {/* Run Details */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        <div className="mb-4 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-slate-400" />
          <h2 className="text-lg font-semibold text-white">Run Details</h2>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-400">Run ID</dt>
            <dd className="font-mono text-sm text-white">{run.run_id}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Idea ID</dt>
            <dd className="font-mono text-sm text-white">{run.idea_id}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Idea Version ID</dt>
            <dd className="font-mono text-sm text-white">{run.idea_version_id}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Created At</dt>
            <dd className="text-sm text-white">{formatDateTime(run.created_at)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Updated At</dt>
            <dd className="text-sm text-white">{formatDateTime(run.updated_at)}</dd>
          </div>
          {run.last_heartbeat_at && (
            <div>
              <dt className="text-xs text-slate-400">Last Heartbeat</dt>
              <dd className="text-sm text-white">{formatRelativeTime(run.last_heartbeat_at)}</dd>
            </div>
          )}
          {run.pod_name && (
            <div>
              <dt className="text-xs text-slate-400">Pod Name</dt>
              <dd className="text-sm text-white">{run.pod_name}</dd>
            </div>
          )}
          {conversationId && (
            <div>
              <dt className="text-xs text-slate-400">Conversation</dt>
              <dd>
                <a
                  href={`/conversations/${conversationId}`}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  View Conversation #{conversationId}
                </a>
              </dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
