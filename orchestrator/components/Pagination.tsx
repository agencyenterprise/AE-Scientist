"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"

export function Pagination({ total, page, pageSize }: { total: number; page: number; pageSize: number }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const router = useRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()

  const setPage = (newPage: number) => {
    const params = new URLSearchParams(searchParams)
    params.set("page", newPage.toString())
    router.replace(`${pathname}?${params.toString()}` as any)
  }

  return (
    <div className="flex items-center justify-between text-sm text-slate-300">
      <div>
        Page {page} of {totalPages}
      </div>
      <div className="flex items-center gap-2">
        <button
          className="rounded border border-slate-700 px-3 py-1 text-xs uppercase tracking-wide text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => setPage(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </button>
        <button
          className="rounded border border-slate-700 px-3 py-1 text-xs uppercase tracking-wide text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => setPage(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </button>
      </div>
    </div>
  )
}
