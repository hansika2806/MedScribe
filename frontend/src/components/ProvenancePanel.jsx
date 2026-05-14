import { useState } from 'react'

function confidenceClass(score) {
  if (score >= 0.85) return 'bg-emerald-100 text-emerald-800'
  if (score >= 0.7) return 'bg-amber-100 text-amber-800'
  return 'bg-red-100 text-red-800'
}

export default function ProvenancePanel({ entities = [] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-5 border-t border-slate-200 pt-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="text-sm font-semibold text-emerald-700 hover:text-emerald-800"
      >
        {open ? 'Hide provenance' : 'Show provenance'}
      </button>

      {open && (
        <div className="mt-4 overflow-x-auto rounded-md border border-slate-200">
          {entities.length === 0 ? (
            <p className="px-4 py-3 text-sm text-slate-500">No provenance records for this section</p>
          ) : (
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-3">Claim</th>
                  <th className="px-3 py-3">Source</th>
                  <th className="px-3 py-3">Speaker</th>
                  <th className="px-3 py-3">Original utterance</th>
                  <th className="px-3 py-3">Verified</th>
                  <th className="px-3 py-3">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {entities.map((entity, index) => (
                  <tr key={`${entity.claim}-${index}`}>
                    <td className="max-w-48 px-3 py-3 font-medium text-slate-900">{entity.claim}</td>
                    <td className="px-3 py-3 text-slate-600">{entity.source || 'Transcript'}</td>
                    <td className="px-3 py-3 text-slate-600">{entity.speaker || 'System'}</td>
                    <td className="max-w-md px-3 py-3 text-slate-600">{entity.utterance || 'Not available'}</td>
                    <td className="px-3 py-3">
                      <span className={entity.verified ? 'text-emerald-700' : 'text-red-700'}>
                        {entity.verified ? '✓' : '✕'}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold ${confidenceClass(entity.confidence || 0)}`}>
                        {Math.round((entity.confidence || 0) * 100)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

