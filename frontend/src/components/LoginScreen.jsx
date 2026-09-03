import { useState } from 'react'
import { login } from '../api/auth'

export default function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('dr.sharma')
  const [password, setPassword] = useState('medscribe123')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const physician = await login(username.trim(), password)
      onLogin(physician)
    } catch (err) {
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail
        setError(typeof detail === 'string' ? detail : (detail.message || 'Invalid username or password.'))
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        setError(`Unable to connect to the MedScribe server. Please try again in a moment.`)

      } else {
        setError('Invalid username or password. Please use one of the demo accounts below.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-7 shadow-sm">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-600 text-xl font-semibold text-white">
            M
          </div>
          <h1 className="text-2xl font-semibold text-slate-950">MedScribe</h1>
          <p className="mt-1 text-sm text-slate-600">Clinical Documentation AI</p>
        </div>

        <form onSubmit={submit} className="mt-7 space-y-4">
          <div>
            <label htmlFor="username" className="text-sm font-medium text-slate-800">Username</label>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              autoComplete="username"
            />
          </div>
          <div>
            <label htmlFor="password" className="text-sm font-medium text-slate-800">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              autoComplete="current-password"
            />
          </div>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-wait disabled:bg-slate-300"
          >
            {loading ? 'Signing in...' : 'Login'}
          </button>
        </form>

        <div className="mt-5 rounded-md bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
          <div className="font-medium text-slate-800">Demo accounts</div>
          <div>dr.sharma / dr.kumar / dr.patel</div>
          <div>Password: medscribe123</div>
        </div>
      </section>
    </main>
  )
}
