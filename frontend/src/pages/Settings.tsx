import { useState, useEffect } from 'react'
import { companyApi, sie4Api, accountApi, defaultAccountApi } from '@/services/api'
import type { Account, DefaultAccount, Company, VATReportingPeriod } from '@/types'

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
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')

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

      const [defaultsRes, accountsRes] = await Promise.all([
        defaultAccountApi.list(comp.id).catch(() => ({ data: [] })),
        accountApi.list(comp.id),
      ])
      setDefaultAccounts(defaultsRes.data)
      setAllAccounts(accountsRes.data)
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
      showMessage(
        `Import lyckades! ${response.data.accounts_created} konton skapade, ${response.data.default_accounts_configured} standardkonton konfigurerade.`,
        'success'
      )
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
    </div>
  )
}
