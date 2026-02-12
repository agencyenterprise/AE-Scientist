"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  createCheckoutSession,
  DEFAULT_TRANSACTION_TYPES,
  fetchFundingOptions,
  fetchPublicConfig,
  fetchWallet,
  TRANSACTION_TYPES,
  type FundingOption,
  type TransactionType,
} from "@/features/billing/api";
import { ApiError } from "@/shared/lib/api-client";
import { useAuthContext } from "@/shared/contexts/AuthContext";
import {
  Wallet,
  Plus,
  Receipt,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ExternalLink,
  Loader2,
  Mail,
} from "lucide-react";

const PAGE_SIZE_OPTIONS = [25, 50, 100];
const DEFAULT_PAGE_SIZE = 25;

const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "james.bowler@ae.studio";

function buildRefundMailto(userEmail?: string): string {
  const body = `Hi,

I'd like to request a refund. Here are the details:

Account email: ${userEmail || "[your email]"}

Reason:

[Please describe why you're requesting a refund]

Thanks!`;
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("Refund Request - AE Scientist")}&body=${encodeURIComponent(body)}`;
}

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

function getSourceLink(
  metadata: Record<string, unknown> | undefined
): { label: string; href: string } | null {
  if (!metadata) return null;

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
    return { label: `Conversation #${conversationId}`, href: `/ideation-queue/${conversationId}` };
  }
  return null;
}

