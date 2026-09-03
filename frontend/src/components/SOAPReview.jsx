import { useMemo, useState } from 'react'
import ApproveButton from './ApproveButton'
import LabValueInput from './LabValueInput'
import QAFlagsPanel from './QAFlagsPanel'
import SafetyFlagsPanel from './SafetyFlagsPanel'
import SOAPSection from './SOAPSection'

function banner(reviewType) {
  if (reviewType === 'urgent_safety') {
    return { className: 'border-red-300 bg-red-700 text-white', text: '⚠️ URGENT SAFETY REVIEW' }
  }
  if (reviewType === 'low_confidence') {
    return { className: 'border-amber-300 bg-amber-500 text-amber-950', text: '📋 REVIEW REQUIRED' }
  }
  return { className: 'border-emerald-300 bg-emerald-600 text-white', text: '✅ READY FOR APPROVAL' }
}

function hasPendingLabs(responseData) {
  const objective = responseData?.soap_note?.objective?.content || ''
  const labs = responseData?.lab_values || []
  return labs.some((lab) => lab.flag || !lab.value) || (/pending/i.test(objective) && /lab/i.test(objective))
}

function extractPlanSafetyAlerts(safetyResult = {}) {
  const flags = safetyResult?.safety_flags || []
  const alerts = []
  const seen = new Set()

  const addTerm = (term, flag) => {
    const normalized = String(term || '').trim()
    const key = normalized.toLowerCase()
    if (normalized.length <= 1 || seen.has(key)) return
    seen.add(key)
    alerts.push({
      term: normalized,
      detail: flag.detail || 'Medication safety review required',
      checkType: flag.check_type || 'safety',
      urgency: flag.urgency || 'review'
    })
  }

  flags.forEach((flag) => {
    if (Array.isArray(flag.terms)) flag.terms.forEach((term) => addTerm(term, flag))
    if (flag.drug) addTerm(flag.drug, flag)
    if (Array.isArray(flag.drugs)) flag.drugs.forEach((term) => addTerm(term, flag))
    if (Array.isArray(flag.medications)) flag.medications.forEach((term) => addTerm(term, flag))

    const detail = flag.detail || ''
    const interaction = detail.match(/detected:\s*([^+]+)\+\s*([^,]+)/i)
    if (interaction) {
      addTerm(interaction[1], flag)
      addTerm(interaction[2], flag)
    }

    const dosage = detail.match(/^(.+?)\s+dose\s+/i)
    if (dosage) addTerm(dosage[1], flag)

    const allergy = detail.match(/Plan mentions\s+(.+?),\s+which/i)
    if (allergy) addTerm(allergy[1], flag)
  })

  return alerts
}

function ConfidenceSummary({ qaResult }) {
  const scores = qaResult?.section_scores || {}
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold uppercase text-slate-500">Confidence summary</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-4">
        {['subjective', 'objective', 'assessment', 'plan'].map((section) => (
          <div key={section} className="rounded-md bg-slate-50 px-3 py-2">
            <div className="text-xs uppercase text-slate-500">{section}</div>
            <div className="mt-1 text-lg font-semibold text-slate-950">{Math.round((scores[section] || 0) * 100)}%</div>
          </div>
        ))}
      </div>
    </section>
  )
}

