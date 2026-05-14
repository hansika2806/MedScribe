import { useEffect, useMemo, useState } from 'react'
import { getStatus } from '../api/client'

const stages = [
  'Uploading audio',
  'Transcribing speech',
  'Identifying speakers',
  'Filtering clinical content',
  'Extracting clinical entities',
  'Retrieving guidelines',
  'Generating SOAP note',
  'Mapping ICD-10 codes',
  'Checking quality',
  'Checking safety',
  'Ready for physician review'
]

function simulatedStageIndex(elapsed, completed) {
  if (completed) return stages.length - 1
  if (elapsed < 10) return 0
  if (elapsed < 20) return 1
  if (elapsed < 27) return 2
  if (elapsed < 34) return 3
  if (elapsed < 40) return 4
  if (elapsed < 47) return 5
  if (elapsed < 54) return 6
  if (elapsed < 60) return 7
  if (elapsed < 70) return 8
  return 9
}

export default function ProcessingScreen({ sessionId, onFailed }) {
  const [elapsed, setElapsed] = useState(0)
  const [status, setStatus] = useState('processing')

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!sessionId) return undefined
    const poll = window.setInterval(async () => {
      const result = await getStatus(sessionId)
      if (!result.ok) return
      setStatus(result.data.status)
      if (result.data.status === 'failed') {
        onFailed({
          session_id: sessionId,
          message: result.data.error_message || 'Processing failed.'
        })
      }
    }, 3000)
    return () => window.clearInterval(poll)
  }, [sessionId, onFailed])

  const currentIndex = useMemo(
    () => simulatedStageIndex(elapsed, status === 'completed'),
    [elapsed, status]
  )

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <section className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">Processing consultation</h1>
            <p className="mt-2 text-sm text-slate-600">This typically takes 60-90 seconds.</p>
          </div>
          <div className="text-sm text-slate-500">
            <div>Session ID</div>
            <div className="font-mono text-xs text-slate-800">{sessionId || 'Creating session...'}</div>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between rounded-md bg-slate-100 px-4 py-3">
          <span className="text-sm font-medium text-slate-800">Elapsed time</span>
          <span className="font-mono text-sm text-slate-900">{elapsed}s</span>
        </div>

        <ol className="mt-6 space-y-3">
          {stages.map((stage, index) => {
            const completed = index < currentIndex
            const active = index === currentIndex
            return (
              <li
                key={stage}
                className={`flex items-center gap-3 rounded-md border px-4 py-3 ${
                  completed
                    ? 'border-emerald-200 bg-emerald-50'
                    : active
                      ? 'border-blue-200 bg-blue-50'
                      : 'border-slate-200 bg-white'
                }`}
              >
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    completed
                      ? 'bg-emerald-600 text-white'
                      : active
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {completed ? '✓' : active ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" /> : index + 1}
                </div>
                <span className={`text-sm ${active ? 'font-semibold text-blue-950' : 'text-slate-700'}`}>
                  {stage}
                </span>
              </li>
            )
          })}
        </ol>
      </section>
    </main>
  )
}

