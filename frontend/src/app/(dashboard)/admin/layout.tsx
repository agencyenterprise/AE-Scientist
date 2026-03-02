"use client";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
