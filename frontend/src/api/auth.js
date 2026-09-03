import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
const TOKEN_KEY = 'medscribe_token'
const PHYSICIAN_KEY = 'medscribe_physician'

export async function login(username, password) {
  const response = await axios.post(`${API_BASE_URL}/auth/login`, { username, password })
  const token = response.data.access_token
  sessionStorage.setItem(TOKEN_KEY, token)

  const me = await axios.get(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  const physician = {
    username: me.data.username,
    physician_name: me.data.physician_name,
    department: me.data.department
  }
  sessionStorage.setItem(PHYSICIAN_KEY, JSON.stringify(physician))
  return { token, ...physician }
}

export function logout() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(PHYSICIAN_KEY)
  sessionStorage.removeItem('medscribe_session')
  sessionStorage.removeItem('medscribe_screen')
  window.dispatchEvent(new Event('medscribe_logout'))
}

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function getPhysician() {
  const stored = sessionStorage.getItem(PHYSICIAN_KEY)
  if (!stored) return null
  try {
    return JSON.parse(stored)
  } catch {
    return null
  }
}

export function isLoggedIn() {
  return Boolean(getToken())
}
