import { useEffect, useState } from 'react'
import { accountApi } from '@/services/api'
import type { Account } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'

export default function Dashboard() {
  const { selectedCompany } = useCompany()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [selectedCompany])

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

  const totalAssets = accounts
    .filter((a) => a.account_type === 'asset')
    .reduce((sum, a) => sum + a.current_balance, 0)

  const totalRevenue = accounts
    .filter((a) => a.account_type === 'revenue')
    .reduce((sum, a) => sum + a.current_balance, 0)

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Översikt</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Company Info */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Företag</h3>
          <p className="text-2xl font-bold">{selectedCompany.name}</p>
          <p className="text-sm text-gray-600">Org.nr: {selectedCompany.org_number}</p>
        </div>

        {/* Assets */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Tillgångar</h3>
          <p className="text-2xl font-bold">
            {totalAssets.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
          </p>
        </div>

        {/* Revenue */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Intäkter</h3>
          <p className="text-2xl font-bold">
            {totalRevenue.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
          </p>
        </div>
      </div>

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
