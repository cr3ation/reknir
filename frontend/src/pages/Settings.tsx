import { useState, useEffect } from 'react'
import { companyApi, sie4Api, accountApi, defaultAccountApi, fiscalYearApi } from '@/services/api'
import type { Account, DefaultAccount, Company, VATReportingPeriod, FiscalYear } from '@/types'
import { Plus, Trash2, Calendar } from 'lucide-react'

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
  const [company, setCompany] = useState<Company | null>(null)
  const [defaultAccounts, setDefaultAccounts] = useState<DefaultAccount[]>([])
  const [allAccounts, setAllAccounts] = useState<Account[]>([])
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')
  const [showCreateFiscalYear, setShowCreateFiscalYear] = useState(false)

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
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)

      // Get first company (single-company mode for MVP)
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) {
        showMessage('Inget företag hittat. Skapa ett företag först.', 'error')
        setLoading(false)
        return
      }

      const comp = companiesRes.data[0]
      setCompany(comp)

      const [defaultsRes, accountsRes, fiscalYearsRes] = await Promise.all([
        defaultAccountApi.list(comp.id).catch(() => ({ data: [] })),
        accountApi.list(comp.id),
        fiscalYearApi.list(comp.id).catch(() => ({ data: [] })),
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

  const handleInitializeDefaults = async () => {
    if (!company) return

    try {
      setLoading(true)
      const response = await companyApi.initializeDefaults(company.id)
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
    if (!company) return

    const file = event.target.files?.[0]
    if (!file) return

    try {
      setLoading(true)
      const response = await sie4Api.import(company.id, file)

      // Build detailed summary message
      const parts = []
      if (response.data.accounts_created > 0) {
        parts.push(`${response.data.accounts_created} konton skapade`)
      }
      if (response.data.accounts_updated > 0) {
        parts.push(`${response.data.accounts_updated} konton uppdaterade`)
      }
      if (response.data.verifications_created > 0) {
        parts.push(`${response.data.verifications_created} verifikationer importerade`)
      }
      if (response.data.default_accounts_configured > 0) {
        parts.push(`${response.data.default_accounts_configured} standardkonton konfigurerade`)
      }

      const summary = parts.length > 0 ? parts.join(', ') : 'Inga ändringar'
      showMessage(`Import lyckades! ${summary}`, 'success')

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
    if (!company) return

    try {
      setLoading(true)
      const response = await sie4Api.export(company.id, includeVerifications)

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
    if (!company) return

    try {
      setLoading(true)
      await companyApi.update(company.id, { vat_reporting_period: newPeriod })
      setCompany({ ...company, vat_reporting_period: newPeriod })
      showMessage('Momsredovisningsperiod uppdaterad!', 'success')
    } catch (error: any) {
      console.error('Failed to update VAT reporting period:', error)
      showMessage('Kunde inte uppdatera momsredovisningsperiod', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateFiscalYear = async () => {
    if (!company) return

    if (!newFiscalYear.label || !newFiscalYear.start_date || !newFiscalYear.end_date) {
      showMessage('Fyll i alla fält', 'error')
      return
    }

    try {
      setLoading(true)
      await fiscalYearApi.create({
        company_id: company.id,
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

  if (!company && !loading) {
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
              company?.vat_reporting_period === 'monthly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="monthly"
                checked={company?.vat_reporting_period === 'monthly'}
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
              company?.vat_reporting_period === 'quarterly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="quarterly"
                checked={company?.vat_reporting_period === 'quarterly'}
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
              company?.vat_reporting_period === 'yearly'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="vat_period"
                value="yearly"
                checked={company?.vat_reporting_period === 'yearly'}
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
    </div>
  )
}