export default function BillingPage() {
  const { isAuthenticated, user } = useAuthContext();
  const refundMailto = buildRefundMailto(user?.email);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [showHolds, setShowHolds] = useState(false);

  // Determine which transaction types to fetch based on filter
  const transactionTypes: TransactionType[] = showHolds
    ? [...TRANSACTION_TYPES]
    : [...DEFAULT_TRANSACTION_TYPES];

  const walletQuery = useQuery({
    queryKey: ["billing", "wallet", currentPage, pageSize, showHolds],
    queryFn: () =>
      fetchWallet({
        limit: pageSize,
        offset: (currentPage - 1) * pageSize,
        transactionTypes,
      }),
    refetchInterval: 30_000,
    enabled: isAuthenticated,
    staleTime: 0, // Always fetch fresh data on mount
    placeholderData: keepPreviousData, // Keep previous data while fetching new data
  });

  const totalPages = walletQuery.data ? Math.ceil(walletQuery.data.total_count / pageSize) : 0;
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
    <div className="space-y-6">
      {/* Balance Card */}
      <section className="rounded-xl border border-border bg-gradient-to-br from-card to-card/80 p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 sm:h-12 sm:w-12">
              <Wallet className="h-5 w-5 text-primary sm:h-6 sm:w-6" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Current balance</p>
              <p className="text-2xl font-bold text-foreground sm:text-3xl">
                {walletQuery.isLoading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </span>
                ) : (
                  formatCurrency(walletQuery.data?.balance_cents, "usd")
                )}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 sm:gap-3">
            {requirements
              .filter(req => req.value > 0)
              .map(req => (
                <div
                  key={req.label}
                  className="flex-1 min-w-[120px] rounded-lg bg-muted/50 px-3 py-2 text-center sm:flex-none sm:text-left"
                >
                  <p className="text-xs text-muted-foreground">{req.label} requires</p>
                  <p className="text-sm font-semibold text-foreground">
                    {formatCurrency(req.value, "usd")}
                  </p>
                </div>
              ))}
          </div>
        </div>
        {error && (
          <div className="mt-4 rounded-lg bg-destructive/10 border border-destructive/30 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="mt-4 pt-4 border-t border-border/50">
          <a
            href={refundMailto}
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            <Mail className="h-4 w-4" />
            Need help? Request a refund
          </a>
        </div>
      </section>

      {/* Add Funds Section */}
      <section className="rounded-xl border border-border bg-card p-4 shadow-sm sm:p-6">
        <div className="flex items-center gap-2 mb-4">
          <Plus className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">Add funds</h2>
        </div>
        {fundingQuery.isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : fundingQuery.data && fundingQuery.data.options.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {fundingQuery.data.options.map(option => (
              <div
                key={option.price_id}
                className="group relative rounded-xl border border-border bg-background p-4 transition-all hover:border-primary/50 hover:shadow-md"
              >
                <p className="text-sm font-medium text-muted-foreground">
                  {option.nickname || "Funding option"}
                </p>
                <p className="mt-2 text-3xl font-bold text-foreground">
                  {formatCurrency(option.unit_amount, option.currency)}
                </p>
                <p className="mt-1 text-sm text-emerald-500">
                  +{formatCurrency(option.amount_cents, option.currency)} to balance
                </p>
                <button
                  type="button"
                  onClick={() => handlePurchase(option)}
                  disabled={activePrice === option.price_id}
                  className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {activePrice === option.price_id ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Redirecting…
                    </>
                  ) : (
                    "Add funds"
                  )}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No funding options are configured. Contact support for assistance.
          </p>
        )}
      </section>

      {/* Transactions Section */}
      <section className="rounded-xl border border-border bg-card p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <div className="flex items-center gap-2">
            <Receipt className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">Recent transactions</h2>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={showHolds}
              onChange={e => {
                setShowHolds(e.target.checked);
                setCurrentPage(1);
              }}
              className="h-4 w-4 rounded border-border accent-primary"
            />
            <span className="text-muted-foreground">Show holds</span>
          </label>
        </div>

        {walletQuery.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : walletQuery.data && walletQuery.data.transactions.length > 0 ? (
          <>
            {/* Desktop Table View */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="px-3 py-3 font-medium">Date</th>
                    <th className="px-3 py-3 font-medium">Type</th>
                    <th className="px-3 py-3 font-medium">Amount</th>
                    <th className="px-3 py-3 font-medium">Description</th>
                    <th className="px-3 py-3 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {walletQuery.data.transactions.map(tx => (
                    <tr key={tx.id} className="text-foreground hover:bg-muted/30 transition-colors">
                      <td className="px-3 py-3 whitespace-nowrap">
                        {new Date(tx.created_at).toLocaleString(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="px-3 py-3">
                        <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium capitalize">
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td
                        className={`px-3 py-3 font-semibold ${tx.amount_cents >= 0 ? "text-emerald-500" : "text-red-500"}`}
                      >
                        {tx.amount_cents >= 0 ? "+" : ""}
                        {formatCurrency(tx.amount_cents, "usd")}
                      </td>
                      <td className="px-3 py-3 text-muted-foreground max-w-[200px] truncate">
                        {tx.description ?? "—"}
                      </td>
                      <td className="px-3 py-3">
                        {(() => {
                          const source = getSourceLink(tx.metadata);
                          if (!source) return <span className="text-muted-foreground">—</span>;
                          return (
                            <Link
                              href={source.href}
                              className="inline-flex items-center gap-1 text-primary hover:underline"
                            >
                              {source.label}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Card View */}
            <div className="sm:hidden space-y-3">
              {walletQuery.data.transactions.map(tx => {
                const source = getSourceLink(tx.metadata);
                return (
                  <div key={tx.id} className="rounded-lg border border-border/50 bg-background p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium capitalize">
                          {tx.transaction_type}
                        </span>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {new Date(tx.created_at).toLocaleString(undefined, {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </p>
                      </div>
                      <p
                        className={`text-lg font-bold ${tx.amount_cents >= 0 ? "text-emerald-500" : "text-red-500"}`}
                      >
                        {tx.amount_cents >= 0 ? "+" : ""}
                        {formatCurrency(tx.amount_cents, "usd")}
                      </p>
                    </div>
                    {tx.description && (
                      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                        {tx.description}
                      </p>
                    )}
                    {source && (
                      <Link
                        href={source.href}
                        className="mt-2 inline-flex items-center gap-1 text-sm text-primary hover:underline"
                      >
                        {source.label}
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Pagination controls */}
            <div className="mt-4 flex flex-col gap-3 border-t border-border/50 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground sm:justify-start">
                <span className="hidden sm:inline">Rows:</span>
                <select
                  value={pageSize}
                  onChange={e => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground"
                >
                  {PAGE_SIZE_OPTIONS.map(size => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
                <span className="text-xs sm:text-sm">
                  {(currentPage - 1) * pageSize + 1}–
                  {Math.min(currentPage * pageSize, walletQuery.data.total_count)} of{" "}
                  {walletQuery.data.total_count}
                </span>
              </div>

              <div className="flex items-center justify-center gap-1">
                <button
                  type="button"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                  className="rounded-md border border-border p-2 text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  aria-label="First page"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="rounded-md border border-border p-2 text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="px-3 py-1 text-sm text-muted-foreground min-w-[100px] text-center">
                  {currentPage} / {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="rounded-md border border-border p-2 text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage >= totalPages}
                  className="rounded-md border border-border p-2 text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  aria-label="Last page"
                >
                  <ChevronsRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="py-12 text-center">
            <Receipt className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <p className="mt-3 text-sm text-muted-foreground">
              No transactions recorded for your account yet.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
