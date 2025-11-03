"use client"

import { useState, type ReactNode } from "react"
import type { Validation } from "@/lib/schemas/validation"

export function ValidationSummary({ auto, human }: { auto?: Validation | null; human?: Validation | null }) {
  return (
    <div>
      <ValidationCard
        title="Auto Evaluation"
        validation={auto}
        emptyMessage="Awaiting automated verdict"
      />
    </div>
  )
}

// Define quantitative and qualitative field categorization
const QUANTITATIVE_FIELDS: Record<string, number> = {
  'Originality': 4, 'Quality': 4, 'Clarity': 4, 'Significance': 4,
  'Soundness': 4, 'Presentation': 4, 'Contribution': 4, 
  'Overall': 10, 'Confidence': 5
}

const QUALITATIVE_FIELDS = new Set([
  'Summary', 'Strengths', 'Weaknesses', 'Questions', 'Limitations', 'Decision'
])

function ValidationCard({
  title,
  validation,
  emptyMessage
}: {
  title: string
  validation?: Validation | null
  emptyMessage: string
}) {
  const [showModal, setShowModal] = useState(false)

  // Try to parse notes as JSON
  let parsedNotes: Record<string, any> | null = null
  
  if (validation?.notes) {
    try {
      parsedNotes = JSON.parse(validation.notes)
    } catch {
      // If parsing fails, display as plain text
    }
  }

  // Separate quantitative and qualitative data
  const quantitativeData: Record<string, any> = {}
  const qualitativeData: Record<string, any> = {}
  
  if (parsedNotes) {
    Object.entries(parsedNotes).forEach(([key, value]) => {
      if (key in QUANTITATIVE_FIELDS) {
        quantitativeData[key] = value
      } else if (QUALITATIVE_FIELDS.has(key)) {
        qualitativeData[key] = value
      } else {
        // Unknown fields go to qualitative
        qualitativeData[key] = value
      }
    })
  }

  const overallScore = quantitativeData['Overall']
  const decision = qualitativeData['Decision']

  // Override verdict based on score for display
  let displayVerdict = validation?.verdict
  if (typeof overallScore === 'number') {
    displayVerdict = overallScore >= 6 ? 'pass' : 'fail'
  }

  return (
    <>
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        {validation ? (
          <div className="mt-3 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <div className="text-xs text-slate-400">Verdict</div>
                <div className={`text-lg font-semibold ${displayVerdict === "pass" ? "text-emerald-400" : "text-rose-400"}`}>
                  {displayVerdict?.toUpperCase()}
                </div>
              </div>
              {overallScore !== undefined && (
                <div>
                  <div className="text-xs text-slate-400">Overall</div>
                  <div className="text-lg font-semibold text-amber-300">{overallScore}/10</div>
                </div>
              )}
              {decision && (
                <div>
                  <div className="text-xs text-slate-400">Decision</div>
                  <div className="text-sm font-medium text-slate-300">{decision}</div>
                </div>
              )}
            </div>
            <button
              onClick={(event) => {
                event.stopPropagation()
                setShowModal(true)
              }}
              className="rounded-lg border border-sky-700 bg-sky-900/40 px-4 py-2 text-sm font-medium text-sky-300 transition-colors hover:bg-sky-900/60 hover:text-sky-200"
            >
              View Details
            </button>
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">{emptyMessage}</p>
        )}
      </div>

      {/* Modal */}
      {showModal && validation && (
        <ValidationModal
          validation={validation}
          quantitativeData={quantitativeData}
          qualitativeData={qualitativeData}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  )
}

function ValidationModal({
  validation,
  quantitativeData,
  qualitativeData,
  onClose
}: {
  validation: Validation
  quantitativeData: Record<string, any>
  qualitativeData: Record<string, any>
  onClose: () => void
}) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())
  const [showSection, setShowSection] = useState<'quantitative' | 'qualitative' | 'both'>('both')

  const overallScore = quantitativeData['Overall']
  
  // Override verdict based on score for display
  let displayVerdict = validation.verdict
  if (typeof overallScore === 'number') {
    displayVerdict = overallScore >= 6 ? 'pass' : 'fail'
  }

  const toggleSection = (key: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(key)) {
      newExpanded.delete(key)
    } else {
      newExpanded.add(key)
    }
    setExpandedSections(newExpanded)
  }

  const hasQuantitative = Object.keys(quantitativeData).length > 0
  const hasQualitative = Object.keys(qualitativeData).length > 0

  // Recursively render arbitrary JSON values (strings, numbers, arrays, objects)
  function renderValue(value: any): ReactNode {
    if (value === null || value === undefined) {
      return <span className="text-slate-500">None</span>
    }
    const t = typeof value
    if (t === 'string' || t === 'number' || t === 'boolean') {
      return <span className="whitespace-pre-wrap break-words">{String(value)}</span>
    }
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-slate-500">Empty</span>
      }
      const isPrimitiveArray = value.every(v => {
        const tv = typeof v
        return tv === 'string' || tv === 'number' || tv === 'boolean'
      })
      if (isPrimitiveArray) {
        return (
          <ul className="list-disc pl-5 space-y-1">
            {value.map((v, idx) => (
              <li key={idx} className="whitespace-pre-wrap break-words">{String(v)}</li>
            ))}
          </ul>
        )
      }
      return (
        <div className="space-y-2">
          {value.map((v, idx) => (
            <div key={idx} className="rounded border border-slate-800/60 bg-slate-950/40 p-2">
              {renderValue(v)}
            </div>
          ))}
        </div>
      )
    }
    if (t === 'object') {
      const entries = Object.entries(value as Record<string, any>)
      if (entries.length === 0) {
        return <span className="text-slate-500">Empty</span>
      }
      return (
        <div className="space-y-2">
          {entries.map(([k, v]) => (
            <div key={k} className="rounded border border-slate-800/60 bg-slate-950/40 p-2">
              <div className="text-xs font-medium text-slate-400">{k}</div>
              <div className="mt-1 text-sm text-slate-300">{renderValue(v)}</div>
            </div>
          ))}
        </div>
      )
    }
    // Fallback
    try {
      return (
        <span className="whitespace-pre-wrap break-words">{JSON.stringify(value)}</span>
      )
    } catch {
      return <span className="whitespace-pre-wrap break-words">{String(value)}</span>
    }
  }

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <div 
        className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Auto Evaluation Details</h2>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-slate-400">Verdict:</span>
              <span className={`text-sm font-semibold ${displayVerdict === "pass" ? "text-emerald-400" : "text-rose-400"}`}>
                {displayVerdict?.toUpperCase()}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Toggle buttons */}
        {hasQuantitative && hasQualitative && (
          <div className="mb-4 flex gap-2 text-xs">
            <button
              onClick={() => setShowSection('both')}
              className={`rounded px-3 py-1.5 transition-colors ${
                showSection === 'both'
                  ? 'bg-sky-900/60 text-sky-300'
                  : 'bg-slate-800/40 text-slate-400 hover:text-slate-300'
              }`}
            >
              Both
            </button>
            <button
              onClick={() => setShowSection('quantitative')}
              className={`rounded px-3 py-1.5 transition-colors ${
                showSection === 'quantitative'
                  ? 'bg-sky-900/60 text-sky-300'
                  : 'bg-slate-800/40 text-slate-400 hover:text-slate-300'
              }`}
            >
              Scores
            </button>
            <button
              onClick={() => setShowSection('qualitative')}
              className={`rounded px-3 py-1.5 transition-colors ${
                showSection === 'qualitative'
                  ? 'bg-sky-900/60 text-sky-300'
                  : 'bg-slate-800/40 text-slate-400 hover:text-slate-300'
              }`}
            >
              Analysis
            </button>
          </div>
        )}

        <div className="space-y-6">
          {/* Quantitative Section */}
          {hasQuantitative && (showSection === 'quantitative' || showSection === 'both') && (
            <div className="space-y-3">
              <p className="text-sm font-semibold text-amber-400">📊 Quantitative Scores</p>
              <div className="grid grid-cols-3 gap-3">
                {Object.entries(quantitativeData).map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-amber-900/30 bg-amber-950/20 p-3">
                    <div className="text-xs text-slate-400">{key}</div>
                    <div className="mt-1 text-xl font-semibold text-amber-300">
                      {typeof value === "number" ? `${value} / ${QUANTITATIVE_FIELDS[key]}` : String(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Qualitative Section */}
          {hasQualitative && (showSection === 'qualitative' || showSection === 'both') && (
            <div className="space-y-3">
              <p className="text-sm font-semibold text-sky-400">📝 Qualitative Analysis</p>
              <div className="space-y-3">
                {Object.entries(qualitativeData).map(([key, value]) => {
                  const isExpanded = expandedSections.has(key)
                  const isString = typeof value === 'string'
                  const rawString = isString ? (value as string) : ''
                  const isLong = isString && rawString.length > 300
                  const displayString = isLong && !isExpanded
                    ? rawString.slice(0, 300) + '...'
                    : rawString

                  return (
                    <div key={key} className="rounded-lg border border-slate-700 bg-slate-950/50 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-medium text-sky-400">{key}</span>
                        {isLong && (
                          <button
                            onClick={() => toggleSection(key)}
                            className="shrink-0 text-xs text-slate-500 hover:text-slate-300"
                          >
                            {isExpanded ? '▼ Collapse' : '▶ Expand'}
                          </button>
                        )}
                      </div>
                      <div className="mt-2 text-sm text-slate-300">
                        {isString ? (
                          <span className="whitespace-pre-wrap break-words">{displayString}</span>
                        ) : (
                          renderValue(value)
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Timestamp */}
          <p className="text-xs text-slate-500">
            Submitted {new Date(validation.createdAt).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  )
}
