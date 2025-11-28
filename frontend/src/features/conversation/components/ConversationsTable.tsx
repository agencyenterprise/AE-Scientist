"use client";

import { useMemo } from "react";

import type { Conversation } from "@/shared/lib/api-adapters";

interface ConversationsTableProps {
  conversations: Conversation[];
  onSelect: (conversation: Conversation) => void;
}

export function ConversationsTable({ conversations, onSelect }: ConversationsTableProps) {
  const rows = useMemo(() => {
    return conversations.map(c => ({
      id: c.id,
      conversation: c,
      title: c.title || "Untitled",
      user: c.userName || c.userEmail,
      imported: new Date(c.importDate).toLocaleString(),
      updated: new Date(c.updatedAt).toLocaleString(),
      hasImages: false,
      hasPdfs: false,
    }));
  }, [conversations]);

  const handleRowClick = (conversation: Conversation) => {
    onSelect(conversation);
  };

  if (rows.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-medium text-gray-900 mb-2">No conversations yet</h2>
          <p className="text-gray-600">
            Click the &quot;Import Chat&quot; button in the sidebar to add one.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Title
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Imported
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Updated
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Flags
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {rows.map(row => (
                <tr
                  key={row.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => handleRowClick(row.conversation)}
                >
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-gray-900">{row.title}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">{row.user}</td>
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {row.imported}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {row.updated}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center space-x-2">
                      {row.hasImages ? (
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                          Images
                        </span>
                      ) : null}
                      {row.hasPdfs ? (
                        <span className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700">
                          PDFs
                        </span>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
