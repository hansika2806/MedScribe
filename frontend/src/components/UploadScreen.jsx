import { useRef, useState } from 'react'

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.webm']

function isAccepted(file) {
  const name = file?.name?.toLowerCase() || ''
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export default function UploadScreen({ onSubmit }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

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

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          type="button"
          disabled={!selectedFile}
          onClick={() => selectedFile && onSubmit(selectedFile)}
          className="mt-6 w-full rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Start Consultation
        </button>
      </section>
    </main>
  )
}

