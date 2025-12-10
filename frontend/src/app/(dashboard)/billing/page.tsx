"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createCheckoutSession,
  fetchCreditPacks,
  fetchWallet,
  type CreditPack,
} from "@/features/billing/api";
import { ApiError } from "@/shared/lib/api-client";
import { config } from "@/shared/lib/config";

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

export default function BillingPage() {
  const walletQuery = useQuery({
    queryKey: ["billing", "wallet"],
    queryFn: fetchWallet,
    refetchInterval: 30_000,
  });
  const packsQuery = useQuery({
    queryKey: ["billing", "packs"],
    queryFn: fetchCreditPacks,
  });
  const [error, setError] = useState<string | null>(null);
  const [activePrice, setActivePrice] = useState<string | null>(null);

  const requirements = useMemo(
    () => [
      { label: "Idea refinement", value: config.minCredits.conversation },
      { label: "Research pipeline", value: config.minCredits.researchPipeline },
    ],
    []
  );

  const handlePurchase = async (pack: CreditPack) => {
    if (!pack.price_id) return;
    setError(null);
    setActivePrice(pack.price_id);
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : config.apiBaseUrl;
      const { checkout_url } = await createCheckoutSession({
        price_id: pack.price_id,
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
              {walletQuery.isLoading ? "…" : (walletQuery.data?.balance ?? 0)} credits
            </p>
          </div>
          <div className="flex gap-4">
            {requirements
              .filter(req => req.value > 0)
              .map(req => (
                <div key={req.label} className="rounded-md bg-muted px-4 py-2 text-sm">
                  <p className="text-muted-foreground">{req.label} needs</p>
                  <p className="font-medium text-foreground">{req.value} credits</p>
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
        <h2 className="text-lg font-semibold text-foreground">Purchase credits</h2>
        {packsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading packs…</p>
        ) : packsQuery.data && packsQuery.data.packs.length > 0 ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {packsQuery.data.packs.map(pack => (
              <div
                key={pack.price_id}
                className="rounded-lg border border-border bg-background p-4 shadow-sm"
              >
                <p className="text-sm text-muted-foreground">{pack.nickname || "Credit pack"}</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">
                  {formatCurrency(pack.unit_amount, pack.currency)}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">{pack.credits} credits</p>
                <button
                  type="button"
                  onClick={() => handlePurchase(pack)}
                  disabled={activePrice === pack.price_id}
                  className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {activePrice === pack.price_id ? "Redirecting…" : "Buy credits"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">
            No credit packs are configured. Contact support for assistance.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">Recent transactions</h2>
        {walletQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading transactions…</p>
        ) : walletQuery.data && walletQuery.data.transactions.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="px-2 py-1 font-medium">Date</th>
                  <th className="px-2 py-1 font-medium">Type</th>
                  <th className="px-2 py-1 font-medium">Amount</th>
                  <th className="px-2 py-1 font-medium">Description</th>
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
                    <td className="px-2 py-2 font-medium">
                      {tx.amount >= 0 ? `+${tx.amount}` : tx.amount} credits
                    </td>
                    <td className="px-2 py-2 text-muted-foreground">{tx.description ?? "—"}</td>
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
