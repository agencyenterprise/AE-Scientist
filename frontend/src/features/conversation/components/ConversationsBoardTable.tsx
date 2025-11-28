"use client";

import { useMemo } from "react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Eye } from "lucide-react";
import type { Conversation } from "@/shared/lib/api-adapters";

interface ConversationsBoardTableProps {
  conversations: Conversation[];
}

function truncateId(id: number | string): string {
  const idStr = String(id);
  if (idStr.length <= 8) return idStr;
  return `${idStr.slice(0, 8)}...`;
}

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function ConversationsBoardTable({ conversations }: ConversationsBoardTableProps) {
  const rows = useMemo(() => {
    return conversations.map(c => ({
      id: c.id,
      displayId: truncateId(c.id),
      title: c.title || c.ideaTitle || "Untitled",
      user: c.userName || c.userEmail || "Unknown",
      imported: formatRelativeTime(c.importDate),
      updated: formatRelativeTime(c.updatedAt),
    }));
  }, [conversations]);

  if (rows.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-slate-300">No conversations found</h3>
          <p className="mt-1 text-sm text-slate-500">Import a conversation to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-800">
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
              ID
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
              Title
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
              User
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
              Imported
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
              Updated
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50">
          {rows.map(row => (
            <tr key={row.id} className="transition-colors hover:bg-slate-900/50">
              <td className="whitespace-nowrap px-6 py-4 font-mono text-sm text-slate-500">
                {row.displayId}
              </td>
              <td className="max-w-xs truncate px-6 py-4 text-sm font-medium text-white">
                {row.title}
              </td>
              <td className="whitespace-nowrap px-6 py-4 text-sm text-slate-300">{row.user}</td>
              <td className="whitespace-nowrap px-6 py-4 text-sm text-slate-400">{row.imported}</td>
              <td className="whitespace-nowrap px-6 py-4 text-sm text-slate-400">{row.updated}</td>
              <td className="whitespace-nowrap px-6 py-4 text-right">
                <Link
                  href={`/conversations/${row.id}`}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-sky-400 transition-colors hover:text-sky-300"
                >
                  <Eye className="h-4 w-4" />
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
