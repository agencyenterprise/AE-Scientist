"use client";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";

interface PaperReviewLayoutProps {
  children: React.ReactNode;
}

export default function PaperReviewLayout({ children }: PaperReviewLayoutProps) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
