import { useEffect, useState } from 'react'
import { Edit2, Save, X, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { companyApi, accountApi } from '@/services/api'
import type { Account } from '@/types'
import api from '@/services/api'

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState<string>('')

  useEffect(() => {
    loadAccounts()
  }, [])

  const loadAccounts = async () => {
    try {
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) {
        setLoading(false)
        return
      }
      const company = companiesRes.data[0]
      const accountsRes = await accountApi.list(company.id)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    } finally {
      setLoading(false)
    }
  }

  const startEdit = (account: Account) => {
    setEditingId(account.id)
    setEditValue(account.opening_balance.toString())
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditValue('')
  }

  const saveBalance = async (accountId: number) => {
    try {
      await api.patch(`/accounts/${accountId}`, {
        opening_balance: parseFloat(editValue) || 0,
      })
      await loadAccounts()
      setEditingId(null)
      setEditValue('')
    } catch (error) {
      console.error('Failed to update balance:', error)
      alert('Kunde inte uppdatera balansen')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar konton...</p>
      </div>
    )
  }

  // Filter accounts
  const filteredAccounts = accounts.filter((account) => {
    const matchesType = filterType === 'all' || account.account_type === filterType
    const matchesSearch =
      searchQuery === '' ||
      account.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      account.account_number.toString().includes(searchQuery)
    return matchesType && matchesSearch
  })

  // Group accounts by type
  const accountsByType = filteredAccounts.reduce((acc, account) => {
    const type = account.account_type
    if (!acc[type]) {
      acc[type] = []
    }
    acc[type].push(account)
    return acc
  }, {} as Record<string, Account[]>)

  const typeLabels: Record<string, string> = {
    asset: 'Tillgångar (1xxx)',
    equity_liability: 'Eget kapital och skulder (2xxx)',
    revenue: 'Intäkter (3xxx)',
    cost_goods: 'Kostnad varor/material (4xxx)',
    cost_local: 'Kostnad lokaler (5xxx)',
    cost_other: 'Övriga kostnader (6xxx)',
    cost_personnel: 'Personalkostnader (7xxx)',
    cost_misc: 'Diverse kostnader (8xxx)',
  }

  const totalBalance = filteredAccounts.reduce((sum, acc) => sum + acc.current_balance, 0)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-4">Kontoplan</h1>
        <p className="text-gray-600">
          BAS 2024 kontoplan med {accounts.length} konton
        </p>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sök konto
            </label>
            <input
              type="text"
              placeholder="Kontonummer eller namn..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kontotyp
            </label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="all">Alla typer ({accounts.length})</option>
              {Object.entries(typeLabels).map(([type, label]) => {
                const count = accounts.filter((a) => a.account_type === type).length
                return (
                  <option key={type} value={type}>
                    {label} ({count})
                  </option>
                )
              })}
            </select>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Totalt antal konton</h3>
          <p className="text-2xl font-bold">{filteredAccounts.length}</p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">BAS-konton</h3>
          <p className="text-2xl font-bold">
            {filteredAccounts.filter((a) => a.is_bas_account).length}
          </p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Totalt saldo</h3>
          <p className="text-2xl font-bold">
            {totalBalance.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
          </p>
        </div>
      </div>

      {/* Accounts grouped by type */}
      {filterType === 'all' ? (
        <div className="space-y-6">
          {Object.entries(accountsByType).map(([type, accs]) => (
            <div key={type} className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center justify-between">
                <span>{typeLabels[type]}</span>
                <span className="text-sm font-normal text-gray-500">
                  {accs.length} konton
                </span>
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Konto
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Namn
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                        Ingående balans (IB)
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                        Saldo
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                        Åtgärd
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {accs.map((account) => (
                      <tr key={account.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium">{account.account_number}</td>
                        <td className="px-4 py-3 text-sm">{account.name}</td>
                        <td className="px-4 py-3 text-sm text-right font-mono">
                          {editingId === account.id ? (
                            <input
                              type="number"
                              step="0.01"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="w-32 px-2 py-1 text-right border border-indigo-300 rounded focus:ring-2 focus:ring-indigo-500"
                              autoFocus
                            />
                          ) : (
                            <span className={account.opening_balance !== 0 ? 'text-indigo-600 font-medium' : ''}>
                              {account.opening_balance.toLocaleString('sv-SE', {
                                style: 'currency',
                                currency: 'SEK',
                              })}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-right font-mono">
                          {account.current_balance.toLocaleString('sv-SE', {
                            style: 'currency',
                            currency: 'SEK',
                          })}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {editingId === account.id ? (
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={() => saveBalance(account.id)}
                                className="p-1 text-green-600 hover:text-green-800"
                                title="Spara"
                              >
                                <Save className="w-4 h-4" />
                              </button>
                              <button
                                onClick={cancelEdit}
                                className="p-1 text-gray-600 hover:text-gray-800"
                                title="Avbryt"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center justify-center gap-2">
                              <Link
                                to={`/accounts/${account.id}/ledger`}
                                className="p-1 text-blue-600 hover:text-blue-800"
                                title="Visa kontohistorik"
                              >
                                <FileText className="w-4 h-4" />
                              </Link>
                              <button
                                onClick={() => startEdit(account)}
                                className="p-1 text-indigo-600 hover:text-indigo-800"
                                title="Sätt ingående balans"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-gray-50">
                    <tr>
                      <td colSpan={4} className="px-4 py-3 text-sm font-medium text-right">
                        Summa:
                      </td>
                      <td className="px-4 py-3 text-sm font-bold text-right font-mono">
                        {accs
                          .reduce((sum, a) => sum + a.current_balance, 0)
                          .toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          ))}
        </div>
      ) : (
        // Single type view
        <div className="card">
          <h2 className="text-xl font-bold mb-4">{typeLabels[filterType]}</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Konto
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Namn
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Ingående balans (IB)
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Saldo
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Åtgärd
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {filteredAccounts.map((account) => (
                  <tr key={account.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">{account.account_number}</td>
                    <td className="px-4 py-3 text-sm">{account.name}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {editingId === account.id ? (
                        <input
                          type="number"
                          step="0.01"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="w-32 px-2 py-1 text-right border border-indigo-300 rounded focus:ring-2 focus:ring-indigo-500"
                          autoFocus
                        />
                      ) : (
                        <span className={account.opening_balance !== 0 ? 'text-indigo-600 font-medium' : ''}>
                          {account.opening_balance.toLocaleString('sv-SE', {
                            style: 'currency',
                            currency: 'SEK',
                          })}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {account.current_balance.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {editingId === account.id ? (
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => saveBalance(account.id)}
                            className="p-1 text-green-600 hover:text-green-800"
                            title="Spara"
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="p-1 text-gray-600 hover:text-gray-800"
                            title="Avbryt"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-2">
                          <Link
                            to={`/accounts/${account.id}/ledger`}
                            className="p-1 text-blue-600 hover:text-blue-800"
                            title="Visa kontohistorik"
                          >
                            <FileText className="w-4 h-4" />
                          </Link>
                          <button
                            onClick={() => startEdit(account)}
                            className="p-1 text-indigo-600 hover:text-indigo-800"
                            title="Sätt ingående balans"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
