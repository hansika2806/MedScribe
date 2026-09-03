import { useEffect, useMemo, useRef, useState } from 'react'
import { getStatus } from '../api/client'

const stages = [
  { label: 'Uploading audio', duration: 3 },
  { label: 'Transcribing speech', duration: 9 },
  { label: 'Identifying speakers', duration: 4 },
  { label: 'Filtering clinical content', duration: 4 },
  { label: 'Extracting clinical entities', duration: 6 },
  { label: 'Generating SOAP note', duration: 10 },
  { label: 'Coding and quality checks', duration: 5 },
  { label: 'Safety review', duration: 4 },
  { label: 'Ready for physician review', duration: 0 }
]

const STAGE_STARTS = stages.reduce((acc, _, index) => {
  acc.push(index === 0 ? 0 : acc[index - 1] + stages[index - 1].duration)
  return acc
}, [])
const TOTAL_ESTIMATED = STAGE_STARTS[STAGE_STARTS.length - 1]

function stageIndexForElapsed(elapsed, completed) {
  if (completed) return stages.length - 1
  for (let index = STAGE_STARTS.length - 1; index >= 0; index -= 1) {
    if (elapsed >= STAGE_STARTS[index]) return Math.min(index, stages.length - 2)
  }
  return 0
}

function formatTime(seconds) {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${String(remainingSeconds).padStart(2, '0')}s`
}

export default function ProcessingScreen({ sessionId, onCompleted, onFailed, onCancel }) {
  const [elapsed, setElapsed] = useState(0)
  const [status, setStatus] = useState('processing')
  const [lastServerUpdate, setLastServerUpdate] = useState(null)
  const startedAt = useRef(Date.now())
  const handledTerminalStatus = useRef(false)

  useEffect(() => {
    const updateElapsed = () => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 1000))
    }
    updateElapsed()
    const timer = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!sessionId) return undefined

    const pollStatus = async () => {
      const result = await getStatus(sessionId)
      if (!result.ok) return

      setStatus(result.data.status)
      setLastServerUpdate(new Date())

      if (handledTerminalStatus.current) return
      if (result.data.status === 'completed') {
        handledTerminalStatus.current = true
        onCompleted(sessionId)
      } else if (result.data.status === 'failed') {
        handledTerminalStatus.current = true
        onFailed({
          session_id: sessionId,
          message: result.data.error_message || 'Processing failed.'
        })
      }
    }

    pollStatus()
    const poll = window.setInterval(pollStatus, 2000)
    return () => window.clearInterval(poll)
  }, [sessionId, onCompleted, onFailed])

  const isCompleted = status === 'completed'
  const currentIndex = useMemo(
    () => stageIndexForElapsed(elapsed, isCompleted),
    [elapsed, isCompleted]
  )
  const progress = isCompleted
    ? 100
    : Math.min(98, Math.round((elapsed / TOTAL_ESTIMATED) * 100))
  const remaining = Math.max(0, TOTAL_ESTIMATED - elapsed)
  const waitingOnServer = elapsed > TOTAL_ESTIMATED && !isCompleted

  return (
    <main className="min-h-[calc(100vh-65px)] bg-slate-50 px-4 py-8">
      <section className="mx-auto max-w-2xl">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-emerald-600 text-2xl font-bold text-white shadow">
            M
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Processing consultation</h1>
          <p className="mt-1 text-sm text-slate-500">
            Most clear recordings finish in about 45 seconds; completion is confirmed by the server.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 grid grid-cols-2 gap-4">
            <div className="rounded-md bg-slate-50 px-4 py-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Elapsed</div>
              <div className="mt-1 font-mono text-2xl font-bold text-slate-900">{formatTime(elapsed)}</div>
            </div>
            <div className="rounded-md bg-slate-50 px-4 py-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estimate</div>
              <div className="mt-1 font-mono text-2xl font-bold text-slate-900">
                {isCompleted ? 'Done' : waitingOnServer ? 'Finalizing' : `~${formatTime(remaining)}`}
              </div>
            </div>
          </div>

          <div className="mb-1 flex justify-between gap-3 text-xs font-medium text-slate-500">
            <span>{progress}% estimated</span>
            <span className="max-w-[50%] truncate text-right">{stages[currentIndex]?.label}</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-700 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="mt-4 flex flex-col gap-1 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Session: <span className="font-mono">{sessionId || 'Creating...'}</span>
            </span>
            <span>
              Server status: {status}
              {lastServerUpdate ? `, checked ${lastServerUpdate.toLocaleTimeString()}` : ''}
            </span>
          </div>
        </div>

        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          {stages.map((stage, index) => {
            const done = index < currentIndex || isCompleted
            const active = index === currentIndex && !isCompleted
            return (
              <div
                key={stage.label}
                className={`flex items-center gap-3 border-b border-slate-100 px-5 py-3.5 transition-colors duration-300 last:border-b-0 ${
                  done ? 'bg-emerald-50' : active ? 'bg-blue-50' : ''
                }`}
              >
                <div
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    done
                      ? 'bg-emerald-500 text-white'
                      : active
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-200 text-slate-400'
                  }`}
                >
                  {done ? (
                    'OK'
                  ) : active ? (
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    '-'
                  )}
                </div>

                <span className={`text-sm font-medium ${done ? 'text-emerald-800' : active ? 'text-blue-900' : 'text-slate-400'}`}>
                  {stage.label}
                </span>

                <span className="ml-auto text-xs">
                  {done && <span className="text-emerald-600">done</span>}
                  {active && <span className="animate-pulse text-blue-500">in progress</span>}
                  {!done && !active && stage.duration > 0 && (
                    <span className="text-slate-300">~{stage.duration}s</span>
                  )}
                </span>
              </div>
            )
          })}
        </div>

        {elapsed > 75 && !isCompleted && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span className="font-semibold">Still processing.</span> Longer audio, model warm-up, or OCR can push this past the usual estimate.
          </div>
        )}

        {elapsed > 180 && !isCompleted && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-4">
            <p className="text-sm font-semibold text-red-900">This is taking unexpectedly long.</p>
            <button
              type="button"
              onClick={onCancel}
              className="mt-3 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
            >
              Cancel and Try Again
            </button>
          </div>
        )}
      </section>
    </main>
  )
}
