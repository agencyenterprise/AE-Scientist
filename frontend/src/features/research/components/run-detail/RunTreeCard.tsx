"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { RunTreeNode, RunTreeResponse } from "@/types/research";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, GitBranch, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

interface RunTreeCardProps {
  runId: string;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />;
    case "running":
    case "initializing":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-400 flex-shrink-0" />;
    default:
      return <Circle className="h-4 w-4 text-slate-500 flex-shrink-0" />;
  }
}

interface TreeLevel {
  node: RunTreeNode;
  children: TreeLevel[];
}

interface FlatTreeNode {
  node: RunTreeNode;
  depth: number;
  isLast: boolean;
  // For each ancestor level, true if that ancestor was NOT the last sibling (needs │)
  connectors: boolean[];
}

function buildTree(nodes: RunTreeNode[]): TreeLevel[] {
  const nodeMap = new Map<string, RunTreeNode>();
  nodes.forEach(node => nodeMap.set(node.run_id, node));

  const childrenMap = new Map<string | null, RunTreeNode[]>();
  nodes.forEach(node => {
    const parentId = node.parent_run_id;
    if (!childrenMap.has(parentId)) {
      childrenMap.set(parentId, []);
    }
    childrenMap.get(parentId)!.push(node);
  });

  // Find root nodes (nodes with no parent or whose parent is not in our set)
  const rootNodes = nodes.filter(node => !node.parent_run_id || !nodeMap.has(node.parent_run_id));

  function buildLevel(node: RunTreeNode): TreeLevel {
    const children = childrenMap.get(node.run_id) || [];
    return {
      node,
      children: children.map(child => buildLevel(child)),
    };
  }

  return rootNodes.map(root => buildLevel(root));
}

function flattenTree(
  levels: TreeLevel[],
  depth: number = 0,
  connectors: boolean[] = [],
  result: FlatTreeNode[] = []
): FlatTreeNode[] {
  levels.forEach((level, index) => {
    const isLast = index === levels.length - 1;
    result.push({
      node: level.node,
      depth,
      isLast,
      connectors: [...connectors],
    });
    if (level.children.length > 0) {
      // Pass down whether THIS node is not the last (so children know to draw │)
      flattenTree(level.children, depth + 1, [...connectors, !isLast], result);
    }
  });
  return result;
}

interface TreeNodeDisplayProps {
  item: FlatTreeNode;
}

function TreeNodeDisplay({ item }: TreeNodeDisplayProps) {
  const { node, depth, isLast, connectors } = item;

  // Build the prefix string for tree visualization
  // For depth 0 (root), no prefix
  // For depth > 0, show connectors for each ancestor level, then the branch symbol
  const renderPrefix = () => {
    if (depth === 0) return null;

    const parts: React.ReactNode[] = [];

    // Add continuation lines for ancestor levels
    for (let i = 0; i < connectors.length; i++) {
      parts.push(
        <span key={`c-${i}`} className="inline-block w-4 text-center text-slate-600">
          {connectors[i] ? "│" : "\u00A0"}
        </span>
      );
    }

    // Add the branch symbol for this node
    parts.push(
      <span key="branch" className="inline-block w-4 text-center text-slate-600">
        {isLast ? "└" : "├"}
      </span>
    );
    parts.push(
      <span key="dash" className="inline-block w-3 text-slate-600">
        ──
      </span>
    );

    return <span className="font-mono flex-shrink-0">{parts}</span>;
  };

  return (
    <div className="flex items-center gap-1 py-1 whitespace-nowrap">
      {renderPrefix()}
      <StatusIcon status={node.status} />
      <Link
        href={`/research/${node.run_id}`}
        className={`text-sm hover:underline overflow-hidden text-ellipsis ${
          node.is_current
            ? "text-emerald-400 font-semibold"
            : "text-slate-300 hover:text-emerald-300"
        }`}
        style={{ maxWidth: "250px" }}
        title={node.idea_title}
      >
        {node.idea_title || "Untitled"}
      </Link>
      {node.is_current && (
        <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded flex-shrink-0">
          Current
        </span>
      )}
    </div>
  );
}

export function RunTreeCard({ runId }: RunTreeCardProps) {
  const { data, isLoading, error } = useQuery<RunTreeResponse>({
    queryKey: ["runTree", runId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/research-runs/{run_id}/tree", {
        params: { path: { run_id: runId } },
      });
      if (error) throw new Error("Failed to load run tree");
      return data as RunTreeResponse;
    },
    enabled: !!runId,
    staleTime: 60 * 1000,
  });

  const treeData = useMemo(() => {
    if (!data?.nodes || data.nodes.length <= 1) return null;
    const tree = buildTree(data.nodes);
    return flattenTree(tree);
  }, [data]);

  // Don't show if there's only one node (no ancestors or descendants)
  if (!isLoading && (!data?.nodes || data.nodes.length <= 1)) {
    return null;
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <div className="mb-4 flex items-center gap-2">
        <GitBranch className="h-5 w-5 text-slate-400" />
        <h2 className="text-lg font-semibold text-white">Run Lineage</h2>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : error ? (
        <p className="text-sm text-center text-slate-400">Could not load run tree.</p>
      ) : treeData ? (
        <div>
          <p className="text-xs text-slate-500 mb-3">Showing all runs in this research lineage</p>
          <div className="overflow-x-auto">
            {treeData.map(item => (
              <TreeNodeDisplay key={item.node.run_id} item={item} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
