"use client";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";

interface BillingLayoutProps {
  children: React.ReactNode;
}

export default function BillingLayout({ children }: BillingLayoutProps) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
