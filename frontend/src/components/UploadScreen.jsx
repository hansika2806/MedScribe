import { useEffect, useRef, useState } from 'react'
import { healthCheck } from '../api/client'

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.webm']
const DEFAULT_PATIENT_CONTEXT = {
  age: '',
  gender: '',
  allergies: '',
  current_meds: '',
  chief_complaint: ''
}

const BrowserAudioContext = window.AudioContext || window.webkitAudioContext

function isAccepted(file) {
  const name = file?.name?.toLowerCase() || ''
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

function formatSize(bytes) {
  if (!bytes) return '0 MB'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatRecordingTime(seconds) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`
}

function processingEstimate(bytes) {
  const mb = bytes / (1024 * 1024)
  if (mb < 2) return '~35-45 seconds'
  if (mb <= 5) return '~45-70 seconds'
  return '~70-120 seconds'
}

function recorderMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return types.find((type) => window.MediaRecorder?.isTypeSupported(type)) || ''
}

export default function UploadScreen({ onSubmit }) {
  const [activeTab, setActiveTab] = useState('upload')
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedPdf, setSelectedPdf] = useState(null)
  const [patientContext, setPatientContext] = useState(() => ({ ...DEFAULT_PATIENT_CONTEXT }))
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [serverUnavailable, setServerUnavailable] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [recording, setRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [audioUrl, setAudioUrl] = useState('')

  const fileInputRef = useRef(null)
  const pdfInputRef = useRef(null)
  const canvasRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)
  const audioContextRef = useRef(null)
  const animationRef = useRef(null)

  useEffect(() => {
    let mounted = true
    healthCheck().then((result) => {
      if (mounted) setServerUnavailable(!result.ok)
    })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    if (!recording) return undefined
    const timer = window.setInterval(() => setRecordingSeconds((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [recording])

  useEffect(() => {
    return () => {
      stopStream()
      if (audioUrl) window.URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  const updatePatientContext = (key, value) => {
    setPatientContext((current) => ({ ...current, [key]: value }))
  }

  const chooseFile = (file) => {
    if (!file || submitting || recording) return
    if (!isAccepted(file)) {
      setError('Please upload a WAV, MP3, M4A, or WEBM audio file.')
      setSelectedFile(null)
      return
    }
    setError('')
    if (audioUrl) {
      window.URL.revokeObjectURL(audioUrl)
      setAudioUrl('')
    }
    setSelectedFile(file)
  }

  const choosePdf = (file) => {
    if (!file || submitting) return
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

  function stopStream() {
    if (animationRef.current) {
      window.cancelAnimationFrame(animationRef.current)
      animationRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {})
      audioContextRef.current = null
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  function drawWaveform(analyser) {
    const canvas = canvasRef.current
    if (!canvas) return

    const context = canvas.getContext('2d')
    const data = new Uint8Array(analyser.fftSize)

    const draw = () => {
      analyser.getByteTimeDomainData(data)
      context.clearRect(0, 0, canvas.width, canvas.height)
      context.fillStyle = '#f8fafc'
      context.fillRect(0, 0, canvas.width, canvas.height)
      context.lineWidth = 2
      context.strokeStyle = '#059669'
      context.beginPath()

      const sliceWidth = canvas.width / data.length
      let x = 0
      data.forEach((value, index) => {
        const y = (value / 128) * (canvas.height / 2)
        if (index === 0) context.moveTo(x, y)
        else context.lineTo(x, y)
        x += sliceWidth
      })

      context.lineTo(canvas.width, canvas.height / 2)
      context.stroke()
      animationRef.current = window.requestAnimationFrame(draw)
    }

    draw()
  }

  const startRecording = async () => {
    if (submitting || recording) return
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !BrowserAudioContext) {
      setError('This browser does not support in-browser audio recording.')
      return
    }
    if (!validateContext()) return

    try {
      if (audioUrl) {
        window.URL.revokeObjectURL(audioUrl)
        setAudioUrl('')
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = recorderMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      const audioContext = new BrowserAudioContext()
      const source = audioContext.createMediaStreamSource(stream)
      const analyser = audioContext.createAnalyser()

      analyser.fftSize = 1024
      source.connect(analyser)

      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blobType = mimeType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type: blobType })
        const extension = blobType.includes('mp4') ? 'm4a' : blobType.includes('ogg') ? 'ogg' : 'webm'
        const file = new File([blob], `consultation-recording-${Date.now()}.${extension}`, { type: blobType })

        setAudioUrl(window.URL.createObjectURL(blob))
        setSelectedFile(file)
        chunksRef.current = []
        recorderRef.current = null
        stopStream()
      }

      streamRef.current = stream
      recorderRef.current = recorder
      audioContextRef.current = audioContext
      setSelectedFile(null)
      setRecordingSeconds(0)
      setError('')
      setRecording(true)
      drawWaveform(analyser)
      recorder.start(1000)
    } catch (recordingError) {
      stopStream()
      setRecording(false)
      setError(
        recordingError?.name === 'NotAllowedError'
          ? 'Microphone permission was denied.'
          : 'Could not start microphone recording.'
      )
    }
  }

  const stopRecording = () => {
    if (!recording || !recorderRef.current) return
    setRecording(false)
    if (recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
  }

  const validateContext = () => {
    if (!patientContext.age.trim() || !patientContext.gender.trim() || !patientContext.chief_complaint.trim()) {
      setError('Enter age, gender, and chief complaint before starting.')
      return false
    }
    return true
  }

  const handleSubmit = async () => {
    if (!selectedFile || submitting || recording || !validateContext()) return
    setSubmitting(true)
    try {
      await onSubmit(selectedFile, selectedPdf, patientContext)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-[calc(100vh-65px)] bg-slate-50 px-4 py-8">
      <section className="mx-auto w-full max-w-3xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-7 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-600 text-xl font-semibold text-white">
            M
          </div>
          <h1 className="text-2xl font-semibold text-slate-950">MedScribe</h1>
          <p className="mt-2 text-sm text-slate-600">Capture consultation audio for physician review.</p>
        </div>

        {serverUnavailable && (
          <div className="mb-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
            Cannot connect to MedScribe server. Please ensure the backend is running.
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-5">
          <h2 className="text-sm font-semibold uppercase text-slate-500">Patient context</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-800">
              Age
              <input
                type="number"
                min="0"
                max="120"
                value={patientContext.age}
                onChange={(event) => updatePatientContext('age', event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="text-sm font-medium text-slate-800">
              Gender
              <select
                value={patientContext.gender}
                onChange={(event) => updatePatientContext('gender', event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
              >
                <option value="">Select</option>
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Not specified">Not specified</option>
              </select>
            </label>
            <label className="text-sm font-medium text-slate-800">
              Allergies
              <input
                type="text"
                value={patientContext.allergies}
                onChange={(event) => updatePatientContext('allergies', event.target.value)}
                placeholder="None known"
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="text-sm font-medium text-slate-800">
              Current meds
              <input
                type="text"
                value={patientContext.current_meds}
                onChange={(event) => updatePatientContext('current_meds', event.target.value)}
                placeholder="None reported"
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <label className="text-sm font-medium text-slate-800 sm:col-span-2">
              Chief complaint
              <textarea
                value={patientContext.chief_complaint}
                onChange={(event) => updatePatientContext('chief_complaint', event.target.value)}
                rows={3}
                className="mt-1 w-full resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
              />
            </label>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 rounded-lg border border-slate-200 bg-slate-100 p-1">
          {[
            ['upload', 'Upload audio'],
            ['record', 'Record live']
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                if (!recording) setActiveTab(key)
              }}
              disabled={recording && key !== activeTab}
              className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
                activeTab === key
                  ? 'bg-white text-slate-950 shadow-sm'
                  : 'text-slate-600 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'upload' ? (
          <div
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`mt-5 flex min-h-52 flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
              dragging ? 'border-emerald-500 bg-emerald-50' : 'border-slate-300 bg-slate-50'
            }`}
          >
            <div className="text-sm font-semibold uppercase text-slate-400">Audio</div>
            <p className="mt-3 text-base font-medium text-slate-900">Drag and drop audio here</p>
            <p className="mt-1 text-sm text-slate-500">WAV, MP3, M4A, or WEBM</p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={submitting}
              className="mt-5 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
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
        ) : (
          <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-semibold uppercase text-slate-400">Microphone</div>
                <div className="mt-1 font-mono text-2xl font-semibold text-slate-950">
                  {formatRecordingTime(recordingSeconds)}
                </div>
              </div>
              <div className="flex gap-3">
                {!recording ? (
                  <button
                    type="button"
                    onClick={startRecording}
                    disabled={submitting}
                    className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    Record
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
                  >
                    Stop
                  </button>
                )}
              </div>
            </div>
            <canvas
              ref={canvasRef}
              width="680"
              height="120"
              className="mt-4 h-28 w-full rounded-md border border-slate-200 bg-white"
            />
            {audioUrl && (
              <audio controls src={audioUrl} className="mt-4 w-full">
                <track kind="captions" />
              </audio>
            )}
          </div>
        )}

        {selectedFile && (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <div>
              Audio file: <span className="font-medium">{selectedFile.name}</span> ({formatSize(selectedFile.size)})
            </div>
            <div className="mt-1">Estimated processing time: {processingEstimate(selectedFile.size)}</div>
          </div>
        )}

        <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-5">
          <div>
            <label className="text-sm font-semibold text-slate-950">Test Report PDF (optional)</label>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Upload lab report, blood work, or any test report PDF. Values will be extracted and included in the SOAP note.
            </p>
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={() => pdfInputRef.current?.click()}
              disabled={submitting}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Choose PDF
            </button>
            {selectedPdf && (
              <button
                type="button"
                onClick={() => setSelectedPdf(null)}
                disabled={submitting}
                className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
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
              PDF file: <span className="font-medium">{selectedPdf.name}</span> ({formatSize(selectedPdf.size)})
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
          disabled={!selectedFile || submitting || recording}
          onClick={handleSubmit}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
          {submitting ? 'Starting Consultation...' : 'Start Consultation'}
        </button>
      </section>
    </main>
  )
}
