import { useState } from 'react'
import { companyApi, fiscalYearApi } from '@/services/api'
import { authService } from '@/services/authService'
import { useAuth } from '@/contexts/AuthContext'
import { CheckCircle, Building2, Calendar, BookOpen, UserPlus } from 'lucide-react'
import { AccountingBasis, VATReportingPeriod } from '@/types'

type SetupStep = 'admin-user' | 'company' | 'fiscal-year' | 'chart-of-accounts' | 'complete'

export default function Setup() {
  const { login } = useAuth()
  const [currentStep, setCurrentStep] = useState<SetupStep>('admin-user')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Admin user data
  const [adminData, setAdminData] = useState({
    full_name: '',
    email: '',
    password: '',
    confirmPassword: '',
  })

  // Company data
  const currentYear = new Date().getFullYear()
  const [companyData, setCompanyData] = useState({
    name: '',
    org_number: '',
    vat_number: '',
    address: '',
    postal_code: '',
    city: '',
    phone: '',
    email: '',
    accounting_basis: AccountingBasis.ACCRUAL,
    vat_reporting_period: VATReportingPeriod.QUARTERLY,
    is_vat_registered: true,
  })

  // Fiscal year data
  const [fiscalYearData, setFiscalYearData] = useState({
    year: currentYear,
    label: `${currentYear}`,
    start_date: `${currentYear}-01-01`,
    end_date: `${currentYear}-12-31`,
    is_closed: false,
  })

  // Created IDs
  const [companyId, setCompanyId] = useState<number | null>(null)
  const [fiscalYearId, setFiscalYearId] = useState<number | null>(null)

  // Chart of accounts choice
  const [importBAS, setImportBAS] = useState<boolean | null>(null)

  // Step 1: Create Admin User
  const handleAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validate passwords match
    if (adminData.password !== adminData.confirmPassword) {
      setError('Lösenorden matchar inte')
      return
    }

    // Validate password length
    if (adminData.password.length < 8) {
      setError('Lösenordet måste vara minst 8 tecken')
      return
    }

    setLoading(true)

    try {
      // Register the admin user
      await authService.register({
        email: adminData.email,
        password: adminData.password,
        full_name: adminData.full_name,
      })

      // Login immediately after registration
      await login(adminData.email, adminData.password)

      setCurrentStep('company')
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError('En användare finns redan i systemet. Logga in istället.')
      } else {
        setError(err.response?.data?.detail || 'Kunde inte skapa användare')
      }
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Create Company
  const handleCompanySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await companyApi.create({
        ...companyData,
        // Temporary fiscal year dates (will be replaced by actual fiscal year)
        fiscal_year_start: fiscalYearData.start_date,
        fiscal_year_end: fiscalYearData.end_date,
      })
      setCompanyId(response.data.id)
      setCurrentStep('fiscal-year')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Kunde inte skapa företag')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Create Fiscal Year
  const handleFiscalYearSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validate 12-month period
    const start = new Date(fiscalYearData.start_date)
    const end = new Date(fiscalYearData.end_date)
    const diffMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth())

    if (diffMonths < 11 || diffMonths > 12) {
      setError('Räkenskapsåret måste vara cirka 12 månader')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fiscalYearApi.create({
        company_id: companyId!,
        ...fiscalYearData,
      })
      setFiscalYearId(response.data.id)
      setCurrentStep('chart-of-accounts')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Kunde inte skapa räkenskapsår')
    } finally {
      setLoading(false)
    }
  }

  // Step 3: Import Chart of Accounts (or skip)
  const handleChartOfAccountsChoice = async (choice: boolean) => {
    setImportBAS(choice)
    setLoading(true)
    setError(null)

    try {
      if (choice) {
        // Seed BAS accounts for this fiscal year
        await companyApi.seedBas(companyId!, fiscalYearId!)

        // Initialize default accounts
        await companyApi.initializeDefaults(companyId!, fiscalYearId!)

        // Seed posting templates
        try {
          await companyApi.seedTemplates(companyId!)
        } catch {
          console.warn('Failed to seed posting templates, but continuing...')
        }
      }

      setCurrentStep('complete')

      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        window.location.href = '/'
      }, 2000)

    } catch (err: any) {
      console.error('Failed to seed data:', err)
      setError(`Varning: ${err.message || 'Kontoplanen kunde inte importeras automatiskt'}. Du kan göra det manuellt i inställningar.`)

      // Still proceed to complete after showing error
      setTimeout(() => {
        setCurrentStep('complete')
        setTimeout(() => {
          window.location.href = '/'
        }, 2000)
      }, 3000)
    } finally {
      setLoading(false)
    }
  }

  // Render progress indicator
  const steps = [
    { id: 'admin-user', label: 'Administratör', icon: UserPlus },
    { id: 'company', label: 'Företag', icon: Building2 },
    { id: 'fiscal-year', label: 'Räkenskapsår', icon: Calendar },
    { id: 'chart-of-accounts', label: 'Kontoplan', icon: BookOpen },
  ]

  const currentStepIndex = steps.findIndex(s => s.id === currentStep)

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-3xl w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Välkommen till Reknir</h1>
          <p className="text-gray-600">Låt oss sätta upp ditt bokföringssystem</p>
        </div>

        {/* Progress Steps */}
        {currentStep !== 'complete' && (
          <div className="mb-8">
            {/* Step circles and labels */}
            <div className="grid grid-cols-4 gap-0">
              {steps.map((step, index) => {
                const Icon = step.icon
                const isActive = index === currentStepIndex
                const isCompleted = index < currentStepIndex

                return (
                  <div key={step.id} className="flex flex-col items-center relative">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                      isCompleted ? 'bg-green-500' : isActive ? 'bg-indigo-600' : 'bg-gray-300'
                    } text-white mb-2 z-10`}>
                      {isCompleted ? (
                        <CheckCircle className="w-6 h-6" />
                      ) : (
                        <Icon className="w-6 h-6" />
                      )}
                    </div>
                    <span className={`text-sm font-medium text-center whitespace-nowrap ${
                      isActive ? 'text-indigo-600' : isCompleted ? 'text-green-600' : 'text-gray-400'
                    }`}>
                      {step.label}
                    </span>
                    {/* Connecting line to next step */}
                    {index < steps.length - 1 && (
                      <div
                        className={`absolute top-6 h-1 ${isCompleted ? 'bg-green-500' : 'bg-gray-300'}`}
                        style={{ left: '50%', width: '100%' }}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Step 1: Admin User */}
        {currentStep === 'admin-user' && (
          <form onSubmit={handleAdminSubmit} className="space-y-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <h3 className="font-medium text-blue-900 mb-2">Skapa ditt administratörskonto</h3>
              <p className="text-sm text-blue-800">
                Detta konto kommer att ha full tillgång till systemet och kan bjuda in andra användare.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Namn *
                </label>
                <input
                  type="text"
                  required
                  value={adminData.full_name}
                  onChange={(e) => setAdminData({ ...adminData, full_name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Ditt fullständiga namn"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  E-postadress *
                </label>
                <input
                  type="email"
                  required
                  value={adminData.email}
                  onChange={(e) => setAdminData({ ...adminData, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="din@epost.se"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Lösenord *
                </label>
                <input
                  type="password"
                  required
                  value={adminData.password}
                  onChange={(e) => setAdminData({ ...adminData, password: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Minst 8 tecken"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Bekräfta lösenord *
                </label>
                <input
                  type="password"
                  required
                  value={adminData.confirmPassword}
                  onChange={(e) => setAdminData({ ...adminData, confirmPassword: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="Skriv lösenordet igen"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 font-medium"
            >
              {loading ? 'Skapar konto...' : 'Nästa: Skapa företag'}
            </button>
          </form>
        )}

        {/* Step 2: Company Info */}
        {currentStep === 'company' && (
          <form onSubmit={handleCompanySubmit} className="space-y-6">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Företagsnamn *
                </label>
                <input
                  type="text"
                  required
                  value={companyData.name}
                  onChange={(e) => setCompanyData({ ...companyData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  placeholder="t.ex. Min Företag AB"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Organisationsnummer *
                </label>
                <input
                  type="text"
                  required
                  value={companyData.org_number}
                  onChange={(e) => {
                    // Remove all non-digits
                    let value = e.target.value.replace(/[^0-9]/g, '')

                    // Limit to 10 digits
                    if (value.length > 10) {
                      value = value.slice(0, 10)
                    }

                    // Add dash after 6 digits
                    if (value.length > 6) {
                      value = value.slice(0, 6) + '-' + value.slice(6)
                    }

                    setCompanyData({ ...companyData, org_number: value })
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono tracking-wider"
                  placeholder="XXXXXX-XXXX"
                  maxLength={11}
                />
              </div>

              {/* VAT Registration */}
              <div className="mb-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={companyData.is_vat_registered}
                    onChange={(e) => setCompanyData({ ...companyData, is_vat_registered: e.target.checked })}
                    className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    Företaget är momsregistrerat
                  </span>
                </label>
                <p className="mt-1 text-xs text-gray-500 ml-6">
                  Avmarkera om företaget inte är registrerat för moms hos Skatteverket
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Redovisningsmetod
                  </label>
                  <div className="relative">
                    <select
                      value={companyData.accounting_basis}
                      onChange={(e) => setCompanyData({ ...companyData, accounting_basis: e.target.value as AccountingBasis })}
                      className="w-full px-4 py-2.5 pr-10 border border-gray-300 rounded-lg appearance-none bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 cursor-pointer text-gray-900 font-medium"
                    >
                      <option value="accrual">Fakturametoden</option>
                      <option value="cash">Kontantmetoden</option>
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                      <svg className="h-5 w-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                </div>

                <div>
                  <label className={`block text-sm font-medium mb-2 ${companyData.is_vat_registered ? 'text-gray-700' : 'text-gray-400'}`}>
                    Momsperiod
                  </label>
                  <div className="relative">
                    <select
                      value={companyData.vat_reporting_period}
                      onChange={(e) => setCompanyData({ ...companyData, vat_reporting_period: e.target.value as any })}
                      disabled={!companyData.is_vat_registered}
                      className={`w-full px-4 py-2.5 pr-10 border border-gray-300 rounded-lg appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-medium ${
                        companyData.is_vat_registered
                          ? 'bg-white cursor-pointer text-gray-900'
                          : 'bg-gray-100 cursor-not-allowed text-gray-400'
                      }`}
                    >
                      <option value="monthly">Månadsvis</option>
                      <option value="quarterly">Kvartalsvis</option>
                      <option value="yearly">Årsvis</option>
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                      <svg className={`h-5 w-5 ${companyData.is_vat_registered ? 'text-gray-400' : 'text-gray-300'}`} viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                  {!companyData.is_vat_registered && (
                    <p className="mt-1 text-xs text-gray-400">
                      Ej relevant för företag som inte är momsregistrerade
                    </p>
                  )}
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 font-medium"
            >
              {loading ? 'Skapar företag...' : 'Nästa: Ange räkenskapsår'}
            </button>
          </form>
        )}

        {/* Step 2: Fiscal Year */}
        {currentStep === 'fiscal-year' && (
          <form onSubmit={handleFiscalYearSubmit} className="space-y-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <h3 className="font-medium text-blue-900 mb-2">Ange start- och slutdatum för ditt första räkenskapsår</h3>
              <p className="text-sm text-blue-800">
                Systemet föreslår innevarande år (1 januari - 31 december), men du kan ange vilket datum som helst.
                Perioden måste vara cirka 12 månader.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Startdatum *
                </label>
                <input
                  type="date"
                  required
                  value={fiscalYearData.start_date}
                  onChange={(e) => setFiscalYearData({ ...fiscalYearData, start_date: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Slutdatum *
                </label>
                <input
                  type="date"
                  required
                  value={fiscalYearData.end_date}
                  onChange={(e) => setFiscalYearData({ ...fiscalYearData, end_date: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Etikett (valfri)
              </label>
              <input
                type="text"
                value={fiscalYearData.label}
                onChange={(e) => setFiscalYearData({ ...fiscalYearData, label: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder={`t.ex. ${currentYear}`}
              />
              <p className="mt-1 text-sm text-gray-500">
                Används för att identifiera räkenskapsåret i systemet
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 font-medium"
            >
              {loading ? 'Skapar räkenskapsår...' : 'Nästa: Välj kontoplan'}
            </button>
          </form>
        )}

        {/* Step 3: Chart of Accounts */}
        {currentStep === 'chart-of-accounts' && (
          <div className="space-y-6">
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Vill du skapa en grundläggande kontoplan baserad på BAS2024?
              </h2>
              <p className="text-gray-600">
                BAS är den svenska standardkontoplanen som används av de flesta företag
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Option 1: Yes, import BAS */}
              <button
                onClick={() => handleChartOfAccountsChoice(true)}
                disabled={loading}
                className="p-6 border-2 border-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors text-left disabled:opacity-50"
              >
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
                      <CheckCircle className="w-6 h-6 text-indigo-600" />
                    </div>
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Ja, skapa kontoplan
                    </h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Systemet skapar automatiskt:
                    </p>
                    <ul className="text-sm text-gray-600 space-y-1">
                      <li>✓ 43 BAS-konton från BAS2024</li>
                      <li>✓ Standardkonton för moms</li>
                      <li>✓ Konteringsmallar</li>
                      <li>✓ Du är redo att börja!</li>
                    </ul>
                  </div>
                </div>
              </button>

              {/* Option 2: No, skip */}
              <button
                onClick={() => handleChartOfAccountsChoice(false)}
                disabled={loading}
                className="p-6 border-2 border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
              >
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
                      <BookOpen className="w-6 h-6 text-gray-600" />
                    </div>
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Nej, hoppa över
                    </h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Om du väljer detta:
                    </p>
                    <ul className="text-sm text-gray-600 space-y-1">
                      <li>• Inga konton skapas</li>
                      <li>• Du lägger in konton själv</li>
                      <li>• Kan importera BAS senare i inställningar</li>
                    </ul>
                  </div>
                </div>
              </button>
            </div>

            {loading && (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-2"></div>
                <p className="text-gray-600">
                  {importBAS ? 'Importerar BAS-kontoplan...' : 'Slutför installation...'}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Complete */}
        {currentStep === 'complete' && (
          <div className="text-center py-8">
            <div className="text-green-500 mb-4">
              <CheckCircle className="w-20 h-20 mx-auto" />
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2">Klart!</h2>
            <p className="text-gray-600 mb-4">
              Ditt företag har skapats och är redo att användas
            </p>
            {importBAS && (
              <p className="text-sm text-gray-500">
                BAS2024-kontoplanen har importerats med 43 konton
              </p>
            )}
            <p className="text-sm text-gray-400 mt-4">
              Omdirigerar till instrumentpanelen...
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
