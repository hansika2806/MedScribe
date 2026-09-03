import GuidelineCitations from './GuidelineCitations'
import ProvenancePanel from './ProvenancePanel'

function confidenceMeta(score = 0) {
  if (score >= 0.85) return { label: 'High Confidence', className: 'bg-emerald-100 text-emerald-800' }
  if (score >= 0.7) return { label: 'Review Recommended', className: 'bg-amber-100 text-amber-800' }
  return { label: 'Low Confidence - Review Required', className: 'bg-red-100 text-red-800' }
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function uniqueTerms(values) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
    .sort((a, b) => b.length - a.length)
}

function normalizeSafetyAlerts(values = []) {
  const byTerm = new Map()
  values.forEach((value) => {
    const term = String(value?.term || '').trim()
    if (!term) return
    byTerm.set(term.toLowerCase(), {
      ...value,
      term
    })
  })
  return [...byTerm.values()].sort((a, b) => b.term.length - a.term.length)
}

function HighlightedContent({ content = '', uncertainSpans = [], safetyAlerts = [] }) {
  const spans = uniqueTerms(uncertainSpans.map((span) => span.text))
  const alerts = normalizeSafetyAlerts(safetyAlerts)
  const alertTerms = alerts.map((alert) => alert.term)
  const terms = uniqueTerms([...alertTerms, ...spans])
  if (!terms.length) return <p className="whitespace-pre-wrap leading-7 text-slate-800">{content}</p>

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi')
  const parts = content.split(pattern)
  return (
    <p className="whitespace-pre-wrap leading-7 text-slate-800">
      {parts.map((part, index) => {
        const lowerPart = part.toLowerCase()
        const safetyAlert = alerts.find((alert) => alert.term.toLowerCase() === lowerPart)
        const uncertainMatch = spans.some((span) => span.toLowerCase() === lowerPart)
        if (!safetyAlert && !uncertainMatch) {
          return <span key={`${part}-${index}`}>{part}</span>
        }
        return (
          <mark
            key={`${part}-${index}`}
            className={`rounded px-1 ${
              safetyAlert
                ? 'bg-red-200 text-red-950 ring-1 ring-red-300'
                : 'bg-amber-200 text-amber-950'
            }`}
            title={safetyAlert ? safetyAlert.detail : 'Low confidence span'}
          >
            {part}
          </mark>
        )
      })}
    </p>
  )
}

export default function SOAPSection({
  title,
  sectionKey,
  content,
  confidence,
  entities = [],
  uncertain_spans = [],
  safetyAlerts = [],
  diagnoses = [],
  icd10Codes = [],
  guidelineCitations = [],
  retrievedGuidelines = []
}) {
  const meta = confidenceMeta(confidence)
  const contentLower = String(content || '').toLowerCase()
  const visibleSafetyAlerts = sectionKey === 'plan'
    ? normalizeSafetyAlerts(safetyAlerts).filter((alert) => contentLower.includes(alert.term.toLowerCase()))
    : []

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-slate-100 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
        <span className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${meta.className}`}>
          {meta.label} · {Math.round((confidence || 0) * 100)}%
        </span>
      </div>

      <div className="mt-4">
        {visibleSafetyAlerts.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {visibleSafetyAlerts.map((alert) => (
              <span
                key={`${alert.term}-${alert.detail}`}
                className="inline-flex max-w-full items-center gap-2 rounded-md border border-red-300 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-900"
                title={alert.detail}
              >
                <span className="shrink-0 rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                  {alert.urgency === 'urgent' ? 'urgent' : 'review'}
                </span>
                <span className="truncate">{alert.term}</span>
              </span>
            ))}
          </div>
        )}
        <HighlightedContent
          content={content}
          uncertainSpans={uncertain_spans}
          safetyAlerts={visibleSafetyAlerts}
        />
      </div>

      {sectionKey === 'assessment' && diagnoses.length > 0 && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
          <h3 className="text-sm font-semibold text-slate-800">Diagnoses</h3>
          <div className="mt-2 space-y-2">
            {diagnoses.map((diagnosis) => {
              const code = icd10Codes.find((item) => item.diagnosis === diagnosis || item.diagnosis_text === diagnosis)
              const codeValue = code?.code || code?.icd10_code || 'PENDING'
              return (
                <div key={diagnosis} className="flex flex-col gap-1 rounded-md bg-white px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <span className="font-medium text-slate-900">{diagnosis}</span>
                  <span className={`w-fit rounded-full px-2 py-1 text-xs font-semibold ${codeValue === 'PENDING' ? 'bg-slate-200 text-slate-600' : 'bg-blue-100 text-blue-800'}`}>
                    ICD-10: {codeValue}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {sectionKey === 'plan' && (
        <GuidelineCitations guidelines={retrievedGuidelines.length ? retrievedGuidelines : guidelineCitations.map((item) => ({ source: item }))} />
      )}

      <ProvenancePanel entities={entities} />
    </section>
  )
}
