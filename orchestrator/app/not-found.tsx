export default function NotFound() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-start gap-4 py-10">
      <h1 className="text-2xl font-semibold text-slate-100">Not found</h1>
      <p className="text-sm text-slate-400">
        The resource you were looking for does not exist or has been removed.
      </p>
      <a className="text-sm text-sky-400 hover:text-sky-300" href="/">
        Back to overview
      </a>
    </div>
  )
}
