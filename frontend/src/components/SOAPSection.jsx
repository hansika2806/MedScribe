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

function HighlightedContent({ content = '', uncertainSpans = [] }) {
  const spans = uncertainSpans.map((span) => span.text).filter(Boolean)
  if (!spans.length) return <p className="whitespace-pre-wrap leading-7 text-slate-800">{content}</p>

  const pattern = new RegExp(`(${spans.map(escapeRegExp).join('|')})`, 'gi')
  const parts = content.split(pattern)
  return (
    <p className="whitespace-pre-wrap leading-7 text-slate-800">
      {parts.map((part, index) => {
        const match = spans.some((span) => span.toLowerCase() === part.toLowerCase())
        return match ? (
          <mark key={`${part}-${index}`} className="rounded bg-amber-200 px-1 text-amber-950">
            {part}
          </mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
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
  diagnoses = [],
  icd10Codes = [],
  guidelineCitations = [],
  retrievedGuidelines = []
}) {
  const meta = confidenceMeta(confidence)

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-slate-100 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
        <span className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${meta.className}`}>
          {meta.label} · {Math.round((confidence || 0) * 100)}%
        </span>
      </div>

      <div className="mt-4">
        <HighlightedContent content={content} uncertainSpans={uncertain_spans} />
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

