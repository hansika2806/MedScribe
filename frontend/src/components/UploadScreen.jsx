import { useRef, useState } from 'react'

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.webm']

function isAccepted(file) {
  const name = file?.name?.toLowerCase() || ''
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export default function UploadScreen({ onSubmit }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedPdf, setSelectedPdf] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)
  const pdfInputRef = useRef(null)

  const chooseFile = (file) => {
    if (!file) return
    if (!isAccepted(file)) {
      setError('Please upload a WAV, MP3, M4A, or WEBM audio file.')
      setSelectedFile(null)
      return
    }
    setError('')
    setSelectedFile(file)
  }

  const choosePdf = (file) => {
    if (!file) return
    if (!file.name?.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF test report.')
      setSelectedPdf(null)
      return
    }
    setError('')
    setSelectedPdf(file)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    chooseFile(event.dataTransfer.files?.[0])
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <section className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-600 text-xl font-semibold text-white">
            M
          </div>
          <h1 className="text-2xl font-semibold text-slate-950">MedScribe</h1>
          <p className="mt-2 text-sm text-slate-600">Upload consultation audio for physician review.</p>
        </div>

        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`flex min-h-52 flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
            dragging ? 'border-emerald-500 bg-emerald-50' : 'border-slate-300 bg-slate-50'
          }`}
        >
          <div className="text-4xl text-slate-500">↑</div>
          <p className="mt-4 text-base font-medium text-slate-900">Drag and drop audio here</p>
          <p className="mt-1 text-sm text-slate-500">WAV, MP3, M4A, or WEBM</p>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="mt-5 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            Browse files
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".wav,.mp3,.m4a,.webm,audio/*"
            className="hidden"
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
        </div>

        {selectedFile && (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            Selected: <span className="font-medium">{selectedFile.name}</span>
          </div>
        )}

        <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-5">
          <div>
            <label className="text-sm font-semibold text-slate-950">Test Report PDF (optional)</label>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Upload lab report, blood work, or any test report PDF. Values will be automatically extracted and included in the SOAP note.
            </p>
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={() => pdfInputRef.current?.click()}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
            >
              Choose PDF
            </button>
            {selectedPdf && (
              <button
                type="button"
                onClick={() => setSelectedPdf(null)}
                className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100"
              >
                Remove
              </button>
            )}
          </div>
          <input
            ref={pdfInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(event) => choosePdf(event.target.files?.[0])}
          />
          {selectedPdf && (
            <div className="mt-4 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
              Selected: <span className="font-medium">{selectedPdf.name}</span>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          type="button"
          disabled={!selectedFile}
          onClick={() => selectedFile && onSubmit(selectedFile, selectedPdf)}
          className="mt-6 w-full rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Start Consultation
        </button>
      </section>
    </main>
  )
}