function PatientContextSummary({ patientContext = {} }) {
  const rows = [
    ['Age', patientContext.age],
    ['Gender', patientContext.gender],
    ['Allergies', patientContext.allergies],
    ['Current meds', patientContext.current_meds],
    ['Chief complaint', patientContext.chief_complaint]
  ].filter(([, value]) => String(value || '').trim())

  if (!rows.length) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold uppercase text-slate-500">Patient context</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className={label === 'Chief complaint' ? 'sm:col-span-2' : ''}>
            <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
            <div className="mt-1 whitespace-pre-wrap text-sm font-medium text-slate-900">{value}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

function DiarizationBadge({ method }) {
  const normalized = method || 'unknown'
  if (normalized === 'pyannote') {
    return (
      <span
        className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800"
        title="Speaker identification using pyannote AI model"
      >
        🎙️ Real Diarization ✓
      </span>
    )
  }
  if (normalized === 'speechbrain') {
    return (
      <span
        className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900"
        title="Speaker identification using Speechbrain embeddings"
      >
        🎙️ AI Diarization
      </span>
    )
  }
  return (
    <span
      className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-800"
      title="Speaker identification unavailable. Doctor/Patient labels may be inaccurate. Review speaker attribution carefully."
    >
      ⚠️ Fallback Diarization
    </span>
  )
}

function LabValuesExtractedPanel({ values, pageCount }) {
  const rows = Object.entries(values || {})
  if (!rows.length) return null

  return (
    <section className="rounded-lg border border-emerald-200 bg-white shadow-sm">
      <div className="rounded-t-lg bg-emerald-600 px-5 py-3 text-sm font-semibold text-white">
        📄 Lab Values Extracted from PDF
      </div>
      <div className="p-5">
        <div className="mb-3 text-sm text-emerald-900">
          {rows.length} values extracted from {pageCount || 0} page PDF
        </div>
        <div className="overflow-hidden rounded-md border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Test Name</th>
                <th className="px-4 py-3">Value</th>
                <th className="px-4 py-3">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map(([name, lab]) => (
                <tr key={name}>
                  <td className="px-4 py-3 font-medium text-slate-950">{name.replaceAll('_', ' ')}</td>
                  <td className="px-4 py-3 text-slate-700">{lab?.value || 'N/A'}</td>
                  <td className="px-4 py-3 text-slate-700">PDF (OCR verified)</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function NoPdfObjectiveNote() {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-medium text-amber-900">
      No test report uploaded. Lab values will be based on verbal mentions in consultation only.
    </div>
  )
}

function FallbackSubjectiveWarning() {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-sm font-medium text-red-900">
      ⚠️ Speaker diarization was not available for this consultation. Symptom attribution to Patient may be inaccurate. Please verify.
    </div>
  )
}

export default function SOAPReview({ responseData, onNewConsultation, onSessionUpdate, onApproved, physician }) {
  const [data, setData] = useState(responseData)
  const [labsSaved, setLabsSaved] = useState(!hasPendingLabs(responseData))
  const [approved, setApproved] = useState(Boolean(responseData?.approved))
  const [approvedAt, setApprovedAt] = useState(responseData?.approved_at)

  const soap = data?.soap_note || {}
  const reviewType = data?.review_type || 'standard_approval'
  const bannerMeta = banner(reviewType)
  const extractedLabValues = data?.extracted_lab_values || {}
  const hasExtractedPdfLabs = Object.keys(extractedLabValues).length > 0
  const noPdfUploaded = data?.ocr_method === 'no_pdf'
  const safetyAlerts = useMemo(() => extractPlanSafetyAlerts(data?.safety_result), [data?.safety_result])

  const sections = useMemo(() => [
    { key: 'subjective', title: 'Subjective', data: soap.subjective },
    { key: 'objective', title: 'Objective', data: soap.objective },
    { key: 'assessment', title: 'Assessment', data: soap.assessment },
    { key: 'plan', title: 'Plan', data: soap.plan }
  ], [soap])

  const handleLabsSaved = (labs) => {
    const updated = { ...data, lab_values: labs }
    setData(updated)
    setLabsSaved(true)
    onSessionUpdate(updated)
  }

  const handleApproved = (approval) => {
    const updated = { ...data, approved: true, approved_at: approval.approved_at }
    setData(updated)
    setApproved(true)
    setApprovedAt(approval.approved_at)
    onSessionUpdate(updated)
    onApproved?.(approval)
  }

  return (
    <main className="min-h-screen bg-slate-50 pb-28">
      <div className={`border-b px-4 py-5 ${bannerMeta.className}`}>
        <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold">{bannerMeta.text}</h1>
            <div className="mt-1 text-sm opacity-90">
              Reviewing as: {physician?.physician_name || 'Physician'} · {physician?.department || 'Department'}
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:items-end">
            <DiarizationBadge method={data?.diarization_method} />
            <div className="break-all font-mono text-xs opacity-90">Session: {data?.session_id}</div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <SafetyFlagsPanel safetyResult={data?.safety_result} />
        {data?.qa_result && <QAFlagsPanel qaResult={data?.qa_result} />}
        {reviewType === 'standard_approval' && <ConfidenceSummary qaResult={data?.qa_result} />}
        <PatientContextSummary patientContext={data?.patient_context} />

        {sections.map((section) => (
          <div key={section.key} className="space-y-5">
            {section.key === 'subjective' && data?.diarization_method === 'fallback' && <FallbackSubjectiveWarning />}
            {section.key === 'objective' && hasExtractedPdfLabs && (
              <LabValuesExtractedPanel values={extractedLabValues} pageCount={data?.ocr_page_count} />
            )}
            {section.key === 'objective' && noPdfUploaded && <NoPdfObjectiveNote />}
            <SOAPSection
              sectionKey={section.key}
              title={section.title}
              content={section.data?.content || ''}
              confidence={section.data?.confidence || 0}
              entities={section.data?.entities || []}
              uncertain_spans={section.data?.uncertain_spans || []}
              safetyAlerts={safetyAlerts}
              diagnoses={section.data?.diagnoses || []}
              icd10Codes={data?.icd10_codes || []}
              guidelineCitations={section.data?.guideline_citations || []}
              retrievedGuidelines={data?.retrieved_guidelines || []}
            />
          </div>
        ))}

        <LabValueInput sessionId={data?.session_id} responseData={data} onSaved={handleLabsSaved} />

        {approved && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-900">
            This consultation is approved and shown in read-only mode.
            <button type="button" onClick={onNewConsultation} className="ml-2 underline">Start a new consultation</button>
          </div>
        )}
      </div>

      {!approved && (
        <ApproveButton
          sessionId={data?.session_id}
          disabled={!labsSaved}
          approved={approved}
          approvedAt={approvedAt}
          onApproved={handleApproved}
        />
      )}
    </main>
  )
}
