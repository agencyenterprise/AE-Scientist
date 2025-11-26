"use client";

import React from "react";

type ConflictItem = { id: number; title: string; updated_at: string; url: string };

interface ConflictResolutionProps {
  conflicts: ConflictItem[];
  selectedConflictId: number | null;
  onSelectConflict: (id: number) => void;
  onGoToSelected: () => void;
  onUpdateSelected: () => void;
  onCreateNew: () => void;
  onCancel: () => void;
  onClose: () => void;
}

export function ConflictResolution({
  conflicts,
  selectedConflictId,
  onSelectConflict,
  onGoToSelected,
  onUpdateSelected,
  onCreateNew,
  onCancel,
  onClose,
}: ConflictResolutionProps) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">URL Already Imported</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1 rounded"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="mb-4">
        <p className="text-gray-600">
          This URL was already imported. Choose one or create a new chat.
        </p>
      </div>

      <div className="mb-4 border border-gray-200 rounded">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-3 py-2">Select</th>
              <th className="text-left px-3 py-2">Title</th>
              <th className="text-left px-3 py-2">Last updated</th>
              <th className="text-left px-3 py-2">Open</th>
            </tr>
          </thead>
          <tbody>
            {conflicts.map(item => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">
                  <input
                    type="radio"
                    name="conflictSelect"
                    checked={selectedConflictId === item.id}
                    onChange={() => onSelectConflict(item.id)}
                  />
                </td>
                <td className="px-3 py-2">{item.title || "Untitled"}</td>
                <td className="px-3 py-2">{new Date(item.updated_at).toLocaleString()}</td>
                <td className="px-3 py-2">
                  <a
                    className="text-[var(--primary)] hover:underline"
                    href={`/conversations/${item.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View
                  </a>
                </td>
              </tr>
            ))}
            {conflicts.length === 0 && (
              <tr>
                <td className="px-3 py-2" colSpan={4}>
                  No matches
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="space-y-3 mb-2">
        <button
          onClick={onGoToSelected}
          disabled={!selectedConflictId}
          className="w-full p-4 text-left border border-[var(--border)] rounded-lg hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] disabled:opacity-50"
        >
          <div className="font-medium text-gray-900">Go to selected conversation</div>
          <div className="text-sm text-gray-500">Open the conversation page in a new tab</div>
        </button>

        <button
          onClick={onUpdateSelected}
          disabled={!selectedConflictId}
          className="w-full p-4 text-left border border-[var(--border)] rounded-lg hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] disabled:opacity-50"
        >
          <div className="font-medium text-gray-900">Update selected conversation content</div>
          <div className="text-sm text-gray-500">Re-import to add any new messages</div>
        </button>

        <button
          onClick={onCreateNew}
          className="w-full p-4 text-left border border-[var(--border)] rounded-lg hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          <div className="font-medium text-gray-900">Create a new conversation for this URL</div>
          <div className="text-sm text-gray-500">Start fresh without changing existing ones</div>
        </button>

        <button
          onClick={onCancel}
          className="w-full p-4 text-left border border-[var(--border)] rounded-lg hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          <div className="font-medium text-gray-900">Cancel</div>
          <div className="text-sm text-gray-500">Go back and try a different URL</div>
        </button>
      </div>
    </div>
  );
}
