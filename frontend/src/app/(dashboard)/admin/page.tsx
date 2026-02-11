"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAuthContext } from "@/shared/contexts/AuthContext";
import {
  addCreditToUser,
  createPendingCredit,
  fetchPendingCredits,
  fetchUsersWithBalances,
  type UserWithBalance,
} from "@/features/admin/api";

function formatCurrency(amountCents: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "usd",
  }).format(amountCents / 100);
}

export default function AdminPage() {
  const { isAuthenticated, user, isLoading: authLoading } = useAuthContext();
  const router = useRouter();
  const queryClient = useQueryClient();

  // State for UI
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedUser, setSelectedUser] = useState<UserWithBalance | null>(null);
  const [creditAmount, setCreditAmount] = useState("");
  const [creditDescription, setCreditDescription] = useState("");
  const [pendingEmail, setPendingEmail] = useState("");
  const [pendingAmount, setPendingAmount] = useState("");
  const [pendingDescription, setPendingDescription] = useState("");
  const [activeTab, setActiveTab] = useState<"users" | "pending">("users");
  const [includeClaimed, setIncludeClaimed] = useState(false);

  const isAdmin = isAuthenticated && user?.is_admin;

  // Fetch users with balances
  const usersQuery = useQuery({
    queryKey: ["admin", "users", searchTerm],
    queryFn: () => fetchUsersWithBalances({ search: searchTerm || undefined }),
    enabled: isAdmin,
  });

  // Fetch pending credits
  const pendingQuery = useQuery({
    queryKey: ["admin", "pending-credits", includeClaimed],
    queryFn: () => fetchPendingCredits({ include_claimed: includeClaimed }),
    enabled: isAdmin && activeTab === "pending",
  });

  // Mutations
  const addCreditMutation = useMutation({
    mutationFn: addCreditToUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setSelectedUser(null);
      setCreditAmount("");
      setCreditDescription("");
    },
  });

  const createPendingMutation = useMutation({
    mutationFn: createPendingCredit,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "pending-credits"] });
      setPendingEmail("");
      setPendingAmount("");
      setPendingDescription("");
    },
  });

  // Redirect non-admin users
  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push("/");
    }
  }, [authLoading, isAdmin, router]);

  const handleAddCredit = () => {
    if (!selectedUser || !creditAmount || !creditDescription) return;
    const amountCents = Math.round(parseFloat(creditAmount) * 100);
    if (isNaN(amountCents) || amountCents <= 0) return;

    addCreditMutation.mutate({
      user_id: selectedUser.id,
      amount_cents: amountCents,
      description: creditDescription,
    });
  };

  const handleCreatePending = () => {
    if (!pendingEmail || !pendingAmount) return;
    const amountCents = Math.round(parseFloat(pendingAmount) * 100);
    if (isNaN(amountCents) || amountCents <= 0) return;

    createPendingMutation.mutate({
      email: pendingEmail,
      amount_cents: amountCents,
      description: pendingDescription || undefined,
    });
  };

  if (authLoading || !isAdmin) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-foreground">Admin - Credit Management</h1>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => setActiveTab("users")}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === "users"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Users & Balances
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("pending")}
          className={`px-4 py-2 text-sm font-medium ${
            activeTab === "pending"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Pending Credits
        </button>
      </div>

      {activeTab === "users" && (
        <div className="space-y-6">
          {/* Search */}
          <div className="flex gap-4">
            <input
              type="text"
              placeholder="Search by email or name..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="flex-1 rounded-md border border-border bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground"
            />
          </div>

          {/* Add Credit Form */}
          {selectedUser && (
            <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-foreground">
                Add Credit to {selectedUser.name} ({selectedUser.email})
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Current balance: {formatCurrency(selectedUser.balance_cents)}
              </p>
              <div className="mt-4 flex flex-col gap-4 md:flex-row">
                <input
                  type="number"
                  placeholder="Amount ($)"
                  value={creditAmount}
                  onChange={e => setCreditAmount(e.target.value)}
                  min="0.01"
                  step="0.01"
                  className="w-32 rounded-md border border-border bg-background px-4 py-2 text-foreground"
                />
                <input
                  type="text"
                  placeholder="Description (required)"
                  value={creditDescription}
                  onChange={e => setCreditDescription(e.target.value)}
                  className="flex-1 rounded-md border border-border bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground"
                />
                <button
                  type="button"
                  onClick={handleAddCredit}
                  disabled={addCreditMutation.isPending || !creditAmount || !creditDescription}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {addCreditMutation.isPending ? "Adding..." : "Add Credit"}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedUser(null)}
                  className="rounded-md border border-border px-4 py-2 text-sm text-foreground hover:bg-muted"
                >
                  Cancel
                </button>
              </div>
              {addCreditMutation.isError && (
                <p className="mt-2 text-sm text-red-500">Failed to add credit. Please try again.</p>
              )}
              {addCreditMutation.isSuccess && (
                <p className="mt-2 text-sm text-emerald-500">Credit added successfully!</p>
              )}
            </section>
          )}

          {/* Users Table */}
          <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">Active Users</h2>
            {usersQuery.isLoading ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading users...</p>
            ) : usersQuery.data?.users.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="px-2 py-1 font-medium">Name</th>
                      <th className="px-2 py-1 font-medium">Email</th>
                      <th className="px-2 py-1 font-medium">Balance</th>
                      <th className="px-2 py-1 font-medium">Registered</th>
                      <th className="px-2 py-1 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usersQuery.data.users.map(u => (
                      <tr key={u.id} className="border-t border-border/50 text-foreground">
                        <td className="px-2 py-2">{u.name}</td>
                        <td className="px-2 py-2">{u.email}</td>
                        <td className="px-2 py-2 font-medium">{formatCurrency(u.balance_cents)}</td>
                        <td className="px-2 py-2 text-muted-foreground">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-2 py-2">
                          <button
                            type="button"
                            onClick={() => setSelectedUser(u)}
                            className="text-primary hover:underline"
                          >
                            Add Credit
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">No users found.</p>
            )}
            {usersQuery.data && (
              <p className="mt-4 text-sm text-muted-foreground">
                Total: {usersQuery.data.total_count} users
              </p>
            )}
          </section>
        </div>
      )}

      {activeTab === "pending" && (
        <div className="space-y-6">
          {/* Create Pending Credit Form */}
          <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">
              Add Credit for Unregistered Email
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              The credit will be automatically applied when the user registers with this email.
            </p>
            <div className="mt-4 flex flex-col gap-4 md:flex-row">
              <input
                type="email"
                placeholder="Email address"
                value={pendingEmail}
                onChange={e => setPendingEmail(e.target.value)}
                className="w-64 rounded-md border border-border bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground"
              />
              <input
                type="number"
                placeholder="Amount ($)"
                value={pendingAmount}
                onChange={e => setPendingAmount(e.target.value)}
                min="0.01"
                step="0.01"
                className="w-32 rounded-md border border-border bg-background px-4 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="Description (optional)"
                value={pendingDescription}
                onChange={e => setPendingDescription(e.target.value)}
                className="flex-1 rounded-md border border-border bg-background px-4 py-2 text-foreground placeholder:text-muted-foreground"
              />
              <button
                type="button"
                onClick={handleCreatePending}
                disabled={createPendingMutation.isPending || !pendingEmail || !pendingAmount}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {createPendingMutation.isPending ? "Creating..." : "Create Pending Credit"}
              </button>
            </div>
            {createPendingMutation.isError && (
              <p className="mt-2 text-sm text-red-500">
                Failed to create pending credit. The email may already be registered.
              </p>
            )}
            {createPendingMutation.isSuccess && (
              <p className="mt-2 text-sm text-emerald-500">Pending credit created successfully!</p>
            )}
          </section>

          {/* Pending Credits Table */}
          <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Pending Credits</h2>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={includeClaimed}
                  onChange={e => setIncludeClaimed(e.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                Show claimed
              </label>
            </div>
            {pendingQuery.isLoading ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading pending credits...</p>
            ) : pendingQuery.data?.pending_credits.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="px-2 py-1 font-medium">Email</th>
                      <th className="px-2 py-1 font-medium">Amount</th>
                      <th className="px-2 py-1 font-medium">Description</th>
                      <th className="px-2 py-1 font-medium">Created By</th>
                      <th className="px-2 py-1 font-medium">Created</th>
                      <th className="px-2 py-1 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingQuery.data.pending_credits.map(pc => (
                      <tr key={pc.id} className="border-t border-border/50 text-foreground">
                        <td className="px-2 py-2">{pc.email}</td>
                        <td className="px-2 py-2 font-medium">{formatCurrency(pc.amount_cents)}</td>
                        <td className="px-2 py-2 text-muted-foreground">{pc.description || "—"}</td>
                        <td className="px-2 py-2 text-muted-foreground">{pc.granted_by_email}</td>
                        <td className="px-2 py-2 text-muted-foreground">
                          {new Date(pc.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-2 py-2">
                          {pc.claimed_at ? (
                            <span className="text-emerald-500">Claimed</span>
                          ) : (
                            <span className="text-amber-500">Pending</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">No pending credits found.</p>
            )}
            {pendingQuery.data && (
              <p className="mt-4 text-sm text-muted-foreground">
                Total: {pendingQuery.data.total_count} pending credits
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
