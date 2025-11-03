import { getOverviewData } from "@/lib/data/overview"
import { OverviewPageClient } from "@/components/OverviewPageClient"

export const dynamic = "force-dynamic"

export default async function OverviewPage() {
  const data = await getOverviewData()
  return <OverviewPageClient initialData={data} />
}
