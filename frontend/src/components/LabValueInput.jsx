import { useMemo, useState } from 'react'
import { updateLabValues } from '../api/client'

function inferPendingLabs(responseData) {
  const labs = responseData?.lab_values || []
  if (labs.length) return labs
  const objective = responseData?.soap_note?.objective?.content || ''
  if (/pending/i.test(objective) && /lab/i.test(objective)) {
    return [{ lab_name: 'Pending lab value', value: '', unit: '', source: 'manual_physician_entry', verified: true }]
  }
  return []
}

export default function LabValueInput({ sessionId, responseData, onSaved }) {
  const pendingLabs = useMemo(() => inferPendingLabs(responseData), [responseData])
  const [rows, setRows] = useState(
    pendingLabs.map((lab) => ({
      lab_name: lab.lab_name || lab.name || 'Lab value',
      value: lab.value || '',
      unit: lab.unit || '',
      source: 'manual_physician_entry',
      verified: true,
      date: lab.date || ''
    }))
  )
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  if (!pendingLabs.length || saved) {
    return saved ? (
      <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-900">
        Lab values saved. You can now approve the note.
      </section>
    ) : null
  }

  const updateRow = (index, field, value) => {
    setRows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)))
  }

  const save = async () => {
    setSaving(true)
    setError('')
    const result = await updateLabValues(sessionId, rows)
    setSaving(false)
    if (!result.ok) {
      setError(result.message)
      return
    }
    setSaved(true)
    onSaved(rows)
  }

  return (
    <section className="rounded-lg border border-amber-300 bg-amber-50 p-5">
      <h2 className="text-lg font-bold text-amber-950">Lab Values Pending</h2>
      <p className="mt-2 text-sm text-amber-900">
        The following lab values could not be read from the test report. Please enter them before approving.
      </p>

      <div className="mt-4 space-y-3">
        {rows.map((row, index) => (
          <div key={`${row.lab_name}-${index}`} className="grid gap-3 rounded-md border border-amber-200 bg-white p-3 md:grid-cols-4">
            <label className="text-sm">
              <span className="font-medium text-slate-700">Lab name</span>
              <input value={row.lab_name} readOnly className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-slate-700" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Value</span>
              <input value={row.value} onChange={(event) => updateRow(index, 'value', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Unit</span>
              <input value={row.unit} onChange={(event) => updateRow(index, 'unit', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Date</span>
              <input type="date" value={row.date} onChange={(event) => updateRow(index, 'date', event.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
          </div>
        ))}
      </div>

      {error && <p className="mt-3 text-sm font-medium text-red-700">{error}</p>}

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="mt-4 rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:bg-slate-300"
      >
        {saving ? 'Saving...' : 'Save Lab Values'}
      </button>
    </section>
  )
}

