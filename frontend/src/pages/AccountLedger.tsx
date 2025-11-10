import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { accountApi } from '@/services/api'
import { useFiscalYear } from '@/contexts/FiscalYearContext'

interface LedgerEntry {
  verification_id: number
  verification_number: number
  series: string
  transaction_date: string
  description: string
  debit: number
  credit: number
  balance: number
}

interface AccountLedger {
  account_id: number
  account_number: number
  account_name: string
  opening_balance: number
  closing_balance: number
  entries: LedgerEntry[]
}

export default function AccountLedger() {
  const { accountId } = useParams<{ accountId: string }>()
  const navigate = useNavigate()
  const { selectedFiscalYear } = useFiscalYear()
  const [ledger, setLedger] = useState<AccountLedger | null>(null)
  const [loading, setLoading] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Set default date range to selected fiscal year
  useEffect(() => {
    if (selectedFiscalYear) {
      setStartDate(selectedFiscalYear.start_date)
      setEndDate(selectedFiscalYear.end_date)
    }
  }, [selectedFiscalYear])

  useEffect(() => {
    if (accountId) {
      loadLedger()
    }
  }, [accountId, startDate, endDate])

  const loadLedger = async () => {
    if (!accountId) return

    try {
      setLoading(true)
      const params: any = {}
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate

      const response = await accountApi.getLedger(parseInt(accountId), params)
      setLedger(response.data)
    } catch (error) {
      console.error('Failed to load ledger:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 2,
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('sv-SE')
  }

  if (loading && !ledger) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!ledger) {
    return <div>Kontohistorik saknas</div>
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="text-blue-600 hover:text-blue-800 mb-2 inline-flex items-center"
        >
          ← Tillbaka
        </button>
        <h1 className="text-3xl font-bold">
          Kontohistorik: {ledger.account_number} - {ledger.account_name}
        </h1>
        <p className="text-gray-600 mt-2">
          Ingående balans: {formatCurrency(ledger.opening_balance)} | Utgående balans:{' '}
          {formatCurrency(ledger.closing_balance)}
          {selectedFiscalYear && (
            <span className="ml-4 text-sm">
              (Räkenskapsår: {formatDate(selectedFiscalYear.start_date)} -{' '}
              {formatDate(selectedFiscalYear.end_date)})
            </span>
          )}
        </p>
      </div>

      {/* Date filters */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4">Filter</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Från datum</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Till datum</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>
        <div className="flex gap-3 mt-3">
          {selectedFiscalYear && (
            <button
              onClick={() => {
                setStartDate(selectedFiscalYear.start_date)
                setEndDate(selectedFiscalYear.end_date)
              }}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Återställ till räkenskapsår
            </button>
          )}
          {(startDate || endDate) && (
            <button
              onClick={() => {
                setStartDate('')
                setEndDate('')
              }}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              Visa allt (ingen filtrering)
            </button>
          )}
        </div>
      </div>

      {/* Ledger table */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">
          Transaktioner ({ledger.entries.length})
        </h2>

        {ledger.entries.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>Inga transaktioner hittades för den valda perioden.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ver.nr
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Beskrivning
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Debet
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Kredit
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Saldo
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {ledger.entries.map((entry, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/verifications/${entry.verification_id}`)}
                  >
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {formatDate(entry.transaction_date)}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-600">
                      {entry.series}-{entry.verification_number}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">{entry.description}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {entry.debit > 0 ? formatCurrency(entry.debit) : ''}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {entry.credit > 0 ? formatCurrency(entry.credit) : ''}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                      {formatCurrency(entry.balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50">
                <tr>
                  <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                    Totalt
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                    {formatCurrency(ledger.entries.reduce((sum, e) => sum + e.debit, 0))}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                    {formatCurrency(ledger.entries.reduce((sum, e) => sum + e.credit, 0))}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                    {formatCurrency(ledger.closing_balance)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
