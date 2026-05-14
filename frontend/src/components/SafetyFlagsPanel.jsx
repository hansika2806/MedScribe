const labels = {
  drug_interaction: { icon: '💊', label: 'Drug Interaction' },
  red_flag: { icon: '🚨', label: 'Red Flag Diagnosis' },
  red_flag_diagnosis: { icon: '🚨', label: 'Red Flag Diagnosis' },
  dosage: { icon: '⚠️', label: 'Dosage Risk' },
  dosage_risk: { icon: '⚠️', label: 'Dosage Risk' },
  system_error: { icon: '⚠️', label: 'System Error' }
}

export default function SafetyFlagsPanel({ safetyResult = {} }) {
  const flags = safetyResult?.safety_flags || []

  if (!flags.length) return null

  return (
    <section className="rounded-lg border-2 border-red-300 bg-red-50 p-5">
      <h2 className="text-lg font-bold text-red-950">⚠️ Safety Flags Detected</h2>
      <div className="mt-4 space-y-3">
        {flags.map((flag, index) => {
          const meta = labels[flag.check_type] || { icon: '⚠️', label: flag.check_type || 'Safety Flag' }
          const urgent = flag.urgency === 'urgent'
          return (
            <article key={`${flag.detail}-${index}`} className="rounded-md border border-red-300 bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex gap-3">
                  <span className="text-2xl">{meta.icon}</span>
                  <div>
                    <h3 className="font-semibold text-red-950">{meta.label}</h3>
                    <p className="mt-1 text-sm leading-6 text-red-900">{flag.detail}</p>
                  </div>
                </div>
                <span className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${urgent ? 'bg-red-700 text-white' : 'bg-orange-100 text-orange-800'}`}>
                  {urgent ? 'URGENT' : 'REVIEW'}
                </span>
              </div>
            </article>
          )
        })}
      </div>
      <p className="mt-4 text-sm font-medium text-red-950">Please review all safety flags before approving this note.</p>
    </section>
  )
}

