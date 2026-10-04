import { useCallback, useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { companyApi } from '@/services/api'
import type { PeriodLockStatus } from '@/types'
import { useToast } from '@/contexts/ToastContext'

interface Props {
  companyId: number
  suggestedDate?: string
  compact?: boolean
  onLocked?: () => void
}

export default function PeriodLockPanel({ companyId, suggestedDate, compact = false, onLocked }: Props) {
  const { showToast } = useToast()
  const [status, setStatus] = useState<PeriodLockStatus | null>(null)
  const [date, setDate] = useState(suggestedDate ?? '')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await companyApi.periodLocks(companyId)
      setStatus(res.data)
    } catch {
      setStatus(null)
    }
  }, [companyId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (suggestedDate) setDate(suggestedDate)
  }, [suggestedDate])

  const lock = async () => {
    if (!date) return
    const confirmed = window.confirm(
      `Lås bokföringen till och med ${date}? Inget kan bokföras på eller före det datumet efteråt; rättelser bokförs på ett senare datum. Låsningen kan inte flyttas bakåt.`
    )
    if (!confirmed) return
    setSaving(true)
    try {
      await companyApi.lockPeriod(companyId, { locked_through: date, note: note || undefined })
      showToast(`Perioden är låst t.o.m. ${date}`, 'success')
      setNote('')
      await load()
      onLocked?.()
    } catch (error: any) {
      showToast(error.response?.data?.detail || 'Kunde inte låsa perioden', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={compact ? 'p-4 bg-gray-50 rounded-lg border border-gray-200' : 'card'}>
      <div className="flex items-center gap-2 mb-2">
        <Lock className="w-5 h-5 text-gray-600" />
        <h3 className={compact ? 'font-semibold' : 'text-xl font-bold'}>Låst period</h3>
      </div>
      <p className="text-sm text-gray-600 mb-3">
        {status?.locked_through
          ? `Bokföringen är låst till och med ${status.locked_through}.`
          : 'Ingen period är låst. Lås perioden när momsen är deklarerad, så kan inget ändras bakåt.'}
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Lås t.o.m.</label>
          <input
            type="date"
            value={date}
            min={status?.locked_through ?? undefined}
            onChange={(e) => setDate(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
        </div>
        <div className="flex-1 min-w-[12rem]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Anteckning</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="t.ex. Moms Q1 deklarerad"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
        </div>
        <button onClick={lock} disabled={!date || saving} className="btn btn-primary inline-flex items-center">
          <Lock className="w-4 h-4 mr-2" />
          {saving ? 'Låser...' : 'Lås perioden'}
        </button>
      </div>
      {!compact && status && status.history.length > 0 && (
        <ul className="mt-4 text-xs text-gray-600 divide-y divide-gray-100">
          {status.history.map((h) => (
            <li key={h.id} className="py-1 flex justify-between gap-4">
              <span>
                Låst t.o.m. {h.locked_through}
                {h.note ? ` – ${h.note}` : ''}
              </span>
              <span className="text-gray-400">{new Date(h.created_at + 'Z').toLocaleString('sv-SE')}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
