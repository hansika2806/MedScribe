import { useEffect, useMemo, useState } from 'react'
import { logout } from '../api/auth'

function messageFor(error) {
  return error?.message || 'An error occurred during processing. Please try again.'
}

export default function ErrorScreen({ error, sessionId, onRetry, onUploadNew }) {
  const errorCode = error?.error_code || 'UNKNOWN_ERROR'
  const message = messageFor(error)
  const [waitSeconds, setWaitSeconds] = useState(errorCode === 'GROQ_RATE_LIMIT' ? 180 : 0)

  useEffect(() => {
    if (errorCode === 'AUTH_EXPIRED') {
      const timer = window.setTimeout(() => logout(), 1200)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [errorCode])

  useEffect(() => {
    if (errorCode !== 'GROQ_RATE_LIMIT' || waitSeconds <= 0) return undefined
    const timer = window.setInterval(() => {
      setWaitSeconds((value) => Math.max(0, value - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [errorCode, waitSeconds])

  const minutes = useMemo(() => Math.ceil(waitSeconds / 60), [waitSeconds])

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-lg rounded-lg border border-red-200 bg-white p-8 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-2xl text-red-700">
          !
        </div>
        <h1 className="mt-5 text-2xl font-semibold text-slate-950">Processing Failed</h1>
        <p className="mt-3 text-sm leading-6 text-slate-700">{message}</p>

        {errorCode === 'GROQ_RATE_LIMIT' && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Please wait {minutes} minute{minutes === 1 ? '' : 's'} before retrying.
          </div>
        )}

        {errorCode === 'NO_CLINICAL_CONTENT' && (
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
            <div className="font-semibold">Tips for better results:</div>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>Speak clearly and close to microphone</li>
              <li>Ensure minimal background noise</li>
              <li>Audio should be at least 30 seconds long</li>
            </ul>
          </div>
        )}

        {sessionId && (
          <p className="mt-4 rounded-md bg-slate-100 px-3 py-2 font-mono text-xs text-slate-700">
            Session: {sessionId}
          </p>
        )}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          {errorCode === 'AUTH_EXPIRED' ? (
            <button
              type="button"
              onClick={logout}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
            >
              Log In Again
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={onRetry}
                disabled={errorCode === 'GROQ_RATE_LIMIT' && waitSeconds > 0}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {errorCode === 'GROQ_RATE_LIMIT' ? 'Retry' : 'Try Again'}
              </button>
              <button
                type="button"
                onClick={onUploadNew}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
              >
                Upload New File
              </button>
            </>
          )}
        </div>
      </section>
    </main>
  )
}
