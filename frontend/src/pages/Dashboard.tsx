import { useEffect, useState } from 'react'
import { accountApi, reportApi } from '@/services/api'
import type { Account, MonthlyStatistics } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function Dashboard() {
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [monthlyStats, setMonthlyStats] = useState<MonthlyStatistics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [selectedCompany, selectedFiscalYear])

  const loadData = async () => {
    if (!selectedCompany) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      // Load accounts
      const accountsRes = await accountApi.list(selectedCompany.id)
      setAccounts(accountsRes.data)

      // Load monthly statistics if fiscal year is selected
      if (selectedFiscalYear) {
        console.log('Loading monthly statistics for year:', selectedFiscalYear.year)
        const statsRes = await reportApi.monthlyStatistics(selectedCompany.id, selectedFiscalYear.year)
        console.log('Monthly statistics loaded:', statsRes.data)
        setMonthlyStats(statsRes.data)
      } else {
        console.log('No fiscal year selected, skipping monthly statistics')
        setMonthlyStats(null)
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar...</p>
      </div>
    )
  }

  if (!selectedCompany) {
    return (
      <div className="card">
        <h2 className="text-2xl font-bold mb-4">Välkommen till Reknir</h2>
        <p className="text-gray-600 mb-4">
          Inget företag registrerat ännu. Gå till Inställningar för att skapa ditt företag.
        </p>
      </div>
    )
  }

  const formatCurrency = (value: number) =>
    value.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0 })

  const totalAssets = accounts
    .filter((a) => a.account_type === 'asset')
    .reduce((sum, a) => sum + a.current_balance, 0)

  const totalRevenue = accounts
    .filter((a) => a.account_type === 'revenue')
    .reduce((sum, a) => sum + a.current_balance, 0)

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Översikt</h1>

      {/* No fiscal year selected message */}
      {!selectedFiscalYear && (
        <div className="card mb-8 bg-blue-50 border-blue-200">
          <p className="text-blue-800">
            📅 Välj ett verksamhetsår i menyn ovan för att se ekonomiska grafer och statistik.
          </p>
        </div>
      )}

      {/* Financial Overview Cards */}
      {monthlyStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {/* Company Info */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Företag</h3>
            <p className="text-xl font-bold">{selectedCompany.name}</p>
            <p className="text-xs text-gray-600">Org.nr: {selectedCompany.org_number}</p>
            {selectedFiscalYear && (
              <p className="text-xs text-gray-500 mt-2">
                År: {selectedFiscalYear.year} ({selectedFiscalYear.label})
              </p>
            )}
          </div>

          {/* YTD Revenue */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Intäkter (Hittills)</h3>
            <p className="text-2xl font-bold text-green-600">
              {formatCurrency(monthlyStats.ytd_totals.revenue)}
            </p>
            <p className="text-xs text-gray-500 mt-2">
              {selectedFiscalYear ? `${selectedFiscalYear.year}` : 'Innevarande år'}
            </p>
          </div>

          {/* YTD Expenses */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Kostnader (Hittills)</h3>
            <p className="text-2xl font-bold text-red-600">
              {formatCurrency(monthlyStats.ytd_totals.expenses)}
            </p>
            <p className="text-xs text-gray-500 mt-2">
              {selectedFiscalYear ? `${selectedFiscalYear.year}` : 'Innevarande år'}
            </p>
          </div>

          {/* YTD Profit/Loss */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Resultat (Hittills)</h3>
            <p
              className={`text-2xl font-bold ${
                monthlyStats.ytd_totals.profit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {formatCurrency(monthlyStats.ytd_totals.profit)}
            </p>
            <p className="text-xs text-gray-500 mt-2">
              {monthlyStats.ytd_totals.profit >= 0 ? 'Vinst' : 'Förlust'}
            </p>
          </div>
        </div>
      )}

      {/* Monthly Financial Chart */}
      {monthlyStats && monthlyStats.monthly_data.length > 0 && (
        <div className="card mb-8">
          <h2 className="text-xl font-bold mb-4">Ekonomisk utveckling per månad</h2>
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart
              data={monthlyStats.monthly_data}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month_name" />
              <YAxis
                tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                labelStyle={{ color: '#333' }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="revenue"
                stackId="1"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.6}
                name="Intäkter"
              />
              <Area
                type="monotone"
                dataKey="expenses"
                stackId="2"
                stroke="#ef4444"
                fill="#ef4444"
                fillOpacity={0.6}
                name="Kostnader"
              />
              <Area
                type="monotone"
                dataKey="profit"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.3}
                name="Resultat"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent accounts */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">Kontoöversikt</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Konto
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Namn
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Saldo
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {accounts.slice(0, 10).map((account) => (
                <tr key={account.id}>
                  <td className="px-4 py-3 text-sm">{account.account_number}</td>
                  <td className="px-4 py-3 text-sm">{account.name}</td>
                  <td className="px-4 py-3 text-sm text-right font-mono">
                    {account.current_balance.toLocaleString('sv-SE', {
                      style: 'currency',
                      currency: 'SEK',
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
