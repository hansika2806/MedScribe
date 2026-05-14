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

export default function SOAPReview({ responseData, onNewConsultation, onSessionUpdate }) {
  const [data, setData] = useState(responseData)
  const [labsSaved, setLabsSaved] = useState(!hasPendingLabs(responseData))
  const [approved, setApproved] = useState(Boolean(responseData?.approved))
  const [approvedAt, setApprovedAt] = useState(responseData?.approved_at)

  const soap = data?.soap_note || {}
  const reviewType = data?.review_type || 'standard_approval'
  const bannerMeta = banner(reviewType)
  const showQa = reviewType === 'low_confidence' || (data?.qa_result?.flags || []).length > 0

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

  const handleApproved = (timestamp) => {
    const updated = { ...data, approved: true, approved_at: timestamp }
    setData(updated)
    setApproved(true)
    setApprovedAt(timestamp)
    onSessionUpdate(updated)
  }

  return (
    <main className="min-h-screen bg-slate-50 pb-28">
      <div className={`border-b px-4 py-5 ${bannerMeta.className}`}>
        <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-xl font-bold">{bannerMeta.text}</h1>
          <div className="font-mono text-xs opacity-90">Session: {data?.session_id}</div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        {reviewType === 'urgent_safety' && <SafetyFlagsPanel safetyResult={data?.safety_result} />}
        {showQa && <QAFlagsPanel qaResult={data?.qa_result} />}
        {reviewType === 'standard_approval' && <ConfidenceSummary qaResult={data?.qa_result} />}

        {sections.map((section) => (
          <SOAPSection
            key={section.key}
            sectionKey={section.key}
            title={section.title}
            content={section.data?.content || ''}
            confidence={section.data?.confidence || 0}
            entities={section.data?.entities || []}
            uncertain_spans={section.data?.uncertain_spans || []}
            diagnoses={section.data?.diagnoses || []}
            icd10Codes={data?.icd10_codes || []}
            guidelineCitations={section.data?.guideline_citations || []}
            retrievedGuidelines={data?.retrieved_guidelines || []}
          />
        ))}

        <LabValueInput sessionId={data?.session_id} responseData={data} onSaved={handleLabsSaved} />

        {approved && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-900">
            This consultation is approved. <button type="button" onClick={onNewConsultation} className="ml-2 underline">Start a new consultation</button>
          </div>
        )}
      </div>

      <ApproveButton
        sessionId={data?.session_id}
        disabled={!labsSaved}
        approved={approved}
        approvedAt={approvedAt}
        onApproved={handleApproved}
      />
    </main>
  )
}

