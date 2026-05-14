import { useState } from 'react'
import { approveConsultation } from '../api/client'

export default function ApproveButton({ sessionId, disabled, approved, approvedAt, onApproved }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const approve = async () => {
    setLoading(true)
    setError('')
    const result = await approveConsultation(sessionId)
    setLoading(false)
    if (!result.ok) {
      setError(result.message)
      return
    }
    onApproved(result.data.approved_at)
  }

  return (
    <div className="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-4 shadow-lg backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">This note will not be saved to the hospital record until you click Approve.</p>
          {error && <p className="mt-1 text-sm text-red-700">{error}</p>}
          {approved && <p className="mt-1 text-sm text-emerald-700">Approved at {approvedAt}</p>}
        </div>
        <button
          type="button"
          disabled={disabled || loading || approved}
          onClick={approve}
          className={`rounded-md px-5 py-3 text-sm font-bold text-white ${
            approved
              ? 'bg-emerald-700'
              : disabled
                ? 'cursor-not-allowed bg-slate-300'
                : 'bg-emerald-600 hover:bg-emerald-700'
          }`}
        >
          {approved
            ? 'Note Approved and Saved ✓'
            : loading
              ? 'Approving...'
              : disabled
                ? 'Enter lab values above before approving'
                : 'Approve and Save Note'}
        </button>
      </div>
    </div>
  )
}

