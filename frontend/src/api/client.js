import axios from 'axios'
import { getToken, logout } from './auth.js'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://medscribe-production-39ab.up.railway.app'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1200000
})

const getHeaders = () => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function normalizeError(error) {
  const rawDetail = error?.response?.data?.detail || error?.message || ''
  const structured = typeof rawDetail === 'object' && rawDetail !== null ? rawDetail : {}
  const detail = structured.detail || rawDetail
  const status = error?.response?.status || 0
  const errorCode = structured.error_code || null
  let message = structured.message || 'An error occurred during processing. Please try again.'

  if (errorCode === 'AUTH_EXPIRED' || status === 401 || /401|Unauthorized|Invalid or expired token/i.test(detail)) {
    message = 'Your session has expired. Please log in again.'
    logout()
  } else if (errorCode === 'GROQ_RATE_LIMIT' || status === 429 || /Rate limit reached|429/i.test(detail)) {
    message = 'AI service is temporarily busy. Please wait a few minutes and try again.'
  } else if (errorCode === 'NO_CLINICAL_CONTENT' || /No extracted entities|No clinical data|extract/i.test(detail)) {
    message = 'Could not extract clinical information from the audio. Please check audio quality and ensure the consultation was clearly recorded.'
  } else if (!structured.message && (status === 500 || /Groq API error|Groq|AI|LLM|API/i.test(detail))) {
    message = 'Processing service temporarily unavailable. Please try again in a moment.'
  } else if (/Network Error/i.test(detail) || !error?.response) {
    message = 'Cannot connect to MedScribe server. Please check your connection.'
  } else if (/timeout/i.test(detail)) {
    message = 'Processing took too long. Please try again with a shorter or clearer recording.'
  }

  return {
    ok: false,
    status,
    error_code: errorCode,
    retryable: structured.retryable ?? true,
    session_id: structured.session_id,
    detail,
    message
  }
}

export async function healthCheck() {
  try {
    const response = await api.get('/health', { timeout: 5000 })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function submitConsultation(audioFile, pdfFile = null, sessionId = null, patientContext = {}) {
  try {
    const formData = new FormData()
    formData.append('audio_file', audioFile)
    if (pdfFile) {
      formData.append('pdf_file', pdfFile)
    }
    if (sessionId) {
      formData.append('session_id', sessionId)
    }
    const cleanedContext = Object.fromEntries(
      Object.entries(patientContext || {}).filter(([, value]) => String(value || '').trim())
    )
    if (Object.keys(cleanedContext).length > 0) {
      formData.append('patient_context', JSON.stringify(cleanedContext))
    }
    const response = await api.post('/consultation', formData, {
      headers: getHeaders()
    })

    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function getConsultation(sessionId) {
  try {
    const response = await api.get(`/consultation/${sessionId}`, { headers: getHeaders() })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function getStatus(sessionId) {
  try {
    const response = await api.get(`/consultation/${sessionId}/status`, { headers: getHeaders() })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function updateLabValues(sessionId, labValues) {
  try {
    const response = await api.post(`/consultation/${sessionId}/labs`, {
      lab_values: labValues
    }, { headers: getHeaders() })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function approveConsultation(sessionId, note = '') {
  try {
    const response = await api.post(`/consultation/${sessionId}/approve`, {
      physician_note: note
    }, { headers: getHeaders() })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function retryConsultation(sessionId) {
  try {
    const response = await api.post(`/consultation/${sessionId}/retry`, {}, { headers: getHeaders() })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}
