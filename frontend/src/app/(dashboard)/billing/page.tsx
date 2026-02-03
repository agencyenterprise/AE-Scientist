"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createCheckoutSession,
  fetchFundingOptions,
  fetchPublicConfig,
  fetchWallet,
  type FundingOption,
} from "@/features/billing/api";
import { ApiError } from "@/shared/lib/api-client";
import { useAuthContext } from "@/shared/contexts/AuthContext";

function formatCurrency(amountCents?: number | null, currency?: string | null): string {
  if (amountCents === undefined || amountCents === null) {
    return "—";
  }
  const formatter = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "usd",
  });
  return formatter.format(amountCents / 100);
}

function getSourceLink(metadata: Record<string, unknown>): { label: string; href: string } | null {
  const runId = metadata.run_id as string | undefined;
  const conversationId = metadata.conversation_id as number | undefined;
  const paperReviewId = metadata.paper_review_id as number | undefined;

  if (runId) {
    return { label: runId, href: `/research/${runId}` };
  }
  if (paperReviewId) {
    return { label: `Review #${paperReviewId}`, href: `/paper-review/${paperReviewId}` };
  }
  if (conversationId) {
    return { label: `Conversation #${conversationId}`, href: `/conversations/${conversationId}` };
  }
  return null;
}

export default function BillingPage() {
  const { isAuthenticated } = useAuthContext();

  const walletQuery = useQuery({
    queryKey: ["billing", "wallet"],
    queryFn: fetchWallet,
    refetchInterval: 30_000,
    enabled: isAuthenticated,
    staleTime: 0, // Always fetch fresh data on mount
  });
  const fundingQuery = useQuery({
    queryKey: ["billing", "funding-options"],
    queryFn: fetchFundingOptions,
    enabled: isAuthenticated,
  });
  const configQuery = useQuery({
    queryKey: ["public-config"],
    queryFn: fetchPublicConfig,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
  const [error, setError] = useState<string | null>(null);
  const [activePrice, setActivePrice] = useState<string | null>(null);

  const requirements = useMemo(
    () => [
      {
        label: "Idea refinement",
        value: configQuery.data?.min_balance_cents_for_conversation ?? 0,
      },
      { label: "Paper review", value: configQuery.data?.min_balance_cents_for_paper_review ?? 0 },
      {
        label: "Research pipeline",
        value: configQuery.data?.min_balance_cents_for_research_pipeline ?? 0,
      },
    ],
    [configQuery.data]
  );

  const handlePurchase = async (option: FundingOption) => {
    if (!option.price_id) return;
    setError(null);
    setActivePrice(option.price_id);
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : "";
      const { checkout_url } = await createCheckoutSession({
        price_id: option.price_id,
        success_url: `${origin}/billing?success=1`,
        cancel_url: `${origin}/billing?canceled=1`,
      });
      window.location.href = checkout_url;
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.data && typeof err.data === "string"
            ? err.data
            : err.message
          : "Failed to start checkout. Please try again.";
      setError(message);
    } finally {
      setActivePrice(null);
    }
  };

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current balance</p>
            <p className="text-3xl font-semibold text-foreground">
              {!walletQuery.data || walletQuery.isFetching
                ? "…"
                : formatCurrency(walletQuery.data.balance_cents, "usd")}
            </p>
          </div>
          <div className="flex gap-4">
            {requirements
              .filter(req => req.value > 0)
              .map(req => (
                <div key={req.label} className="rounded-md bg-muted px-4 py-2 text-sm">
                  <p className="text-muted-foreground">{req.label} needs</p>
                  <p className="font-medium text-foreground">{formatCurrency(req.value, "usd")}</p>
                </div>
              ))}
          </div>
        </div>
        {error && (
          <p className="mt-4 rounded-md bg-[color-mix(in_srgb,var(--danger),transparent_85%)] px-4 py-2 text-sm text-[var(--danger)]">
            {error}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Add funds</h2>
        {fundingQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading options…</p>
        ) : fundingQuery.data && fundingQuery.data.options.length > 0 ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {fundingQuery.data.options.map(option => (
              <div
                key={option.price_id}
                className="rounded-lg border border-border bg-background p-4 shadow-sm"
              >
                <p className="text-sm text-muted-foreground">
                  {option.nickname || "Funding option"}
                </p>
                <p className="mt-1 text-2xl font-semibold text-foreground">
                  {formatCurrency(option.unit_amount, option.currency)}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Adds {formatCurrency(option.amount_cents, option.currency)} to balance
                </p>
                <button
                  type="button"
                  onClick={() => handlePurchase(option)}
                  disabled={activePrice === option.price_id}
                  className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {activePrice === option.price_id ? "Redirecting…" : "Add funds"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">
            No funding options are configured. Contact support for assistance.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Recent transactions</h2>
        {!walletQuery.data || walletQuery.isFetching ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading transactions…</p>
        ) : walletQuery.data.transactions.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="px-2 py-1 font-medium">Date</th>
                  <th className="px-2 py-1 font-medium">Type</th>
                  <th className="px-2 py-1 font-medium">Amount</th>
                  <th className="px-2 py-1 font-medium">Description</th>
                  <th className="px-2 py-1 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {walletQuery.data.transactions.map(tx => (
                  <tr key={tx.id} className="border-t border-border/50 text-foreground">
                    <td className="px-2 py-2">
                      {new Date(tx.created_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </td>
                    <td className="px-2 py-2 capitalize">{tx.transaction_type}</td>
                    <td
                      className={`px-2 py-2 font-medium ${tx.amount_cents >= 0 ? "text-emerald-500" : "text-red-500"}`}
                    >
                      {tx.amount_cents >= 0 ? "+" : ""}
                      {formatCurrency(tx.amount_cents, "usd")}
                    </td>
                    <td className="px-2 py-2 text-muted-foreground">{tx.description ?? "—"}</td>
                    <td className="px-2 py-2">
                      {(() => {
                        const source = getSourceLink(tx.metadata);
                        if (!source) return <span className="text-muted-foreground">—</span>;
                        return (
                          <Link href={source.href} className="text-primary hover:underline">
                            {source.label}
                          </Link>
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">
            No transactions recorded for your account yet.
          </p>
        )}
      </section>
    </div>
  );
}
