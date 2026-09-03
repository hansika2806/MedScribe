export default function NavBar({ physician, onLogout }) {
  return (
    <header className="border-b border-slate-200 bg-white px-4 py-3">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 font-semibold text-white">
            M
          </div>
          <div className="text-base font-semibold text-slate-950">MedScribe</div>
        </div>
        <div className="min-w-0 text-left sm:text-center">
          <div className="truncate text-sm font-semibold text-slate-900">
            {physician?.physician_name || 'Physician'}
          </div>
          <div className="truncate text-xs text-slate-500">
            {physician?.department || 'Department'}
          </div>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="w-full rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100 sm:w-auto"
        >
          Logout
        </button>
      </div>
    </header>
  )
}
