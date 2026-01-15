"use client";

import NarrativeResearchPage from "@/features/narrator/components/NarrativeResearchPage";
import { useParams } from "next/navigation";

export default function NarrativePage() {
  const params = useParams();
  const runId = params?.runId as string;
  if (!runId) {
    // Should never happen, but just in case.
    return null;
  }

  return <NarrativeResearchPage runId={runId} />;
}
