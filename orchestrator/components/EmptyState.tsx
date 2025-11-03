export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center">
      <p className="text-lg font-semibold text-slate-100">{title}</p>
      <p className="mt-2 text-sm text-slate-400">{description}</p>
    </div>
  )
}
