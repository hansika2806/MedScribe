const failureModes = [
  { key: 'missing_field', label: 'Missing Field' },
  { key: 'population_mismatch', label: 'Population Mismatch' },
  { key: 'low_confidence', label: 'Low Confidence' },
  { key: 'undocumented', label: 'Undocumented Entity' },
  { key: 'provenance_integrity', label: 'Provenance Gap' }
]

function scoreClass(score) {
  if (score >= 0.85) return 'bg-emerald-100 text-emerald-800'
  if (score >= 0.7) return 'bg-amber-100 text-amber-800'
  return 'bg-red-100 text-red-800'
}

function readableMode(mode) {
  return failureModes.find((item) => item.key === mode)?.label || mode?.replaceAll('_', ' ') || 'Review Flag'
}

export default function QAFlagsPanel({ qaResult = {} }) {
  const flags = qaResult?.flags || []
  const scores = qaResult?.section_scores || {}
  const triggered = new Set(flags.map((flag) => flag.failure_mode))

  return (
    <section className="rounded-lg border border-amber-300 bg-amber-50 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-bold text-amber-950">Quality Review Required</h2>
        {qaResult?.pass && flags.length === 0 && (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            All quality checks passed
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {['subjective', 'objective', 'assessment', 'plan'].map((section) => {
          const score = Number(scores[section] || 0)
          return (
            <span key={section} className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreClass(score)}`}>
              {section}: {Math.round(score * 100)}%
            </span>
          )
        })}
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-5">
        {failureModes.map((mode) => {
          const active = triggered.has(mode.key)
          return (
            <div
              key={mode.key}
              className={`rounded-md border px-3 py-2 text-xs font-semibold ${
                active ? 'border-amber-400 bg-amber-100 text-amber-950' : 'border-slate-200 bg-white text-slate-500'
              }`}
            >
              {mode.label}
            </div>
          )
        })}
      </div>

      {flags.length > 0 && (
        <div className="mt-4 space-y-3">
          {flags.map((flag, index) => (
            <article key={`${flag.detail}-${index}`} className="rounded-md border border-amber-300 bg-white p-4">
              <div className="text-sm font-semibold text-amber-950">{readableMode(flag.failure_mode)}</div>
              <div className="mt-1 text-xs uppercase text-amber-700">{flag.section || 'all sections'}</div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{flag.detail}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

