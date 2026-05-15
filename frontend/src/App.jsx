import { useCallback, useEffect, useState } from 'react'
import { retryConsultation, submitConsultation } from './api/client'
import ErrorScreen from './components/ErrorScreen'
import ProcessingScreen from './components/ProcessingScreen'
import SOAPReview from './components/SOAPReview'
import UploadScreen from './components/UploadScreen'

const SESSION_KEY = 'medscribe_session'
const SCREEN_KEY = 'medscribe_screen'
const TWO_HOURS = 2 * 60 * 60 * 1000

function createSessionId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID()
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function saveSession(screen, response) {
  sessionStorage.setItem(SCREEN_KEY, screen)
  if (response) {
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({
        session_id: response.session_id,
        response_data: response,
        saved_at: Date.now()
      })
    )
  }
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY)
  sessionStorage.removeItem(SCREEN_KEY)
}

export default function App() {
  const [screen, setScreen] = useState('upload')
  const [responseData, setResponseData] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [error, setError] = useState(null)
  const [lastFile, setLastFile] = useState(null)
  const [lastPdfFile, setLastPdfFile] = useState(null)

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY)
    if (!stored) return

    try {
      const parsed = JSON.parse(stored)
      const fresh = Date.now() - parsed.saved_at < TWO_HOURS
      if (!fresh) {
        clearSession()
        return
      }

      setSessionId(parsed.session_id)
      setResponseData(parsed.response_data)

      if (parsed.response_data?.status === 'completed') {
        setScreen('review')
        sessionStorage.setItem(SCREEN_KEY, 'review')
      } else if (parsed.response_data?.status === 'failed') {
        setError({ message: parsed.response_data?.error_message || 'Processing failed.' })
        setScreen('error')
        sessionStorage.setItem(SCREEN_KEY, 'error')
      }
    } catch {
      clearSession()
    }
  }, [])

  const startProcessing = useCallback(async (file, pdfFile = null) => {
    const nextSessionId = createSessionId()
    setLastFile(file)
    setLastPdfFile(pdfFile)
    setSessionId(nextSessionId)
    setError(null)
    setScreen('processing')
    sessionStorage.setItem(SCREEN_KEY, 'processing')

    const result = await submitConsultation(file, pdfFile, nextSessionId)
    if (!result.ok) {
      setError(result)
      setScreen('error')
      sessionStorage.setItem(SCREEN_KEY, 'error')
      return
    }

    setResponseData(result.data)
    setScreen('review')
    saveSession('review', result.data)
  }, [])

  const handleFailed = useCallback((failure) => {
    setError({ message: failure.message || 'Processing failed.' })
    setScreen('error')
    sessionStorage.setItem(SCREEN_KEY, 'error')
  }, [])

  const handleRetry = async () => {
    if (sessionId) {
      await retryConsultation(sessionId)
    }
    if (lastFile) {
      startProcessing(lastFile, lastPdfFile)
      return
    }
    setScreen('upload')
  }

  const handleUploadNew = () => {
    clearSession()
    setResponseData(null)
    setSessionId(null)
    setError(null)
    setLastFile(null)
    setLastPdfFile(null)
    setScreen('upload')
  }

  const handleSessionUpdate = (updated) => {
    setResponseData(updated)
    saveSession('review', updated)
  }

  if (screen === 'processing') {
    return <ProcessingScreen sessionId={sessionId} onFailed={handleFailed} />
  }

  if (screen === 'error') {
    return (
      <ErrorScreen
        error={error}
        sessionId={sessionId}
        onRetry={handleRetry}
        onUploadNew={handleUploadNew}
      />
    )
  }

  if (screen === 'review' && responseData) {
    return (
      <SOAPReview
        responseData={responseData}
        onNewConsultation={handleUploadNew}
        onSessionUpdate={handleSessionUpdate}
      />
    )
  }

  return <UploadScreen onSubmit={startProcessing} />
}
