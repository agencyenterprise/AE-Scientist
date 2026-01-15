"use client";

import { useResource } from "@/features/research/systems/narrative";

export function NarrativeSystemBoundary() {
  const { useCleanup } = useResource("cleanup");
  useCleanup();
  return null;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NarrativeSystemBoundary />
      {children}
    </>
  );
}
