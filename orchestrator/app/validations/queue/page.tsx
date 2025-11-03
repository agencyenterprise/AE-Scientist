import { getValidationQueue } from "@/lib/data/validations"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import type { Validation } from "@/lib/schemas/validation"
import { ValidationQueueCard } from "@/components/ValidationQueueCard"
import { Pagination } from "@/components/Pagination"
import { extract } from "@/lib/utils/extract"

export const dynamic = "force-dynamic"

export default async function ValidationQueuePage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const params = await searchParams
  const page = parseInt(extract(params.page) ?? "1", 10) || 1
  const pageSize = 10
  const { items, total } = await getValidationQueue(page, pageSize)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-100">Validation Queue</h1>
        <p className="text-sm text-slate-400">
          Human reviewers evaluate the AI Scientist outputs here. Every entry reflects the latest
          MongoDB state.
        </p>
      </header>
      <div className="space-y-4">
        {items.length === 0 && (
          <p className="text-sm text-slate-500">No runs awaiting human validation.</p>
        )}
        {items.map(({ run, hypothesis, validations }: { run: Run; hypothesis?: Hypothesis; validations: Validation[] }) => (
          <ValidationQueueCard
            key={run._id}
            run={run}
            hypothesis={hypothesis}
            validations={validations}
          />
        ))}
      </div>
      <Pagination total={total} page={page} pageSize={pageSize} />
    </div>
  )
}
