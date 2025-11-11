import { useState, useEffect } from 'react'
import { companyApi, sie4Api, accountApi, defaultAccountApi, fiscalYearApi } from '@/services/api'
import type { Account, DefaultAccount, VATReportingPeriod, FiscalYear, Company } from '@/types'
import { Plus, Trash2, Calendar, Building2, Edit2, Save, X } from 'lucide-react'
import { useCompany } from '@/contexts/CompanyContext'

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

export default function SettingsPage() {
  const { selectedCompany, setSelectedCompany, companies, loadCompanies } = useCompany()
  const [defaultAccounts, setDefaultAccounts] = useState<DefaultAccount[]>([])
  const [allAccounts, setAllAccounts] = useState<Account[]>([])
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')
  const [showCreateFiscalYear, setShowCreateFiscalYear] = useState(false)
  const [showImportSummary, setShowImportSummary] = useState(false)
  const [importSummary, setImportSummary] = useState<{
    accounts_created: number
    accounts_updated: number
    verifications_created: number
    default_accounts_configured: number
    errors?: string[]
    warnings?: string[]
  } | null>(null)
  const [editingCompany, setEditingCompany] = useState(false)
  const [showCreateCompany, setShowCreateCompany] = useState(false)
  const [companyForm, setCompanyForm] = useState({
    name: '',
    org_number: '',
    fiscal_year_start: new Date().getFullYear() + '-01-01',
    fiscal_year_end: new Date().getFullYear() + '-12-31',
    accounting_basis: 'accrual' as 'accrual' | 'cash',
    vat_reporting_period: 'quarterly' as VATReportingPeriod,
  })

  const getNextFiscalYearDefaults = () => {
    const currentYear = new Date().getFullYear()
    // Find the highest year in existing fiscal years, or use current year
    const nextYear = fiscalYears.length > 0
      ? Math.max(...fiscalYears.map(fy => fy.year)) + 1
      : currentYear

    return {
      year: nextYear,
      label: `${nextYear}`,
      start_date: `${nextYear}-01-01`,
      end_date: `${nextYear}-12-31`,
    }
  }

  const [newFiscalYear, setNewFiscalYear] = useState(getNextFiscalYearDefaults())

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
      const [defaultsRes, accountsRes, fiscalYearsRes] = await Promise.all([
        defaultAccountApi.list(selectedCompany.id).catch(() => ({ data: [] })),
        accountApi.list(selectedCompany.id),
        fiscalYearApi.list(selectedCompany.id).catch(() => ({ data: [] })),
      ])
      setDefaultAccounts(defaultsRes.data)
      setAllAccounts(accountsRes.data)
      setFiscalYears(fiscalYearsRes.data)
    } catch (error: any) {
      console.error('Failed to load data:', error)
      showMessage('Kunde inte ladda data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const showMessage = (msg: string, type: 'success' | 'error' = 'success') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => setMessage(''), 5000)
  }

  const startEditCompany = () => {
    if (!selectedCompany) return
    setCompanyForm({
      name: selectedCompany.name,
      org_number: selectedCompany.org_number,
      fiscal_year_start: selectedCompany.fiscal_year_start,
      fiscal_year_end: selectedCompany.fiscal_year_end,
      accounting_basis: selectedCompany.accounting_basis,
      vat_reporting_period: selectedCompany.vat_reporting_period,
    })
    setEditingCompany(true)
  }

  const cancelEditCompany = () => {
    setEditingCompany(false)
    setCompanyForm({
      name: '',
      org_number: '',
      fiscal_year_start: new Date().getFullYear() + '-01-01',
      fiscal_year_end: new Date().getFullYear() + '-12-31',
      accounting_basis: 'accrual',
      vat_reporting_period: 'quarterly',
    })
  }

  const formatErrorMessage = (error: any): string => {
    // Handle FastAPI validation errors (422)
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      // If detail is an array of validation errors
      if (Array.isArray(detail)) {
        return detail.map((err: any) => `${err.loc.join('.')}: ${err.msg}`).join(', ')
      }
      // If detail is a string
      if (typeof detail === 'string') {
        return detail
      }
      // If detail is an object, try to stringify it
      return JSON.stringify(detail)
    }
    return 'Ett fel uppstod'
  }

  const handleUpdateCompany = async () => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      const response = await companyApi.update(selectedCompany.id, companyForm)
      setSelectedCompany(response.data)
      showMessage('Företagsinformation uppdaterad!', 'success')
      setEditingCompany(false)
      await loadCompanies()
    } catch (error: any) {
      console.error('Failed to update company:', error)
      showMessage(formatErrorMessage(error), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateCompany = async () => {
    try {
      setLoading(true)
      const response = await companyApi.create(companyForm)
      showMessage('Nytt företag skapat!', 'success')
      setShowCreateCompany(false)
      setCompanyForm({
        name: '',
        org_number: '',
        fiscal_year_start: new Date().getFullYear() + '-01-01',
        fiscal_year_end: new Date().getFullYear() + '-12-31',
        accounting_basis: 'accrual',
        vat_reporting_period: 'quarterly',
      })
      await loadCompanies()
      setSelectedCompany(response.data)
    } catch (error: any) {
      console.error('Failed to create company:', error)
      showMessage(formatErrorMessage(error), 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleInitializeDefaults = async () => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      const response = await companyApi.initializeDefaults(selectedCompany.id)
      showMessage(response.data.message, 'success')
      await loadData()
    } catch (error: any) {
      console.error('Failed to initialize defaults:', error)
      showMessage(
        error.response?.data?.detail || 'Kunde inte initialisera standardkonton',
        'error'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleSIE4Import = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCompany) return

    const file = event.target.files?.[0]
    if (!file) return

    try {
      setLoading(true)
      const response = await sie4Api.import(selectedCompany.id, file)

      // Show modal with import summary
      setImportSummary({
        accounts_created: response.data.accounts_created,
        accounts_updated: response.data.accounts_updated,
        verifications_created: response.data.verifications_created,
        default_accounts_configured: response.data.default_accounts_configured,
        errors: response.data.errors || [],
        warnings: response.data.warnings || [],
      })
      setShowImportSummary(true)

      await loadData()
    } catch (error: any) {
      console.error('SIE4 import failed:', error)
      showMessage(error.response?.data?.detail || 'Import misslyckades', 'error')
    } finally {
      setLoading(false)
      // Reset input
      event.target.value = ''
    }
  }

  const handleSIE4Export = async (includeVerifications: boolean) => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      const response = await sie4Api.export(selectedCompany.id, includeVerifications)

      // Create download link
      const blob = new Blob([response.data], { type: 'text/plain' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `reknir_export_${new Date().toISOString().split('T')[0]}.se`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      showMessage('Export lyckades!', 'success')
    } catch (error: any) {
      console.error('SIE4 export failed:', error)
      showMessage('Export misslyckades', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleVATReportingPeriodChange = async (newPeriod: VATReportingPeriod) => {
    if (!selectedCompany) return

    try {
      setLoading(true)
      await companyApi.update(selectedCompany.id, { vat_reporting_period: newPeriod })
      setSelectedCompany({ ...selectedCompany, vat_reporting_period: newPeriod })
      showMessage('Momsredovisningsperiod uppdaterad!', 'success')
    } catch (error: any) {
      console.error('Failed to update VAT reporting period:', error)
      showMessage('Kunde inte uppdatera momsredovisningsperiod', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateFiscalYear = async () => {
    if (!selectedCompany) return

    if (!newFiscalYear.label || !newFiscalYear.start_date || !newFiscalYear.end_date) {
      showMessage('Fyll i alla fält', 'error')
      return
    }

    try {
      setLoading(true)
      await fiscalYearApi.create({
        company_id: selectedCompany.id,
        year: newFiscalYear.year,
        label: newFiscalYear.label,
        start_date: newFiscalYear.start_date,
        end_date: newFiscalYear.end_date,
        is_closed: false,
      })
      showMessage('Räkenskapsår skapat!', 'success')
      await loadData()
      setShowCreateFiscalYear(false)
      // Reset to next year defaults after creating
      setTimeout(() => {
        setNewFiscalYear(getNextFiscalYearDefaults())
      }, 100)
    } catch (error: any) {
      console.error('Failed to create fiscal year:', error)
      showMessage(error.response?.data?.detail || 'Kunde inte skapa räkenskapsår', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteFiscalYear = async (fiscalYearId: number, label: string) => {
    if (!confirm(`Är du säker på att du vill radera räkenskapsåret "${label}"? Verifikationer kommer att kopplas loss.`)) {
      return
    }

    try {
      setLoading(true)
      await fiscalYearApi.delete(fiscalYearId)
      showMessage('Räkenskapsår raderat', 'success')
      await loadData()
    } catch (error: any) {
      console.error('Failed to delete fiscal year:', error)
      showMessage('Kunde inte radera räkenskapsår', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAssignVerifications = async (fiscalYearId: number, label: string) => {
    if (!confirm(`Tilldela alla verifikationer till räkenskapsår "${label}" baserat på transaktionsdatum?`)) {
      return
    }

    try {
      setLoading(true)
      const result = await fiscalYearApi.assignVerifications(fiscalYearId)
      showMessage(result.data.message, 'success')
      await loadData()
    } catch (error: any) {
      console.error('Failed to assign verifications:', error)
      showMessage('Kunde inte tilldela verifikationer', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleYearChange = (year: number) => {
    setNewFiscalYear({
      year,
      label: `${year}`,
      start_date: `${year}-01-01`,
      end_date: `${year}-12-31`,
    })
  }

  const handleToggleCreateForm = () => {
    if (!showCreateFiscalYear) {
      // Opening form - reset to defaults
      setNewFiscalYear(getNextFiscalYearDefaults())
    }
    setShowCreateFiscalYear(!showCreateFiscalYear)
  }

  const getAccountForType = (accountType: string): DefaultAccount | undefined => {
    return defaultAccounts.find((da) => da.account_type === accountType)
  }

  const getAccountDisplay = (accountId: number): string => {
    const account = allAccounts.find((a) => a.id === accountId)
    return account ? `${account.account_number} - ${account.name}` : 'Okänt konto'
  }

  if (!selectedCompany && !loading) {
    return (
      <div className="card">
        <h2 className="text-2xl font-bold mb-4">Företagsinställningar</h2>
        <p className="text-gray-600">
          Inget företag hittat. Skapa ett företag först.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Företagsinställningar</h1>

      {message && (
        <div
          className={`mb-4 p-4 rounded ${
            messageType === 'success'
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          {message}
        </div>
      )}

      {/* Company Management Section */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Building2 className="w-5 h-5" />
            Företagsinformation
          </h2>
          <div className="flex gap-2">
            {!editingCompany && !showCreateCompany && (
              <>
                <button
                  onClick={startEditCompany}
                  disabled={loading}
                  className="btn btn-secondary flex items-center gap-2"
                >
                  <Edit2 className="w-4 h-4" />
                  Redigera
                </button>
                <button
                  onClick={() => setShowCreateCompany(true)}
                  disabled={loading}
                  className="btn btn-primary flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Nytt företag
                </button>
              </>
            )}
          </div>
        </div>

        {/* View Mode */}
        {!editingCompany && !showCreateCompany && selectedCompany && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Företagsnamn</label>
              <p className="text-gray-900">{selectedCompany.name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Organisationsnummer</label>
              <p className="text-gray-900">{selectedCompany.org_number}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Räkenskapsår start</label>
              <p className="text-gray-900">{selectedCompany.fiscal_year_start}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Räkenskapsår slut</label>
              <p className="text-gray-900">{selectedCompany.fiscal_year_end}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Bokföringsmetod</label>
              <p className="text-gray-900">
                {selectedCompany.accounting_basis === 'accrual' ? 'Bokföringsmässiga grunder' : 'Kontantmetoden'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Momsredovisning</label>
              <p className="text-gray-900">
                {selectedCompany.vat_reporting_period === 'monthly' ? 'Månadsvis' :
                 selectedCompany.vat_reporting_period === 'quarterly' ? 'Kvartalsvis' : 'Årlig'}
              </p>
            </div>
          </div>
        )}

        {/* Edit/Create Mode */}
        {(editingCompany || showCreateCompany) && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Företagsnamn *
                </label>
                <input
                  type="text"
                  value={companyForm.name}
                  onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Organisationsnummer *
                </label>
                <input
                  type="text"
                  value={companyForm.org_number}
                  onChange={(e) => setCompanyForm({ ...companyForm, org_number: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="XXXXXX-XXXX"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Räkenskapsår start *
                </label>
                <input
                  type="date"
                  value={companyForm.fiscal_year_start}
                  onChange={(e) => setCompanyForm({ ...companyForm, fiscal_year_start: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Räkenskapsår slut *
                </label>
                <input
                  type="date"
                  value={companyForm.fiscal_year_end}
                  onChange={(e) => setCompanyForm({ ...companyForm, fiscal_year_end: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Bokföringsmetod
                </label>
                <select
                  value={companyForm.accounting_basis}
                  onChange={(e) => setCompanyForm({ ...companyForm, accounting_basis: e.target.value as 'accrual' | 'cash' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="accrual">Bokföringsmässiga grunder</option>
                  <option value="cash">Kontantmetoden</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Momsredovisningsperiod
                </label>
                <select
                  value={companyForm.vat_reporting_period}
                  onChange={(e) => setCompanyForm({ ...companyForm, vat_reporting_period: e.target.value as VATReportingPeriod })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="monthly">Månadsvis</option>
                  <option value="quarterly">Kvartalsvis</option>
                  <option value="yearly">Årlig</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t">
              <button
                onClick={editingCompany ? handleUpdateCompany : handleCreateCompany}
                disabled={loading || !companyForm.name || !companyForm.org_number}
                className="btn btn-primary flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                {editingCompany ? 'Spara ändringar' : 'Skapa företag'}
              </button>
              <button
                onClick={editingCompany ? cancelEditCompany : () => setShowCreateCompany(false)}
                disabled={loading}
                className="btn btn-secondary flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                Avbryt
              </button>
            </div>
          </div>
        )}

        {/* List of all companies */}
        {companies.length > 1 && !editingCompany && !showCreateCompany && (
          <div className="mt-6 pt-6 border-t">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Alla företag ({companies.length})</h3>
            <div className="space-y-2">
              {companies.map((company) => (
                <div
                  key={company.id}
                  className={`flex items-center justify-between p-3 rounded-lg border ${
                    selectedCompany?.id === company.id
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div>
                    <p className="font-medium text-gray-900">{company.name}</p>
                    <p className="text-sm text-gray-600">Org.nr: {company.org_number}</p>
                  </div>
                  {selectedCompany?.id !== company.id && (
                    <button
                      onClick={() => setSelectedCompany(company)}
                      className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                    >
                      Välj
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* VAT Reporting Period Section */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Momsredovisningsperiod</h2>
        <p className="text-gray-600 mb-4">
          Välj hur ofta ditt företag ska redovisa moms till Skatteverket.
        </p>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            {/* Monthly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'monthly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="monthly"
                checked={selectedCompany?.vat_reporting_period === 'monthly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Månadsvis</div>
                <div className="text-sm text-gray-600 mt-1">
                  För företag med omsättning över 40 miljoner SEK/år. Deklarera varje månad.
                </div>
              </div>
            </label>

            {/* Quarterly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'quarterly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="quarterly"
                checked={selectedCompany?.vat_reporting_period === 'quarterly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Kvartalsvis (Rekommenderat)</div>
                <div className="text-sm text-gray-600 mt-1">
                  Vanligast för små och medelstora företag. Deklarera varje kvartal.
                </div>
              </div>
            </label>

            {/* Yearly Option */}
            <label className={`flex items-start p-4 border-2 rounded-lg cursor-pointer transition-colors ${
              selectedCompany?.vat_reporting_period === 'yearly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="yearly"
                checked={selectedCompany?.vat_reporting_period === 'yearly'}
                onChange={(e) => handleVATReportingPeriodChange(e.target.value as VATReportingPeriod)}
                disabled={loading}
                className="mt-1 mr-3"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">Årlig</div>
                <div className="text-sm text-gray-600 mt-1">
                  För företag med omsättning under 1 miljon SEK/år. Deklarera en gång per år.
                </div>
              </div>
            </label>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <p className="text-sm text-blue-800">
              <strong>OBS:</strong> Kontakta Skatteverket om du är osäker på vilken redovisningsperiod
              som gäller för ditt företag. Detta påverkar hur ofta du måste lämna momsdeklaration.
            </p>
          </div>
        </div>
      </div>

      {/* SIE4 Import/Export Section */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">SIE4 Import/Export</h2>
        <p className="text-gray-600 mb-4">
          Importera eller exportera kontoplan och verifikationer i SIE4-format.
        </p>

        <div className="space-y-4">
          {/* Import */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Importera SIE4-fil
            </label>
            <input
              type="file"
              accept=".se,.si"
              onChange={handleSIE4Import}
              disabled={loading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100
                disabled:opacity-50"
            />
            <p className="mt-1 text-sm text-gray-500">
              Konton och ingående balanser kommer importeras och standardkonton konfigureras automatiskt.
            </p>
          </div>

          {/* Export */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Exportera till SIE4
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => handleSIE4Export(true)}
                disabled={loading}
                className="btn btn-primary"
              >
                Exportera med verifikationer
              </button>
              <button
                onClick={() => handleSIE4Export(false)}
                disabled={loading}
                className="btn btn-secondary"
              >
                Endast kontoplan
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Default Accounts Section */}
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
        ) : defaultAccounts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="mb-4">Inga standardkonton konfigurerade.</p>
            <p className="text-sm">
              Klicka på "Initiera automatiskt" för att automatiskt konfigurera standardkonton baserat på din kontoplan.
            </p>
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
                      <span className="text-sm text-gray-700">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                      <span className="text-sm font-mono">
                        {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : '-'}
                      </span>
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
                      <span className="text-sm text-gray-700">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                      <span className="text-sm font-mono">
                        {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : '-'}
                      </span>
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
                      <span className="text-sm text-gray-700">{DEFAULT_ACCOUNT_LABELS[type]}</span>
                      <span className="text-sm font-mono">
                        {defaultAcc ? getAccountDisplay(defaultAcc.account_id) : '-'}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Fiscal Years Section */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Räkenskapsår</h2>
          <button
            onClick={handleToggleCreateForm}
            disabled={loading}
            className="btn btn-primary inline-flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            Lägg till räkenskapsår
          </button>
        </div>

        <p className="text-gray-600 mb-4">
          Hantera räkenskapsår för att kunna filtrera verifikationer och rapporter per period.
        </p>

        {/* Create Fiscal Year Form */}
        {showCreateFiscalYear && (
          <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
            <h3 className="font-medium mb-3">Skapa nytt räkenskapsår</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">År</label>
                <input
                  type="number"
                  value={newFiscalYear.year}
                  onChange={(e) => handleYearChange(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Benämning</label>
                <input
                  type="text"
                  placeholder="t.ex. 2024"
                  value={newFiscalYear.label}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, label: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Automatiskt ifylld med året</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Startdatum</label>
                <input
                  type="date"
                  value={newFiscalYear.start_date}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, start_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Standard: 1 januari</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Slutdatum</label>
                <input
                  type="date"
                  value={newFiscalYear.end_date}
                  onChange={(e) => setNewFiscalYear({ ...newFiscalYear, end_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="text-xs text-gray-500 mt-1">Standard: 31 december</p>
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={handleCreateFiscalYear}
                disabled={loading}
                className="btn btn-primary"
              >
                Skapa
              </button>
              <button
                onClick={() => setShowCreateFiscalYear(false)}
                disabled={loading}
                className="btn btn-secondary"
              >
                Avbryt
              </button>
            </div>
          </div>
        )}

        {/* Fiscal Years List */}
        {fiscalYears.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Calendar className="w-12 h-12 mx-auto mb-3 text-gray-400" />
            <p className="mb-4">Inga räkenskapsår konfigurerade.</p>
            <p className="text-sm">
              Skapa ett räkenskapsår för att kunna se verifikationer och rapporter per period.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {fiscalYears.map((fy) => (
              <div
                key={fy.id}
                className={`flex items-center justify-between p-3 border rounded-lg ${
                  fy.is_current ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{fy.label}</span>
                    {fy.is_current && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded">
                        Aktuellt
                      </span>
                    )}
                    {fy.is_closed && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded">
                        Stängt
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-600 mt-1">
                    {fy.start_date} till {fy.end_date}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAssignVerifications(fy.id, fy.label)}
                    disabled={loading}
                    className="btn btn-secondary text-sm"
                  >
                    Tilldela verifikationer
                  </button>
                  <button
                    onClick={() => handleDeleteFiscalYear(fy.id, fy.label)}
                    disabled={loading}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
          <p className="text-sm text-blue-800">
            <strong>Tips:</strong> Skapa räkenskapsår för varje år du har bokfört. Använd "Tilldela verifikationer" för att
            automatiskt koppla verifikationer till rätt år baserat på transaktionsdatum.
          </p>
        </div>
      </div>

      {/* Import Summary Modal */}
      {showImportSummary && importSummary && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center mb-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="ml-4 text-lg font-semibold text-gray-900">Import Lyckades!</h3>
              </div>

              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Importsammanfattning:</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Konton skapade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.accounts_created}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Konton uppdaterade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.accounts_updated}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
                    <span className="text-sm text-gray-700">Verifikationer importerade:</span>
                    <span className="text-sm font-semibold text-blue-900">{importSummary.verifications_created}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-sm text-gray-700">Standardkonton konfigurerade:</span>
                    <span className="text-sm font-semibold text-gray-900">{importSummary.default_accounts_configured}</span>
                  </div>
                </div>

                {/* Errors */}
                {importSummary.errors && importSummary.errors.length > 0 && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded">
                    <h5 className="text-sm font-medium text-red-900 mb-2">Fel:</h5>
                    <ul className="list-disc list-inside space-y-1">
                      {importSummary.errors.map((error, idx) => (
                        <li key={idx} className="text-sm text-red-800">{error}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warnings */}
                {importSummary.warnings && importSummary.warnings.length > 0 && (
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                    <h5 className="text-sm font-medium text-yellow-900 mb-2">Varningar:</h5>
                    <ul className="list-disc list-inside space-y-1">
                      {importSummary.warnings.map((warning, idx) => (
                        <li key={idx} className="text-sm text-yellow-800">{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {importSummary.verifications_created > 0 && (
                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
                    <p className="text-sm text-blue-800">
                      <strong>Tips:</strong> Glöm inte att tilldela verifikationerna till räkenskapsår!
                      Scrolla ner till "Räkenskapsår" och klicka "Tilldela verifikationer".
                    </p>
                  </div>
                )}
              </div>

              <button
                onClick={() => setShowImportSummary(false)}
                className="w-full btn btn-primary"
              >
                Stäng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
