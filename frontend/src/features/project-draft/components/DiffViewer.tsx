"use client";

import { useMemo } from "react";
import { diff_match_patch } from "diff-match-patch";

interface DiffViewerProps {
  original: string;
  modified: string;
  title: string;
}

export function DiffViewer({ original, modified, title }: DiffViewerProps) {
  const diffs = useMemo(() => {
    const dmp = new diff_match_patch();
    const diffs = dmp.diff_main(original, modified);
    dmp.diff_cleanupSemantic(diffs);
    return diffs;
  }, [original, modified]);

  const renderDiff = () => {
    return diffs.map((diff, index) => {
      const [operation, text] = diff;
      const lines = text.split("\n");

      return lines.map((line, lineIndex) => {
        const key = `${index}-${lineIndex}`;
        const isLastLine = lineIndex === lines.length - 1;

        if (operation === 0) {
          // No change
          return (
            <span key={key} className="text-gray-700">
              {line}
              {!isLastLine && <br />}
            </span>
          );
        } else if (operation === -1) {
          // Deletion
          return (
            <span key={key} className="bg-red-100 text-red-800 px-1 rounded">
              <span className="line-through">{line}</span>
              {!isLastLine && <br />}
            </span>
          );
        } else {
          // Addition
          return (
            <span key={key} className="bg-green-100 text-green-800 px-1 rounded">
              <span className="font-medium">{line}</span>
              {!isLastLine && <br />}
            </span>
          );
        }
      });
    });
  };

  const hasChanges = diffs.some(diff => diff[0] !== 0);

  return (
    <div className="space-y-2">
      {title && <h4 className="text-sm font-medium text-gray-700">{title}</h4>}
      <div className="bg-gray-50 rounded-lg border" style={{ height: "400px" }}>
        <div
          className="h-full p-3 text-sm leading-relaxed overflow-y-scroll"
          style={{
            scrollbarWidth: "auto",
            scrollbarColor: "#6b7280 #e5e7eb",
            scrollbarGutter: "stable",
          }}
        >
          <div className="whitespace-pre-wrap break-words">{renderDiff()}</div>
        </div>
      </div>
      {hasChanges && (
        <div className="text-xs text-gray-500">
          <span className="inline-flex items-center">
            <span className="w-3 h-3 bg-red-100 border border-red-200 rounded mr-2"></span>
            Removed
          </span>
          <span className="inline-flex items-center ml-4">
            <span className="w-3 h-3 bg-green-100 border border-green-200 rounded mr-2"></span>
            Added
          </span>
        </div>
      )}
    </div>
  );
}
