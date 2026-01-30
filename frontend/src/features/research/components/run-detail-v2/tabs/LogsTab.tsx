"use client";

import { ResearchLogsList } from "../../../components/run-detail/research-logs-list";
import type { LogEntry } from "@/types/research";

interface LogsTabProps {
  logs: LogEntry[];
}

export function LogsTab({ logs }: LogsTabProps) {
  return <ResearchLogsList logs={logs} />;
}
