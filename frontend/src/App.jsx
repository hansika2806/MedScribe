import { useCallback, useEffect, useRef, useState } from 'react'
import { getPhysician, isLoggedIn, logout } from './api/auth'
import { getConsultation, retryConsultation, submitConsultation } from './api/client'
import ApprovalSuccessScreen from './components/ApprovalSuccessScreen'
import ErrorScreen from './components/ErrorScreen'
import LoginScreen from './components/LoginScreen'
import NavBar from './components/NavBar'
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
  const [screen, setScreen] = useState(() => (isLoggedIn() ? 'upload' : 'login'))
  const [responseData, setResponseData] = useState(null)
  const [approvalData, setApprovalData] = useState(null)
  const [physician, setPhysician] = useState(() => getPhysician())
  const [sessionId, setSessionId] = useState(null)
  const [error, setError] = useState(null)
  const [lastFile, setLastFile] = useState(null)
  const [lastPdfFile, setLastPdfFile] = useState(null)
  const [lastPatientContext, setLastPatientContext] = useState({})
  const completedSessions = useRef(new Set())

  useEffect(() => {
    if (!isLoggedIn()) {
      setScreen('login')
      return
    }
    setPhysician(getPhysician())
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
        const storedScreen = sessionStorage.getItem(SCREEN_KEY)
        const nextScreen = storedScreen === 'success' && parsed.response_data?.approved ? 'success' : 'review'
        setScreen(nextScreen)
        sessionStorage.setItem(SCREEN_KEY, nextScreen)
      } else if (parsed.response_data?.status === 'failed') {
        setError({ message: parsed.response_data?.error_message || 'Processing failed.' })
        setScreen('error')
        sessionStorage.setItem(SCREEN_KEY, 'error')
      }
    } catch {
      clearSession()
    }
  }, [])

  useEffect(() => {
    const handleLogout = () => {
      clearSession()
      setResponseData(null)
      setApprovalData(null)
      setPhysician(null)
      setScreen('login')
    }
    window.addEventListener('medscribe_logout', handleLogout)
    return () => window.removeEventListener('medscribe_logout', handleLogout)
  }, [])

  const handleLogin = (nextPhysician) => {
    setPhysician(nextPhysician)
    setScreen('upload')
  }

  const handleLogout = () => {
    logout()
  }

  const startProcessing = useCallback(async (file, pdfFile = null, patientContext = {}) => {
    const nextSessionId = createSessionId()
    setLastFile(file)
    setLastPdfFile(pdfFile)
    setLastPatientContext(patientContext)
    setSessionId(nextSessionId)
    setError(null)
    setScreen('processing')
    sessionStorage.setItem(SCREEN_KEY, 'processing')

    const result = await submitConsultation(file, pdfFile, nextSessionId, patientContext)
    if (!result.ok) {
      if (completedSessions.current.has(nextSessionId)) return
      setError(result)
      setScreen('error')
      sessionStorage.setItem(SCREEN_KEY, 'error')
      return
    }

    setResponseData(result.data)
    setScreen('review')
    saveSession('review', result.data)
  }, [])

  const handleCompleted = useCallback(async (completedSessionId) => {
    completedSessions.current.add(completedSessionId)
    const result = await getConsultation(completedSessionId)
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
      startProcessing(lastFile, lastPdfFile, lastPatientContext)
      return
    }
    setScreen('upload')
  }

  const handleUploadNew = () => {
    clearSession()
    setResponseData(null)
    setApprovalData(null)
    setSessionId(null)
    setError(null)
    setLastFile(null)
    setLastPdfFile(null)
    setLastPatientContext({})
    setScreen('upload')
  }

  const handleSessionUpdate = (updated) => {
    setResponseData(updated)
    saveSession('review', updated)
  }

  const handleApproved = (approval) => {
    const updated = {
      ...responseData,
      approved: true,
      approved_at: approval.approved_at
    }
    setApprovalData(approval)
    setResponseData(updated)
    saveSession('success', updated)
    setScreen('success')
  }

  const viewApprovedNote = () => {
    setScreen('review')
  }

  if (screen === 'login') {
    return <LoginScreen onLogin={handleLogin} />
  }

  const withNav = (content) => (
    <>
      <NavBar physician={physician} onLogout={handleLogout} />
      {content}
    </>
  )

  if (screen === 'processing') {
    return withNav(
      <ProcessingScreen
        sessionId={sessionId}
        onCompleted={handleCompleted}
        onFailed={handleFailed}
        onCancel={handleUploadNew}
      />
    )
  }

  if (screen === 'error') {
    return (
      withNav(<ErrorScreen
        error={error}
        sessionId={sessionId}
        onRetry={handleRetry}
        onUploadNew={handleUploadNew}
      />)
    )
  }

  if (screen === 'success' && responseData) {
    return withNav(
      <ApprovalSuccessScreen
        responseData={responseData}
        approval={approvalData}
        physician={physician}
        onStartNew={handleUploadNew}
        onViewNote={viewApprovedNote}
      />
    )
  }

  if (screen === 'review' && responseData) {
    return withNav(
      <SOAPReview
        responseData={responseData}
        onNewConsultation={handleUploadNew}
        onSessionUpdate={handleSessionUpdate}
        onApproved={handleApproved}
        physician={physician}
      />
    )
  }

  return withNav(<UploadScreen onSubmit={startProcessing} physician={physician} />)
}
