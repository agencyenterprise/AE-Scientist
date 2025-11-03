"use client"

import { useRouter } from "next/navigation"
import { FormEvent, useState, useTransition } from "react"

export function HumanValidationForm({ runId }: { runId: string }) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [verdict, setVerdict] = useState<"pass" | "fail" | "">("")
  const [notes, setNotes] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!verdict) {
      setError("Select a verdict before submitting")
      return
    }
    startTransition(async () => {
      setError(null)
      setSuccess(false)
      const response = await fetch(`/api/validations/${runId}/human`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ verdict, notes })
      })
      if (!response.ok) {
        setError("Failed to submit verdict")
        return
      }
      setSuccess(true)
      setNotes("")
      setVerdict("")
      router.refresh()
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <fieldset className="space-y-2">
        <legend className="text-sm font-semibold text-slate-200">Human verdict</legend>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="radio"
            value="pass"
            checked={verdict === "pass"}
            onChange={(event) => setVerdict(event.target.value as "pass")}
          />
          Pass
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="radio"
            value="fail"
            checked={verdict === "fail"}
            onChange={(event) => setVerdict(event.target.value as "fail")}
          />
          Fail
        </label>
      </fieldset>
      <label className="block text-sm text-slate-300">
        Notes
        <textarea
          className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </label>
      <div className="flex items-center gap-4">
        <button
          type="submit"
          className="rounded border border-emerald-600/60 bg-emerald-900/40 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:opacity-40"
          disabled={pending}
        >
          Submit verdict
        </button>
        {error && <span className="text-sm text-rose-400">{error}</span>}
        {success && <span className="text-sm text-emerald-400">Saved!</span>}
      </div>
    </form>
  )
}
