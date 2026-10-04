import { useEffect, useState } from 'react'
import { reportApi } from '@/services/api'
import type { CashFlowReport as CashFlowData } from '@/types'

const formatCurrency = (n: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 }).format(n)

export default function CashFlowReport({ companyId, fiscalYearId }: { companyId: number; fiscalYearId: number }) {
  const [data, setData] = useState<CashFlowData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    reportApi
      .cashFlow(companyId, fiscalYearId)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [companyId, fiscalYearId])

  if (loading || !data) {
    return (
      <div className="card">
        <p className="text-gray-500">Laddar...</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="text-2xl font-bold mb-2">Kassaflödesanalys</h2>
      <p className="text-gray-600 mb-4">
        Rörelser på likvida medel ({data.cash_accounts.join(', ') || 'inga 19xx-konton'}) per månad, fördelade på vad de bokförts mot.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
          <div className="text-xs text-gray-500">Ingående likvida medel</div>
          <div className="font-mono font-semibold">{formatCurrency(data.opening)}</div>
        </div>
        <div className="p-3 rounded-lg bg-green-50 border border-green-200">
          <div className="text-xs text-green-700">Inbetalningar</div>
          <div className="font-mono font-semibold text-green-900">{formatCurrency(data.months.reduce((s, m) => s + m.inflow, 0))}</div>
        </div>
        <div className="p-3 rounded-lg bg-red-50 border border-red-200">
          <div className="text-xs text-red-700">Utbetalningar</div>
          <div className="font-mono font-semibold text-red-900">{formatCurrency(data.months.reduce((s, m) => s + m.outflow, 0))}</div>
        </div>
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
          <div className="text-xs text-blue-700">Utgående likvida medel</div>
          <div className="font-mono font-semibold text-blue-900">{formatCurrency(data.closing)}</div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Månad</th>
              {data.categories.map((c) => (
                <th key={c.key} className="px-3 py-2 text-right font-medium text-gray-600">{c.label}</th>
              ))}
              <th className="px-3 py-2 text-right font-medium text-gray-600">Netto</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Saldo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.months.map((m) => (
              <tr key={m.month}>
                <td className="px-3 py-2 font-mono">{m.month}</td>
                {data.categories.map((c) => {
                  const v = m.by_category[c.key] ?? 0
                  return (
                    <td key={c.key} className={`px-3 py-2 text-right font-mono ${v < 0 ? 'text-red-700' : v > 0 ? 'text-green-700' : 'text-gray-400'}`}>
                      {v === 0 ? '–' : formatCurrency(v)}
                    </td>
                  )
                })}
                <td className={`px-3 py-2 text-right font-mono font-semibold ${m.net < 0 ? 'text-red-700' : 'text-green-700'}`}>{formatCurrency(m.net)}</td>
                <td className="px-3 py-2 text-right font-mono">{formatCurrency(m.closing)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
