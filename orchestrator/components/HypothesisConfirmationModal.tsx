"use client"

import { useState, useEffect } from "react"

interface HypothesisConfirmationModalProps {
  isOpen: boolean
  title: string
  description: string
  onConfirm: (title: string, description: string) => void
  onCancel: () => void
}

export function HypothesisConfirmationModal({
  isOpen,
  title: initialTitle,
  description: initialDescription,
  onConfirm,
  onCancel
}: HypothesisConfirmationModalProps) {
  const [title, setTitle] = useState(initialTitle)
  const [description, setDescription] = useState(initialDescription)

  // Update state when props change
  useEffect(() => {
    setTitle(initialTitle)
    setDescription(initialDescription)
  }, [initialTitle, initialDescription])

  if (!isOpen) return null

  const handleConfirm = () => {
    onConfirm(title, description)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h2 className="text-xl font-semibold text-slate-200 mb-4">
          Review & Edit Hypothesis
        </h2>
        
        <p className="text-sm text-slate-400 mb-6">
          The AI has extracted and structured your hypothesis. You can edit the title and description before creating the hypothesis.
        </p>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-300" htmlFor="modal-title">
              Title
            </label>
            <input
              id="modal-title"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter a title for your hypothesis"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-300" htmlFor="modal-description">
              Description
            </label>
            <textarea
              id="modal-description"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 font-mono"
              rows={15}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="rounded border border-sky-600/60 bg-sky-900/40 px-4 py-2 text-sm font-semibold text-sky-100 hover:bg-sky-900/60"
          >
            Create Hypothesis
          </button>
        </div>
      </div>
    </div>
  )
}

