import { useEffect, useState } from 'react'
import { Edit2, Save, X, FileText, Trash2, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { accountApi, defaultAccountApi, companyApi, postingTemplateApi } from '@/services/api'
import type { Account, DefaultAccount, PostingTemplate } from '@/types'
import api from '@/services/api'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import FiscalYearSelector from '@/components/FiscalYearSelector'

const DEFAULT_ACCOUNT_LABELS: Record<string, string> = {
  revenue_25: 'Försäljning 25% moms',
  revenue_12: 'Försäljning 12% moms',
  revenue_6: 'Försäljning 6% moms',
  revenue_0: 'Försäljning 0% moms (export)',
  vat_outgoing_25: 'Utgående moms 25%',
  vat_outgoing_12: 'Utgående moms 12%',
  vat_outgoing_6: 'Utgående moms 6%',
  vat_incoming_25: 'Ingående moms 25%',
  vat_incoming_12: 'Ingående moms 12%',
  vat_incoming_6: 'Ingående moms 6%',
  accounts_receivable: 'Kundfordringar',
  accounts_payable: 'Leverantörsskulder',
  expense_default: 'Standardkostnadskonto',
}

export default function Accounts() {
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState<string>('')
  const [activeTab, setActiveTab] = useState<'accounts' | 'defaults'>('accounts')

  // Default accounts state
  const [defaultAccounts, setDefaultAccounts] = useState<DefaultAccount[]>([])
  const [editingDefaultAccountType, setEditingDefaultAccountType] = useState<string | null>(null)
  const [selectedAccountIdForDefault, setSelectedAccountIdForDefault] = useState<number | null>(null)
  const [savingDefaultAccount, setSavingDefaultAccount] = useState(false)
  const [deletingDefaultAccountType, setDeletingDefaultAccountType] = useState<string | null>(null)
  const [removingDefaultAccount, setRemovingDefaultAccount] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')

  // Add account state
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [basAccounts, setBasAccounts] = useState<any[]>([])
  const [selectedBasAccount, setSelectedBasAccount] = useState<string>('')

  // Delete account state
  const [templates, setTemplates] = useState<PostingTemplate[]>([])
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    show: boolean
    account: Account | null
    canDelete: boolean
    blockingReason: string | null
  }>({
    show: false,
    account: null,
    canDelete: true,
    blockingReason: null
  })

  const showMessage = (msg: string, type: 'success' | 'error') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => setMessage(''), 3000)
  }

  useEffect(() => {
    loadAccounts()
    loadDefaultAccounts()
    loadTemplates()
  }, [selectedCompany, selectedFiscalYear])

  const loadAccounts = async () => {
    if (!selectedCompany || !selectedFiscalYear) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      const accountsRes = await accountApi.list(selectedCompany.id, selectedFiscalYear.id)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadDefaultAccounts = async () => {
    if (!selectedCompany) return
    try {
      const defaultsRes = await defaultAccountApi.list(selectedCompany.id)
      setDefaultAccounts(defaultsRes.data)
    } catch (error) {
      console.error('Failed to load default accounts:', error)
    }
  }

  const loadTemplates = async () => {
    if (!selectedCompany) return
    try {
      const templatesRes = await postingTemplateApi.list(selectedCompany.id)
      setTemplates(templatesRes.data)
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const loadBasAccounts = async () => {
    try {
      const response = await companyApi.getBasAccounts()
      setBasAccounts(response.data.accounts)
    } catch (error) {
      console.error('Failed to load BAS accounts:', error)
      showMessage('Kunde inte ladda BAS-konton', 'error')
    }
  }

  const handleShowAddAccount = async () => {
    await Promise.all([
      loadBasAccounts(),
      selectedFiscalYear && selectedCompany
        ? accountApi.list(selectedCompany.id, selectedFiscalYear.id)
            .then(res => setAccounts(res.data))
        : Promise.resolve()
    ])
    setShowAddAccount(true)
  }

  const handleAddAccount = async () => {
    if (!selectedCompany || !selectedFiscalYear || !selectedBasAccount) return

    const basAccount = basAccounts.find(acc => acc.account_number === parseInt(selectedBasAccount))
    if (!basAccount) {
      showMessage('Kunde inte hitta det valda kontot', 'error')
      return
    }

    try {
      setLoading(true)
      await accountApi.create({
        company_id: selectedCompany.id,
        fiscal_year_id: selectedFiscalYear.id,
        account_number: basAccount.account_number,
        name: basAccount.name,
        account_type: basAccount.account_type,
        description: basAccount.description,
        active: true,
        opening_balance: 0,
        is_bas_account: true,
      })

      showMessage('Konto tillagt!', 'success')
      setSelectedBasAccount('')
      setShowAddAccount(false)
      await loadAccounts()
    } catch (error: unknown) {
      console.error('Failed to add account:', error)
      const errorMessage = error instanceof Error ? error.message : 'Kunde inte lägga till konto'
      showMessage(errorMessage, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAccount = (account: Account) => {
    // Check if account can be deleted
    let canDelete = true
    let blockingReason: string | null = null

    // Check if account has transactions (balance has changed)
    if (account.current_balance !== account.opening_balance) {
      canDelete = false
      blockingReason = `Kontot har bokförda transaktioner för detta räkenskapsår och kan därför inte raderas.`
    }
    // Check if account is used in posting templates (templates use account_number)
    else {
      const usedInTemplate = templates.find(template =>
        template.template_lines.some(line => line.account_number === account.account_number)
      )

      if (usedInTemplate) {
        canDelete = false
        blockingReason = `Kontot används i konteringsmall "${usedInTemplate.name}". Ta bort eller redigera mallen först.`
      }
      // Check if account is used as default account
      else {
        const usedAsDefault = defaultAccounts.find(da => da.account_id === account.id)
        if (usedAsDefault) {
          canDelete = false
          const label = DEFAULT_ACCOUNT_LABELS[usedAsDefault.account_type] || usedAsDefault.account_type
          blockingReason = `Kontot används som standardkonto för "${label}". Ändra standardkontomappningen först.`
        }
      }
    }

    setDeleteConfirmation({
      show: true,
      account,
      canDelete,
      blockingReason
    })
  }

  const confirmDeleteAccount = async () => {
    if (!deleteConfirmation.account) return

    try {
      setLoading(true)
      await accountApi.delete(deleteConfirmation.account.id)
      showMessage('Konto borttaget!', 'success')
      await loadAccounts()
    } catch (error: unknown) {
      console.error('Failed to delete account:', error)
      const errorMessage = error instanceof Error ? error.message : 'Kunde inte ta bort konto'
      showMessage(errorMessage, 'error')
    } finally {
      setLoading(false)
      setDeleteConfirmation({ show: false, account: null, canDelete: true, blockingReason: null })
    }
  }

  const cancelDeleteAccount = () => {
    setDeleteConfirmation({ show: false, account: null, canDelete: true, blockingReason: null })
  }

  const getAccountForType = (accountType: string): DefaultAccount | undefined => {
    return defaultAccounts.find((da) => da.account_type === accountType)
  }

  const getAccountDisplay = (accountId: number): string => {
    const account = accounts.find((a) => a.id === accountId)
    return account ? `${account.account_number} - ${account.name}` : 'Okänt konto'
  }

  const handleEditDefaultAccount = (accountType: string) => {
    const existingDefault = getAccountForType(accountType)
    setEditingDefaultAccountType(accountType)
    setSelectedAccountIdForDefault(existingDefault?.account_id || null)
  }

  const handleSaveDefaultAccount = async () => {
    if (!selectedCompany || !editingDefaultAccountType || !selectedAccountIdForDefault) return

    setSavingDefaultAccount(true)
    try {
      const existingDefault = getAccountForType(editingDefaultAccountType)

      if (existingDefault) {
        await defaultAccountApi.update(existingDefault.id, { account_id: selectedAccountIdForDefault })
        showMessage('Standardkonto uppdaterat', 'success')
      } else {
        await defaultAccountApi.create({
          company_id: selectedCompany.id,
          account_type: editingDefaultAccountType,
          account_id: selectedAccountIdForDefault,
        })
        showMessage('Standardkonto sparat', 'success')
      }

      await loadDefaultAccounts()
      setEditingDefaultAccountType(null)
      setSelectedAccountIdForDefault(null)
    } catch (error: unknown) {
      console.error('Failed to save default account:', error)
      const errorMessage = error instanceof Error ? error.message : 'Kunde inte spara standardkonto'
      showMessage(errorMessage, 'error')
    } finally {
      setSavingDefaultAccount(false)
    }
  }

  const handleRemoveDefaultAccount = (accountType: string) => {
    setDeletingDefaultAccountType(accountType)
  }

  const confirmRemoveDefaultAccount = async () => {
    if (!selectedCompany || !deletingDefaultAccountType) return

    const existingDefault = getAccountForType(deletingDefaultAccountType)
    if (!existingDefault) return

    setRemovingDefaultAccount(true)
    try {
      await defaultAccountApi.delete(existingDefault.id)
      showMessage('Standardkonto borttaget', 'success')
      await loadDefaultAccounts()
      setDeletingDefaultAccountType(null)
    } catch (error: unknown) {
      console.error('Failed to remove default account:', error)
      const errorMessage = error instanceof Error ? error.message : 'Kunde inte ta bort standardkonto'
      showMessage(errorMessage, 'error')
    } finally {
      setRemovingDefaultAccount(false)
    }
  }

  const handleInitializeDefaults = async () => {
    if (!selectedCompany || !selectedFiscalYear) {
      showMessage('Du måste välja ett räkenskapsår först', 'error')
      return
    }

    try {
      setLoading(true)
      const response = await companyApi.initializeDefaults(selectedCompany.id, selectedFiscalYear.id)
      showMessage(response.data.message, 'success')
      await loadDefaultAccounts()
    } catch (error: unknown) {
      console.error('Failed to initialize defaults:', error)
      const errorMessage = error instanceof Error ? error.message : 'Kunde inte initialisera standardkonton'
      showMessage(errorMessage, 'error')
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
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-4">Kontoplan</h1>
          <p className="text-gray-600">
            BAS 2024 kontoplan med {accounts.length} konton
          </p>
        </div>
        <FiscalYearSelector />
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-4 p-4 rounded-lg ${messageType === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('accounts')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'accounts'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Kontoplan
          </button>
          <button
            onClick={() => setActiveTab('defaults')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'defaults'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Standardkonton
          </button>
        </nav>
      </div>

      {/* Kontoplan Tab */}
      {activeTab === 'accounts' && (
        <>
          {/* Add Account Button and Form */}
          <div className="flex justify-end mb-4">
            <button
              onClick={handleShowAddAccount}
              disabled={loading}
              className="btn btn-primary inline-flex items-center"
            >
              <Plus className="w-4 h-4 mr-2" />
              Lägg till konto
            </button>
          </div>

          {showAddAccount && (
            <div className="card mb-6 bg-gray-50 border border-gray-200">
              <h3 className="font-medium mb-3">Lägg till konto från BAS 2024</h3>
              <div className="mb-4">
                <select
                  value={selectedBasAccount}
                  onChange={(e) => setSelectedBasAccount(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">-- Välj ett BAS-konto --</option>
                  {basAccounts
                    .filter(bas => !accounts.some(acc => acc.account_number === bas.account_number))
                    .map(bas => (
                      <option key={bas.account_number} value={bas.account_number}>
                        {bas.account_number} - {bas.name}
                      </option>
                    ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Endast BAS-konton som inte redan finns i kontoplanen visas
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAddAccount}
                  disabled={loading || !selectedBasAccount}
                  className="btn btn-primary"
                >
                  Lägg till
                </button>
                <button
                  onClick={() => {
                    setShowAddAccount(false)
                    setSelectedBasAccount('')
                  }}
                  disabled={loading}
                  className="btn btn-secondary"
                >
                  Avbryt
                </button>
              </div>
            </div>
          )}

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
                              <button
                                onClick={() => handleDeleteAccount(account)}
                                className="p-1 text-red-600 hover:text-red-800"
                                title="Ta bort konto"
                              >
                                <Trash2 className="w-4 h-4" />
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
                          <button
                            onClick={() => handleDeleteAccount(account)}
                            className="p-1 text-red-600 hover:text-red-800"
                            title="Ta bort konto"
                          >
                            <Trash2 className="w-4 h-4" />
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
        </>
      )}

      {/* Standardkonton Tab */}
      {activeTab === 'defaults' && (
        <div className="card">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Standardkonton</h2>
            <button
              onClick={handleInitializeDefaults}
              disabled={loading}
              className="btn btn-secondary"
            >
              Initiera automatiskt
            </button>
          </div>

          <p className="text-gray-600 mb-4">
            Dessa konton används automatiskt vid fakturering och bokföring.
          </p>

          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Revenue Accounts */}
              <div>
                <h3 className="font-medium text-gray-900 mb-2">Intäktskonton</h3>
                <div className="space-y-2">
                  {['revenue_25', 'revenue_12', 'revenue_6', 'revenue_0'].map((type) => {
                    const defaultAcc = getAccountForType(type)
                    return (
                      <div key={type} className="flex justify-between items-center py-2 border-b">
                        <span className="text-sm text-gray-700 flex-shrink-0">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-600">
                            {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : <span className="text-gray-400">-</span>}
                          </span>
                          <button
                            onClick={() => handleEditDefaultAccount(type)}
                            className="text-blue-600 hover:text-blue-800 p-1 rounded"
                            title="Ändra konto"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {defaultAcc && (
                            <button
                              onClick={() => handleRemoveDefaultAccount(type)}
                              className="text-red-600 hover:text-red-800 p-1 rounded"
                              title="Ta bort standardkonto"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* VAT Accounts */}
              <div>
                <h3 className="font-medium text-gray-900 mb-2">Momskonton</h3>
                <div className="space-y-2">
                  {[
                    'vat_outgoing_25',
                    'vat_outgoing_12',
                    'vat_outgoing_6',
                    'vat_incoming_25',
                    'vat_incoming_12',
                    'vat_incoming_6',
                  ].map((type) => {
                    const defaultAcc = getAccountForType(type)
                    return (
                      <div key={type} className="flex justify-between items-center py-2 border-b">
                        <span className="text-sm text-gray-700 flex-shrink-0">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-600">
                            {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : <span className="text-gray-400">-</span>}
                          </span>
                          <button
                            onClick={() => handleEditDefaultAccount(type)}
                            className="text-blue-600 hover:text-blue-800 p-1 rounded"
                            title="Ändra konto"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {defaultAcc && (
                            <button
                              onClick={() => handleRemoveDefaultAccount(type)}
                              className="text-red-600 hover:text-red-800 p-1 rounded"
                              title="Ta bort standardkonto"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Other Accounts */}
              <div>
                <h3 className="font-medium text-gray-900 mb-2">Övriga konton</h3>
                <div className="space-y-2">
                  {['accounts_receivable', 'accounts_payable', 'expense_default'].map((type) => {
                    const defaultAcc = getAccountForType(type)
                    return (
                      <div key={type} className="flex justify-between items-center py-2 border-b">
                        <span className="text-sm text-gray-700 flex-shrink-0">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-600">
                            {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : <span className="text-gray-400">-</span>}
                          </span>
                          <button
                            onClick={() => handleEditDefaultAccount(type)}
                            className="text-blue-600 hover:text-blue-800 p-1 rounded"
                            title="Ändra konto"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {defaultAcc && (
                            <button
                              onClick={() => handleRemoveDefaultAccount(type)}
                              className="text-red-600 hover:text-red-800 p-1 rounded"
                              title="Ta bort standardkonto"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Default Account Selection Modal */}
      {editingDefaultAccountType && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  Välj konto för "{DEFAULT_ACCOUNT_LABELS[editingDefaultAccountType]}"
                </h3>
                <button
                  onClick={() => {
                    setEditingDefaultAccountType(null)
                    setSelectedAccountIdForDefault(null)
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Konto
                </label>
                <select
                  value={selectedAccountIdForDefault || ''}
                  onChange={(e) => setSelectedAccountIdForDefault(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">-- Välj konto --</option>
                  {accounts
                    .filter(account => account.active)
                    .sort((a, b) => a.account_number - b.account_number)
                    .map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.account_number} - {account.name}
                      </option>
                    ))}
                </select>
                <p className="mt-2 text-xs text-gray-500">
                  Endast aktiva konton från aktuellt räkenskapsår visas.
                </p>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => {
                    setEditingDefaultAccountType(null)
                    setSelectedAccountIdForDefault(null)
                  }}
                  disabled={savingDefaultAccount}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  Avbryt
                </button>
                <button
                  onClick={handleSaveDefaultAccount}
                  disabled={savingDefaultAccount || !selectedAccountIdForDefault}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {savingDefaultAccount ? (
                    <>
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Sparar...</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      <span>Spara</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Default Account Delete Confirmation Modal */}
      {deletingDefaultAccountType && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
            {/* Header */}
            <div className="bg-red-50 px-6 py-4 border-b border-red-100">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <Trash2 className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Ta bort standardkonto
                  </h3>
                  <p className="text-sm text-gray-600">
                    {DEFAULT_ACCOUNT_LABELS[deletingDefaultAccountType]}
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-4">
              <p className="text-gray-700">
                Är du säker på att du vill ta bort detta standardkonto?
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Funktioner som använder detta standardkonto kommer inte längre ha ett förvalt konto.
                Du kan alltid lägga till ett nytt standardkonto senare.
              </p>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setDeletingDefaultAccountType(null)}
                disabled={removingDefaultAccount}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={confirmRemoveDefaultAccount}
                disabled={removingDefaultAccount}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {removingDefaultAccount ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Tar bort...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Ta bort</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Account Confirmation Dialog */}
      {deleteConfirmation.show && deleteConfirmation.account && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-red-500 to-red-600 px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="bg-white bg-opacity-20 p-2 rounded-full">
                  <Trash2 className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-white">Ta bort konto</h3>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-5">
              <div className="mb-4">
                <p className="text-gray-700 mb-3">
                  {deleteConfirmation.canDelete
                    ? 'Är du säker på att du vill ta bort följande konto?'
                    : 'Följande konto kan inte raderas:'}
                </p>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <div className="bg-blue-100 text-blue-600 rounded px-2 py-1 text-sm font-mono font-semibold">
                        {deleteConfirmation.account.account_number}
                      </div>
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900">
                        {deleteConfirmation.account.name}
                      </p>
                      {deleteConfirmation.account.description && (
                        <p className="text-sm text-gray-600 mt-1">
                          {deleteConfirmation.account.description}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {!deleteConfirmation.canDelete && deleteConfirmation.blockingReason && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <div className="flex gap-3">
                    <div className="flex-shrink-0">
                      <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-red-800 mb-1">Kan inte raderas</p>
                      <p className="text-sm text-red-700">
                        {deleteConfirmation.blockingReason}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={cancelDeleteAccount}
                disabled={loading}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteConfirmation.canDelete ? 'Avbryt' : 'Stäng'}
              </button>
              {deleteConfirmation.canDelete && (
                <button
                  onClick={confirmDeleteAccount}
                  disabled={loading}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Tar bort...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4" />
                      <span>Ta bort</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
