"use client";

import { useState, useMemo } from "react";
import { Terminal } from "lucide-react";
import { format } from "date-fns";
import type { LogEntry } from "@/types/research";
import { getLogLevelColor } from "../../utils/research-utils";
import { cn } from "@/shared/lib/utils";

// ===== Filter Types and Configuration =====
type LogLevelFilter = "all" | "info" | "warn" | "error";

const LOG_FILTER_CONFIG: Record<LogLevelFilter, { label: string; activeClass: string }> = {
  all: { label: "all", activeClass: "bg-slate-500/15 text-slate-300" },
  info: { label: "info", activeClass: "bg-sky-500/15 text-sky-400" },
  warn: { label: "warn", activeClass: "bg-amber-500/15 text-amber-400" },
  error: { label: "error", activeClass: "bg-red-500/15 text-red-400" },
};

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];

interface ResearchLogsListProps {
  logs: LogEntry[];
}

/**
 * Logs section for research run detail page
 * Supports filtering by log level (all, info, warn, error)
 */
export function ResearchLogsList({ logs }: ResearchLogsListProps) {
  const [activeFilter, setActiveFilter] = useState<LogLevelFilter>("all");

  // Memoize filtered logs - logs array can grow large during research runs
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

  if (logs.length === 0) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-900/50 p-6 w-full">
      {/* Header with Filter Buttons */}
      <div className="mb-4 flex items-center justify-between">
        {/* Left side: Icon, Title, Count */}
        <div className="flex items-center gap-2">
          <Terminal className="h-5 w-5 text-slate-400" />
          <h2 className="text-lg font-semibold text-white">Logs</h2>
          <span className="text-sm text-slate-400">
            ({filteredLogs.length}
            {activeFilter !== "all" ? `/${logs.length}` : ""})
          </span>
        </div>

        {/* Right side: Filter Buttons */}
        <div className="flex items-center gap-1" role="group" aria-label="Log level filter">
          {LOG_FILTER_OPTIONS.map(option => (
            <button
              key={option}
              type="button"
              onClick={() => setActiveFilter(option)}
              aria-pressed={activeFilter === option}
              className={cn(
                "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                activeFilter === option
                  ? LOG_FILTER_CONFIG[option].activeClass
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
              )}
            >
              {LOG_FILTER_CONFIG[option].label}
            </button>
          ))}
        </div>
      </div>

      {/* Log List */}
      <div className="min-h-0 flex-1 overflow-y-auto rounded-lg bg-slate-950 p-4 font-mono text-sm">
        {filteredLogs.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <span className="text-slate-400">
              {activeFilter === "all" ? "No logs yet" : `No ${activeFilter}-level logs`}
            </span>
          </div>
        ) : (
          filteredLogs.map(log => (
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
          ))
        )}
      </div>
    </div>
  );
}
