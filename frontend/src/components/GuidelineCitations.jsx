import { useState } from 'react'

export default function GuidelineCitations({ guidelines = [] }) {
  const [openIndex, setOpenIndex] = useState(null)

  if (!guidelines.length) {
    return <p className="mt-3 text-sm text-slate-500">No guideline citations returned.</p>
  }

  return (
    <div className="mt-4">
      <h4 className="text-sm font-semibold text-slate-800">Guideline citations</h4>
      <div className="mt-2 flex flex-wrap gap-2">
        {guidelines.map((guideline, index) => {
          const label = `${guideline.source || 'Guideline'} ${guideline.section ? `§${guideline.section}` : ''}`.trim()
          const open = openIndex === index
          return (
            <div key={`${label}-${index}`} className="w-full sm:w-auto">
              <button
                type="button"
                onClick={() => setOpenIndex(open ? null : index)}
                className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800 hover:bg-blue-100"
              >
                {label}
              </button>
              {open && (
                <div className="mt-2 max-w-xl rounded-md border border-blue-200 bg-white p-3 text-sm text-slate-700 shadow-sm">
                  <div className="font-semibold text-slate-900">{guideline.source}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Year: {guideline.year || 'unknown'} · Section: {guideline.section || 'not specified'} · Relevance: {guideline.relevance_score ?? 'n/a'}
                  </div>
                  <p className="mt-2 leading-6">{(guideline.content || '').slice(0, 200)}...</p>
                  <div className="mt-2 text-xs text-slate-500">Population match: {guideline.population_match || 'unknown'}</div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

