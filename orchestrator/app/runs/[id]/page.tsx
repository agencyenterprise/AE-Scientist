import { notFound } from "next/navigation"
import { getRunDetail } from "@/lib/data/runs"
import { RunDetailClient } from "@/components/RunDetailClient"

export const dynamic = "force-dynamic"

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const detail = await getRunDetail(id)
  if (!detail) {
    notFound()
  }

  return <RunDetailClient initialData={detail} />
}
