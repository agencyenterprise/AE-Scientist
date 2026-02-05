"use client";

import { useState, useMemo } from "react";
import {
  Terminal,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  XCircle,
  Info,
  Sparkles,
  Layers,
  FlaskConical,
  FileText,
  Beaker,
  Settings2,
  BookOpen,
  List,
} from "lucide-react";
import { format } from "date-fns";
import type { LogEntry } from "@/types/research";
import { cn } from "@/shared/lib/utils";

// ===== Types =====
type LogLevelFilter = "all" | "info" | "warn" | "error";
type ViewMode = "narrative" | "detailed";

interface StageConfig {
  id: string;
  name: string;
  shortName: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
}

interface GroupedLogs {
  stage: StageConfig;
  logs: LogEntry[];
  errorCount: number;
  warnCount: number;
}

// ===== Constants =====
const STAGE_CONFIGS: StageConfig[] = [
  {
    id: "1_baseline",
    name: "Baseline Implementation",
    shortName: "Baseline",
    icon: <Beaker className="h-4 w-4" />,
    color: "text-violet-400",
    bgColor: "bg-violet-500/10",
    borderColor: "border-violet-500/30",
  },
  {
    id: "2_baseline_tuning",
    name: "Baseline Tuning",
    shortName: "Tuning",
    icon: <Settings2 className="h-4 w-4" />,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
  },
  {
    id: "3_creative",
    name: "Creative Research",
    shortName: "Creative",
    icon: <Sparkles className="h-4 w-4" />,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
  },
  {
    id: "4_ablation",
    name: "Ablation Studies",
    shortName: "Ablation",
    icon: <FlaskConical className="h-4 w-4" />,
    color: "text-rose-400",
    bgColor: "bg-rose-500/10",
    borderColor: "border-rose-500/30",
  },
  {
    id: "5_paper",
    name: "Paper Generation",
    shortName: "Paper",
    icon: <FileText className="h-4 w-4" />,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
  },
];

const GENERAL_STAGE: StageConfig = {
  id: "general",
  name: "General",
  shortName: "General",
  icon: <Layers className="h-4 w-4" />,
  color: "text-slate-400",
  bgColor: "bg-slate-500/10",
  borderColor: "border-slate-500/30",
};

const LOG_FILTER_CONFIG: Record<LogLevelFilter, { label: string; activeClass: string }> = {
  all: { label: "All", activeClass: "bg-slate-600 text-white" },
  info: { label: "Info", activeClass: "bg-sky-600 text-white" },
  warn: { label: "Warn", activeClass: "bg-amber-600 text-white" },
  error: { label: "Error", activeClass: "bg-red-600 text-white" },
};

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];

const STORAGE_KEY = "ae-scientist-logs-view-mode";

// ===== Utility Functions =====
function getStageFromMessage(message: string): StageConfig {
  const lowerMessage = message.toLowerCase();

  // Check for stage indicators in the message
  if (
    lowerMessage.includes("stage 1") ||
    (lowerMessage.includes("baseline") && !lowerMessage.includes("tuning"))
  ) {
    return STAGE_CONFIGS[0];
  }
  if (lowerMessage.includes("stage 2") || lowerMessage.includes("tuning")) {
    return STAGE_CONFIGS[1];
  }
  if (lowerMessage.includes("stage 3") || lowerMessage.includes("creative")) {
    return STAGE_CONFIGS[2];
  }
  if (lowerMessage.includes("stage 4") || lowerMessage.includes("ablation")) {
    return STAGE_CONFIGS[3];
  }
  if (lowerMessage.includes("stage 5") || lowerMessage.includes("paper")) {
    return STAGE_CONFIGS[4];
  }

  // Check for stage number pattern
  const stageMatch = message.match(/(\d)_/);
  if (stageMatch) {
    const stageNum = parseInt(stageMatch[1], 10);
    if (stageNum >= 1 && stageNum <= 5) {
      return STAGE_CONFIGS[stageNum - 1];
    }
  }

  return GENERAL_STAGE;
}

