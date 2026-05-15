import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000
})

function normalizeError(error) {
  const detail = error?.response?.data?.detail || error?.message || ''
  let message = 'An error occurred during processing. Please try again.'

  if (/No clinical data|No extracted entities|extract/i.test(detail)) {
    message = 'Could not extract clinical information from the audio. Please try again or check audio quality.'
  } else if (/Groq|AI|LLM|API/i.test(detail)) {
    message = 'AI service temporarily unavailable. Please try again in a moment.'
  } else if (/timeout/i.test(detail)) {
    message = 'Processing took too long. Please try again with a shorter or clearer recording.'
  }

  return {
    ok: false,
    status: error?.response?.status || 0,
    detail,
    message
  }
}

export async function submitConsultation(audioFile, pdfFile = null, sessionId = null) {
  try {
    const formData = new FormData()
    formData.append('audio_file', audioFile)
    if (pdfFile) {
      formData.append('pdf_file', pdfFile)
    }
    if (sessionId) {
      formData.append('session_id', sessionId)
    }
    const response = await api.post('/consultation', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function getConsultation(sessionId) {
  try {
    const response = await api.get(`/consultation/${sessionId}`)
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function getStatus(sessionId) {
  try {
    const response = await api.get(`/consultation/${sessionId}/status`)
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function updateLabValues(sessionId, labValues) {
  try {
    const response = await api.post(`/consultation/${sessionId}/labs`, {
      lab_values: labValues
    })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function approveConsultation(sessionId, note = '') {
  try {
    const response = await api.post(`/consultation/${sessionId}/approve`, {
      physician_note: note
    })
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}

export async function retryConsultation(sessionId) {
  try {
    const response = await api.post(`/consultation/${sessionId}/retry`)
    return { ok: true, data: response.data }
  } catch (error) {
    return normalizeError(error)
  }
}
