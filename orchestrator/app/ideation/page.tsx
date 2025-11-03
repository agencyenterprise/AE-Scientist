import { IdeationPageClient } from "@/components/IdeationPageClient"
import { getIdeationRequests } from "@/lib/data/ideations"

export const dynamic = "force-dynamic"

type SearchParams = {
  [key: string]: string | string[] | undefined
}

export default async function IdeationPage({ searchParams }: { searchParams: SearchParams }) {
  const hypothesisIdParam = Array.isArray(searchParams.hypothesisId)
    ? searchParams.hypothesisId[0]
    : searchParams.hypothesisId

  const initialData = await getIdeationRequests(1, 25, undefined, hypothesisIdParam)
  return (
    <IdeationPageClient initialData={initialData} initialHypothesisId={hypothesisIdParam ?? ""} />
  )
}
