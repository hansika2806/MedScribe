const PDF_LAB_SOURCES = new Set(['ocr', 'ocr_only', 'pdf', 'pdf_ocr', 'both'])

export function formatLabName(name = '') {
  return String(name || 'Lab value')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

export function isPdfLab(lab = {}) {
  return PDF_LAB_SOURCES.has(String(lab.source || '').toLowerCase())
}

export function isVerifiedPdfLab(lab = {}) {
  return isPdfLab(lab) && lab.verified !== false && Boolean(String(lab.value || '').trim())
}

export function isLabManualReviewRequired(lab = {}) {
  const value = String(lab.value || '').trim()
  if (!value) return true

  if (isVerifiedPdfLab(lab)) return false

  const flag = String(lab.flag || '').toLowerCase()
  const pendingFlag = /(pending|manual|uncertain|unverified|not confirmed|could not|missing)/i.test(flag)
  return lab.verified === false || pendingFlag
}

export function getPendingLabRows(responseData = {}) {
  const labs = responseData?.lab_values || []
  const pendingRows = labs.filter(isLabManualReviewRequired)
  if (pendingRows.length) return pendingRows

  const objective = responseData?.soap_note?.objective?.content || ''
  const hasExtractedPdfLabs = Object.keys(responseData?.extracted_lab_values || {}).length > 0
  if (!hasExtractedPdfLabs && /pending/i.test(objective) && /lab/i.test(objective)) {
    return [{
      lab_name: 'Pending lab value',
      value: '',
      unit: '',
      source: 'manual_physician_entry',
      verified: false,
      flag: 'missing_manual_entry'
    }]
  }
  return []
}

export function labRowsFromExtracted(values = {}) {
  return Object.entries(values || {}).map(([name, lab]) => ({
    lab_name: lab?.lab_name || lab?.display_name || name,
    value: lab?.value || '',
    unit: lab?.unit || '',
    source: lab?.source || 'ocr_only',
    verified: lab?.verified !== false,
    flag: lab?.flag || lab?.interpretation || null,
    reference_range: lab?.reference_range || '',
    display_name: lab?.display_name || formatLabName(name),
    interpretation: lab?.interpretation || lab?.flag || ''
  }))
}

export function mergeLabRows(extractedRows = [], existingRows = []) {
  const byName = new Map()
  extractedRows.forEach((row) => {
    byName.set(String(row.lab_name || row.name || '').toLowerCase(), row)
  })
  existingRows.forEach((row) => {
    const key = String(row.lab_name || row.name || '').toLowerCase()
    if (!byName.has(key)) byName.set(key, row)
  })
  return [...byName.values()]
}

export function labStatus(lab = {}) {
  const flag = String(lab.flag || lab.interpretation || '').toLowerCase()
  if (/(critical|panic)/.test(flag)) {
    return { label: 'Critical', className: 'border-red-200 bg-red-50 text-red-800' }
  }
  if (/(high|low|abnormal)/.test(flag)) {
    return { label: flag.includes('low') ? 'Low' : 'High', className: 'border-amber-200 bg-amber-50 text-amber-800' }
  }
  if (isVerifiedPdfLab(lab)) {
    return { label: 'PDF verified', className: 'border-emerald-200 bg-emerald-50 text-emerald-800' }
  }
  if (isLabManualReviewRequired(lab)) {
    return { label: 'Needs value', className: 'border-red-200 bg-red-50 text-red-800' }
  }
  return { label: 'In range', className: 'border-slate-200 bg-slate-50 text-slate-700' }
}
