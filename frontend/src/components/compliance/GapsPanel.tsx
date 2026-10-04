import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { verificationApi } from '@/services/api'
import type { VerificationGap } from '@/types'
import { useToast } from '@/contexts/ToastContext'

interface Props {
  companyId: number
  fiscalYearId: number
  gaps: VerificationGap[]
  onChange?: () => void
}

export default function GapsPanel({ companyId, fiscalYearId, gaps, onChange }: Props) {
  const { showToast } = useToast()
  const [texts, setTexts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  if (gaps.length === 0) return null

  const explain = async (gap: VerificationGap) => {
    const key = `${gap.series}${gap.verification_number}`
    const explanation = (texts[key] || '').trim()
    if (explanation.length < 3) {
      showToast('Skriv en förklaring till luckan', 'error')
      return
    }
    setSaving(key)
    try {
      await verificationApi.explainGap({
        company_id: companyId,
        fiscal_year_id: fiscalYearId,
        series: gap.series,
        verification_number: gap.verification_number,
        explanation,
      })
      showToast(`Lucka ${key} förklarad`, 'success')
      onChange?.()
    } catch (error: any) {
      showToast(error.response?.data?.detail || 'Kunde inte spara förklaringen', 'error')
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-amber-900">Luckor i verifikationsserien</h3>
          <p className="text-sm text-amber-800 mt-1">
            Verifikationsnumren ska vara obrutna. {gaps.length} nummer saknas utan förklaring. Ange orsaken (BFNAR 2013:2).
          </p>
          <ul className="mt-3 space-y-2">
            {gaps.map((gap) => {
              const key = `${gap.series}${gap.verification_number}`
              return (
                <li key={key} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono font-semibold w-16">{key}</span>
                  <input
                    type="text"
                    value={texts[key] || ''}
                    onChange={(e) => setTexts((t) => ({ ...t, [key]: e.target.value }))}
                    placeholder="Förklaring, t.ex. makulerad vid registrering"
                    className="flex-1 min-w-[14rem] px-2 py-1 border border-amber-300 rounded-md bg-white"
                  />
                  <button onClick={() => explain(gap)} disabled={saving === key} className="btn btn-secondary text-sm">
                    {saving === key ? 'Sparar...' : 'Spara'}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