function getLogLevelStyles(level: string): { color: string; bg: string; icon: React.ReactNode } {
  const normalizedLevel = level.toLowerCase();
  switch (normalizedLevel) {
    case "error":
      return {
        color: "text-red-400",
        bg: "bg-red-500/10",
        icon: <XCircle className="h-3.5 w-3.5" />,
      };
    case "warn":
    case "warning":
      return {
        color: "text-amber-400",
        bg: "bg-amber-500/10",
        icon: <AlertTriangle className="h-3.5 w-3.5" />,
      };
    case "info":
    default:
      return {
        color: "text-sky-400",
        bg: "bg-transparent",
        icon: <Info className="h-3.5 w-3.5" />,
      };
  }
}

function groupLogsByStage(logs: LogEntry[]): GroupedLogs[] {
  const groups = new Map<string, { stage: StageConfig; logs: LogEntry[] }>();

  // Initialize all stages (maintains order)
  [...STAGE_CONFIGS, GENERAL_STAGE].forEach(stage => {
    groups.set(stage.id, { stage, logs: [] });
  });

  // Group logs
  logs.forEach(log => {
    const stage = getStageFromMessage(log.message);
    const group = groups.get(stage.id);
    if (group) {
      group.logs.push(log);
    }
  });

  // Convert to array and add counts, filter empty groups
  return Array.from(groups.values())
    .filter(g => g.logs.length > 0)
    .map(g => ({
      ...g,
      errorCount: g.logs.filter(l => l.level.toLowerCase() === "error").length,
      warnCount: g.logs.filter(l => ["warn", "warning"].includes(l.level.toLowerCase())).length,
    }));
}

function summarizeStage(logs: LogEntry[]): string {
  const errorCount = logs.filter(l => l.level.toLowerCase() === "error").length;
  const warnCount = logs.filter(l => ["warn", "warning"].includes(l.level.toLowerCase())).length;

  if (errorCount > 0) {
    return `${errorCount} error${errorCount > 1 ? "s" : ""} encountered`;
  }
  if (warnCount > 0) {
    return `${warnCount} warning${warnCount > 1 ? "s" : ""}, otherwise running smoothly`;
  }
  return "Running smoothly";
}

// ===== Components =====
interface ResearchLogsListProps {
  logs: LogEntry[];
}

// Helper to get initial view mode from localStorage
function getInitialViewMode(): ViewMode {
  if (typeof window === "undefined") return "narrative";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "narrative" || stored === "detailed") {
    return stored;
  }
  return "narrative";
}

