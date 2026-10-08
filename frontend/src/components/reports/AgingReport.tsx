import { useEffect, useState } from 'react'
import { reportApi } from '@/services/api'
import type { AgingReport as AgingReportData } from '@/types'

const formatCurrency = (n: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 }).format(n)

export default function AgingReport({ companyId }: { companyId: number }) {
  const [kind, setKind] = useState<'customer' | 'supplier'>('customer')
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10))
  const [data, setData] = useState<AgingReportData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    reportApi
      .aging(companyId, kind, asOf)
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [companyId, kind, asOf])

  return (
    <div className="card">
      <h2 className="text-2xl font-bold mb-2">{kind === 'customer' ? 'Kundreskontra' : 'Leverantörsreskontra'} – åldersanalys</h2>
      <p className="text-gray-600 mb-4">Obetalda fakturor fördelade efter hur många dagar de är förfallna.</p>
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="inline-flex rounded-md border border-gray-300 overflow-hidden">
          <button onClick={() => setKind('customer')} className={`px-3 py-2 text-sm ${kind === 'customer' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}>
            Kunder
          </button>
          <button onClick={() => setKind('supplier')} className={`px-3 py-2 text-sm ${kind === 'supplier' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}>
            Leverantörer
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          Per datum
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-md" />
        </label>
      </div>
      {loading || !data ? (
        <p className="text-gray-500">Laddar...</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
            {data.buckets.map((b) => (
              <div key={b.key} className="p-3 rounded-lg bg-gray-50 border border-gray-200">
                <div className="text-xs text-gray-500">{b.label}</div>
                <div className="font-mono font-semibold">{formatCurrency(b.amount)}</div>
              </div>
            ))}
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <div className="text-xs text-blue-700">Totalt öppet</div>
              <div className="font-mono font-semibold text-blue-900">{formatCurrency(data.total)}</div>
            </div>
          </div>
          {data.parties.length === 0 ? (
            <p className="text-gray-500">Inga öppna poster.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">{kind === 'customer' ? 'Kund' : 'Leverantör'}</th>
                    {data.buckets.map((b) => (
                      <th key={b.key} className="px-3 py-2 text-right font-medium text-gray-600">{b.label}</th>
                    ))}
                    <th className="px-3 py-2 text-right font-medium text-gray-600">Totalt</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.parties.map((p) => (
                    <tr key={p.name}>
                      <td className="px-3 py-2">{p.name}</td>
                      {data.buckets.map((b) => (
                        <td key={b.key} className="px-3 py-2 text-right font-mono">{formatCurrency((p as unknown as Record<string, number>)[b.key] ?? 0)}</td>
                      ))}
                      <td className="px-3 py-2 text-right font-mono font-semibold">{formatCurrency(p.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3 className="font-semibold mt-6 mb-2">Fakturor</h3>
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Nr</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Motpart</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Förfaller</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-600">Dagar sena</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-600">Öppet belopp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.invoices.map((inv) => (
                    <tr key={inv.id} className={inv.days_overdue > 0 ? 'text-red-700' : ''}>
                      <td className="px-3 py-2 font-mono">{inv.number}</td>
                      <td className="px-3 py-2">{inv.party}</td>
                      <td className="px-3 py-2">{inv.due_date}</td>
                      <td className="px-3 py-2 text-right">{inv.days_overdue || '–'}</td>
                      <td className="px-3 py-2 text-right font-mono">{formatCurrency(inv.open_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
