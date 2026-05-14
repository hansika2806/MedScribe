export default function ErrorScreen({ error, sessionId, onRetry, onUploadNew }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-lg rounded-lg border border-red-200 bg-white p-8 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-2xl text-red-700">
          !
        </div>
        <h1 className="mt-5 text-2xl font-semibold text-slate-950">Processing Failed</h1>
        <p className="mt-3 text-sm leading-6 text-slate-700">
          {error?.message || 'An error occurred during processing. Please try again.'}
        </p>
        {sessionId && (
          <p className="mt-4 rounded-md bg-slate-100 px-3 py-2 font-mono text-xs text-slate-700">
            Session: {sessionId}
          </p>
        )}
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
          >
            Try Again
          </button>
          <button
            type="button"
            onClick={onUploadNew}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          >
            Upload New File
          </button>
        </div>
      </section>
    </main>
  )
}