export function ResearchLogsList({ logs }: ResearchLogsListProps) {
  const [activeFilter, setActiveFilter] = useState<LogLevelFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>(getInitialViewMode);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());

  // Save preference to localStorage
  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    localStorage.setItem(STORAGE_KEY, mode);
  };

  // Filter logs
  const filteredLogs = useMemo(() => {
    if (activeFilter === "all") return logs;
    return logs.filter(log => {
      const level = log.level.toLowerCase();
      if (activeFilter === "warn") {
        return level === "warn" || level === "warning";
      }
      return level === activeFilter;
    });
  }, [logs, activeFilter]);

  // Group logs by stage
  const groupedLogs = useMemo(() => groupLogsByStage(filteredLogs), [filteredLogs]);

  // Compute stages with errors for auto-expansion
  const stagesWithErrors = useMemo(
    () => new Set(groupedLogs.filter(g => g.errorCount > 0).map(g => g.stage.id)),
    [groupedLogs]
  );

  // Track manually toggled stages (user overrides)
  const [manuallyToggledStages, setManuallyToggledStages] = useState<Set<string>>(new Set());

  // Compute effective expanded stages: auto-expand errors, but respect manual toggles
  const expandedStages = useMemo(() => {
    const expanded = new Set(stagesWithErrors);
    manuallyToggledStages.forEach(stageId => {
      if (expanded.has(stageId)) {
        expanded.delete(stageId);
      } else {
        expanded.add(stageId);
      }
    });
    return expanded;
  }, [stagesWithErrors, manuallyToggledStages]);

  const toggleStage = (stageId: string) => {
    setManuallyToggledStages(prev => {
      const next = new Set(prev);
      if (next.has(stageId)) {
        next.delete(stageId);
      } else {
        next.add(stageId);
      }
      return next;
    });
  };

  const toggleError = (logId: string) => {
    setExpandedErrors(prev => {
      const next = new Set(prev);
      if (next.has(logId)) {
        next.delete(logId);
      } else {
        next.add(logId);
      }
      return next;
    });
  };

  const errorCount = logs.filter(l => l.level.toLowerCase() === "error").length;
  const warnCount = logs.filter(l => ["warn", "warning"].includes(l.level.toLowerCase())).length;

  if (logs.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
        <Terminal className="h-12 w-12 text-slate-600 mb-3" />
        <p className="text-slate-400 text-sm">No logs recorded yet</p>
        <p className="text-slate-500 text-xs mt-1">Logs will appear as the research progresses</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900/50 w-full overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-3 border-b border-slate-800 p-4 sm:p-5 bg-slate-900/80">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Title and stats */}
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800">
              <Terminal className="h-4 w-4 text-slate-300" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Research Logs</h2>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">{logs.length} total</span>
                {errorCount > 0 && <span className="text-red-400">• {errorCount} errors</span>}
                {warnCount > 0 && <span className="text-amber-400">• {warnCount} warnings</span>}
              </div>
            </div>
          </div>

          {/* View mode toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleViewModeChange("narrative")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "narrative"
                  ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              )}
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Narrative</span>
            </button>
            <button
              onClick={() => handleViewModeChange("detailed")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                viewMode === "detailed"
                  ? "bg-slate-600 text-white shadow-lg shadow-slate-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              )}
            >
              <List className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Detailed</span>
            </button>
          </div>
        </div>

        {/* Filters - only show in detailed mode */}
        {viewMode === "detailed" && (
          <div className="flex items-center gap-1" role="group" aria-label="Log level filter">
            {LOG_FILTER_OPTIONS.map(option => (
              <button
                key={option}
                type="button"
                onClick={() => setActiveFilter(option)}
                aria-pressed={activeFilter === option}
                className={cn(
                  "rounded-md px-3 py-1 text-xs font-medium transition-all",
                  activeFilter === option
                    ? LOG_FILTER_CONFIG[option].activeClass
                    : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                )}
              >
                {LOG_FILTER_CONFIG[option].label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {viewMode === "narrative" ? (
          <NarrativeView
            groupedLogs={groupedLogs}
            expandedStages={expandedStages}
            expandedErrors={expandedErrors}
            onToggleStage={toggleStage}
            onToggleError={toggleError}
          />
        ) : (
          <DetailedView
            logs={filteredLogs}
            expandedErrors={expandedErrors}
            onToggleError={toggleError}
          />
        )}
      </div>
    </div>
  );
}

// ===== Narrative View =====
function NarrativeView({
  groupedLogs,
  expandedStages,
  expandedErrors,
  onToggleStage,
  onToggleError,
}: {
  groupedLogs: GroupedLogs[];
  expandedStages: Set<string>;
  expandedErrors: Set<string>;
  onToggleStage: (id: string) => void;
  onToggleError: (id: string) => void;
}) {
  if (groupedLogs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-slate-500 text-sm">No logs match the current filter</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-800/50">
      {groupedLogs.map(group => {
        const isExpanded = expandedStages.has(group.stage.id);
        const hasIssues = group.errorCount > 0 || group.warnCount > 0;

        return (
          <div key={group.stage.id} className={cn(group.stage.bgColor)}>
            {/* Stage Header */}
            <button
              onClick={() => onToggleStage(group.stage.id)}
              className="w-full flex items-center gap-3 p-4 hover:bg-white/5 transition-colors text-left"
            >
              <div className={cn("transition-transform", isExpanded && "rotate-90")}>
                <ChevronRight className="h-4 w-4 text-slate-500" />
              </div>

              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg",
                  group.stage.bgColor,
                  "border",
                  group.stage.borderColor
                )}
              >
                <span className={group.stage.color}>{group.stage.icon}</span>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className={cn("font-medium text-sm", group.stage.color)}>
                    {group.stage.name}
                  </h3>
                  {hasIssues && (
                    <div className="flex items-center gap-1">
                      {group.errorCount > 0 && (
                        <span className="flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                          <XCircle className="h-3 w-3" />
                          {group.errorCount}
                        </span>
                      )}
                      {group.warnCount > 0 && (
                        <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
                          <AlertTriangle className="h-3 w-3" />
                          {group.warnCount}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {summarizeStage(group.logs)} • {group.logs.length} log
                  {group.logs.length !== 1 ? "s" : ""}
                </p>
              </div>
            </button>

            {/* Expanded Logs */}
            {isExpanded && (
              <div className="border-t border-slate-800/50 bg-slate-950/50">
                <div className="p-3 space-y-1">
                  {group.logs.map(log => (
                    <LogRow
                      key={log.id}
                      log={log}
                      isExpanded={expandedErrors.has(log.id)}
                      onToggle={() => onToggleError(log.id)}
                      compact
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ===== Detailed View =====
function DetailedView({
  logs,
  expandedErrors,
  onToggleError,
}: {
  logs: LogEntry[];
  expandedErrors: Set<string>;
  onToggleError: (id: string) => void;
}) {
  if (logs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-slate-500 text-sm">No logs match the current filter</p>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-0.5 font-mono text-xs">
      {logs.map(log => (
        <LogRow
          key={log.id}
          log={log}
          isExpanded={expandedErrors.has(log.id)}
          onToggle={() => onToggleError(log.id)}
        />
      ))}
    </div>
  );
}

// ===== Log Row Component =====
function LogRow({
  log,
  isExpanded,
  onToggle,
  compact = false,
}: {
  log: LogEntry;
  isExpanded: boolean;
  onToggle: () => void;
  compact?: boolean;
}) {
  const levelStyles = getLogLevelStyles(log.level);
  const isError = log.level.toLowerCase() === "error";
  const isWarning = ["warn", "warning"].includes(log.level.toLowerCase());
  const hasExpandableContent = isError && log.message.length > 100;

  return (
    <div
      className={cn(
        "rounded-md transition-colors",
        isError && "bg-red-500/5 border border-red-500/20",
        isWarning && "bg-amber-500/5 border border-amber-500/10",
        !isError && !isWarning && "hover:bg-slate-800/50"
      )}
    >
      <div
        className={cn("flex gap-2 py-1.5 px-2", hasExpandableContent && "cursor-pointer")}
        onClick={hasExpandableContent ? onToggle : undefined}
      >
        {/* Timestamp */}
        <span className="flex-shrink-0 text-slate-600 tabular-nums">
          {format(new Date(log.created_at), "HH:mm:ss")}
        </span>

        {/* Level indicator */}
        <span
          className={cn(
            "flex-shrink-0 w-14 flex items-center gap-1 uppercase font-medium",
            levelStyles.color
          )}
        >
          {levelStyles.icon}
          <span className="text-[10px]">{log.level}</span>
        </span>

        {/* Message */}
        <span
          className={cn(
            "flex-1 text-slate-300",
            compact && "truncate",
            isError && "text-red-300",
            isWarning && "text-amber-300"
          )}
        >
          {compact && !isExpanded
            ? log.message.length > 80
              ? `${log.message.slice(0, 80)}…`
              : log.message
            : log.message}
        </span>

        {/* Expand indicator for errors */}
        {hasExpandableContent && (
          <span className="flex-shrink-0 text-slate-600">
            {isExpanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </span>
        )}
      </div>

      {/* Expanded error details */}
      {isExpanded && hasExpandableContent && (
        <div className="px-2 pb-2 pt-1 border-t border-red-500/10">
          <pre className="text-xs text-red-300/80 whitespace-pre-wrap break-words font-mono bg-red-950/30 rounded p-2">
            {log.message}
          </pre>
        </div>
      )}
    </div>
  );
}
