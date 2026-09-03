import { useMemo, useState } from 'react'
import { jsPDF } from 'jspdf'

function sectionText(title, section) {
  return `${title}\n${section?.content || 'N/A'}`
}

function formatList(title, values, formatter) {
  if (!values?.length) return `${title}\nN/A`
  return `${title}\n${values.map(formatter).join('\n')}`
}

function buildApprovedNoteText(responseData, approval, physician) {
  const soap = responseData?.soap_note || {}
  const confidence = responseData?.qa_result?.overall_confidence
  const approvedAt = approval?.approved_at || responseData?.approved_at || 'N/A'
  const patient = responseData?.patient_context || {}

  return [
    'MedScribe Approved SOAP Note',
    '',
    `Session ID: ${responseData?.session_id || 'N/A'}`,
    `Physician: ${approval?.approved_by || physician?.physician_name || 'N/A'}`,
    `Approved at: ${approvedAt}`,
    `Review type: ${responseData?.review_type || 'standard_approval'}`,
    `Overall confidence: ${confidence == null ? 'N/A' : `${Math.round(confidence * 100)}%`}`,
    '',
    'Patient Context',
    `Age: ${patient.age || 'N/A'}`,
    `Gender: ${patient.gender || 'N/A'}`,
    `Allergies: ${patient.allergies || 'N/A'}`,
    `Current meds: ${patient.current_meds || 'N/A'}`,
    `Chief complaint: ${patient.chief_complaint || 'N/A'}`,
    '',
    sectionText('Subjective', soap.subjective),
    '',
    sectionText('Objective', soap.objective),
    '',
    sectionText('Assessment', soap.assessment),
    '',
    sectionText('Plan', soap.plan),
    '',
    formatList(
      'ICD-10 Codes',
      responseData?.icd10_codes || [],
      (item) => `- ${item.diagnosis || item.diagnosis_text || 'Diagnosis'}: ${item.code || item.icd10_code || 'PENDING'}`
    ),
    '',
    formatList(
      'Lab Values',
      responseData?.lab_values || [],
      (item) => `- ${item.lab_name || item.name || 'Lab'}: ${item.value || 'N/A'} ${item.unit || ''}`.trim()
    ),
    '',
    formatList(
      'Safety Flags',
      responseData?.safety_result?.safety_flags || [],
      (item) => `- ${item.check_type || 'Safety'}: ${item.detail || 'Review required'}`
    )
  ].join('\n')
}

function safeFileId(value) {
  return String(value || 'approved-note').replace(/[^a-z0-9_-]+/gi, '_')
}

function downloadPdf(text, sessionId) {
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const margin = 48
  const maxWidth = doc.internal.pageSize.getWidth() - margin * 2
  const pageHeight = doc.internal.pageSize.getHeight()
  const lines = doc.splitTextToSize(text, maxWidth)
  let y = margin

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(11)

  lines.forEach((line) => {
    if (y > pageHeight - margin) {
      doc.addPage()
      y = margin
    }
    doc.text(line, margin, y)
    y += 15
  })

  doc.save(`medscribe-${safeFileId(sessionId)}.pdf`)
}

function copyTextFallback(text) {
  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.setAttribute('readonly', '')
  textArea.style.position = 'fixed'
  textArea.style.left = '-9999px'
  document.body.appendChild(textArea)
  textArea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textArea)
  if (!copied) throw new Error('copy failed')
}

export default function ApprovalSuccessScreen({
  responseData,
  approval,
  physician,
  onStartNew,
  onViewNote
}) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState('')
  const [pdfError, setPdfError] = useState('')
  const confidence = responseData?.qa_result?.overall_confidence
  const approvedAt = approval?.approved_at || responseData?.approved_at
  const approvedText = useMemo(
    () => buildApprovedNoteText(responseData, approval, physician),
    [responseData, approval, physician]
  )

  const copyAsText = async () => {
    setCopyError('')
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(approvedText)
      } else {
        copyTextFallback(approvedText)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      setCopyError('Could not copy to clipboard in this browser.')
    }
  }

  const handleDownloadPdf = () => {
    setPdfError('')
    try {
      downloadPdf(approvedText, responseData?.session_id)
    } catch {
      setPdfError('Could not create the PDF in this browser.')
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10">
      <section className="mx-auto max-w-2xl rounded-lg border border-emerald-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl font-bold text-emerald-700">
          OK
        </div>
        <h1 className="mt-5 text-2xl font-semibold text-slate-950">Note Approved and Saved</h1>
        <div className="mt-6 overflow-hidden rounded-lg border border-slate-200 text-left">
          {[
            ['Session ID', responseData?.session_id],
            ['Physician', approval?.approved_by || physician?.physician_name],
            ['Timestamp', approvedAt],
            ['Review type', responseData?.review_type || 'standard_approval'],
            ['Overall confidence score', confidence == null ? 'N/A' : `${Math.round(confidence * 100)}%`]
          ].map(([label, value]) => (
            <div key={label} className="grid grid-cols-1 gap-1 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:grid-cols-2">
              <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
              <div className="break-words text-sm font-medium text-slate-900">{value || 'N/A'}</div>
            </div>
          ))}
        </div>

        <div className="mt-7 grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={handleDownloadPdf}
            className="rounded-md bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Download as PDF
          </button>
          <button
            type="button"
            onClick={copyAsText}
            className="rounded-md border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          >
            {copied ? 'Copied' : 'Copy as text'}
          </button>
        </div>
        {copyError && <p className="mt-3 text-sm font-medium text-red-700">{copyError}</p>}
        {pdfError && <p className="mt-3 text-sm font-medium text-red-700">{pdfError}</p>}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={onStartNew}
            className="rounded-md bg-emerald-600 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-700"
          >
            Start New Consultation
          </button>
          <button
            type="button"
            onClick={onViewNote}
            className="rounded-md border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          >
            View Approved Note
          </button>
        </div>
      </section>
    </main>
  )
}
