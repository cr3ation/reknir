import { useState, useEffect } from 'react'
import { companyApi, reportApi } from '@/services/api'
import type { Company, BalanceSheet, IncomeStatement, VATReport, VATPeriod } from '@/types'

type ReportTab = 'balance' | 'income' | 'vat'

export default function Reports() {
  const [company, setCompany] = useState<Company | null>(null)
  const [activeTab, setActiveTab] = useState<ReportTab>('income')
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null)
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null)
  const [vatReport, setVATReport] = useState<VATReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [vatPeriods, setVatPeriods] = useState<VATPeriod[]>([])
  const [selectedPeriod, setSelectedPeriod] = useState<VATPeriod | null>(null)
  const [vatYear, setVatYear] = useState(new Date().getFullYear())

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (company) {
      loadVatPeriods()
    }
  }, [company, vatYear])

  useEffect(() => {
    if (company && selectedPeriod) {
      loadVatReport()
    }
  }, [selectedPeriod])

  const loadData = async () => {
    try {
      setLoading(true)

      // Get first company
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) {
        return
      }

      const comp = companiesRes.data[0]
      setCompany(comp)

      // Load reports
      const [balanceRes, incomeRes] = await Promise.all([
        reportApi.balanceSheet(comp.id),
        reportApi.incomeStatement(comp.id),
      ])

      setBalanceSheet(balanceRes.data)
      setIncomeStatement(incomeRes.data)
    } catch (error) {
      console.error('Failed to load reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadVatPeriods = async () => {
    if (!company) return

    try {
      const periodsRes = await reportApi.vatPeriods(company.id, vatYear)
      setVatPeriods(periodsRes.data.periods)

      // Auto-select the most recent period
      if (periodsRes.data.periods.length > 0) {
        setSelectedPeriod(periodsRes.data.periods[periodsRes.data.periods.length - 1])
      }
    } catch (error) {
      console.error('Failed to load VAT periods:', error)
    }
  }

  const loadVatReport = async () => {
    if (!company || !selectedPeriod) return

    try {
      setLoading(true)
      const vatRes = await reportApi.vatReport(
        company.id,
        selectedPeriod.start_date,
        selectedPeriod.end_date
      )
      setVATReport(vatRes.data)
    } catch (error) {
      console.error('Failed to load VAT report:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!company) {
    return (
      <div className="card">
        <p className="text-gray-600">Inget företag hittat.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount)
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Rapporter</h1>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('income')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'income'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Resultaträkning
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'balance'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Balansräkning
          </button>
          <button
            onClick={() => setActiveTab('vat')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'vat'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Momsrapport
          </button>
        </nav>
      </div>

      {/* Income Statement */}
      {activeTab === 'income' && incomeStatement && (
        <div className="card">
          <h2 className="text-2xl font-bold mb-6">Resultaträkning</h2>

          {/* Revenue */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Intäkter</h3>
            <table className="min-w-full">
              <tbody className="divide-y divide-gray-200">
                {incomeStatement.revenue.accounts.map((account) => (
                  <tr key={account.account_number}>
                    <td className="py-2 text-sm font-mono text-gray-500">
                      {account.account_number}
                    </td>
                    <td className="py-2 text-sm text-gray-900">{account.name}</td>
                    <td className="py-2 text-sm text-right font-mono">
                      {formatCurrency(Math.abs(account.balance))}
                    </td>
                  </tr>
                ))}
                <tr className="border-t-2 border-gray-900">
                  <td colSpan={2} className="py-2 text-sm font-semibold">
                    Summa intäkter
                  </td>
                  <td className="py-2 text-sm text-right font-mono font-semibold">
                    {formatCurrency(Math.abs(incomeStatement.revenue.total))}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Expenses */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Kostnader</h3>
            <table className="min-w-full">
              <tbody className="divide-y divide-gray-200">
                {incomeStatement.expenses.accounts.map((account) => (
                  <tr key={account.account_number}>
                    <td className="py-2 text-sm font-mono text-gray-500">
                      {account.account_number}
                    </td>
                    <td className="py-2 text-sm text-gray-900">{account.name}</td>
                    <td className="py-2 text-sm text-right font-mono">
                      {formatCurrency(account.balance)}
                    </td>
                  </tr>
                ))}
                <tr className="border-t-2 border-gray-900">
                  <td colSpan={2} className="py-2 text-sm font-semibold">
                    Summa kostnader
                  </td>
                  <td className="py-2 text-sm text-right font-mono font-semibold">
                    {formatCurrency(incomeStatement.expenses.total)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Profit/Loss */}
          <div className="border-t-4 border-gray-900 pt-4">
            <div className="flex justify-between items-center">
              <span className="text-xl font-bold">
                {incomeStatement.profit_loss >= 0 ? 'Resultat (vinst)' : 'Resultat (förlust)'}
              </span>
              <span
                className={`text-xl font-bold font-mono ${
                  incomeStatement.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {formatCurrency(Math.abs(incomeStatement.profit_loss))}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Balance Sheet */}
      {activeTab === 'balance' && balanceSheet && (
        <div className="card">
          <h2 className="text-2xl font-bold mb-6">Balansräkning</h2>

          <div className="grid grid-cols-2 gap-8">
            {/* Assets */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Tillgångar</h3>
              <table className="min-w-full">
                <tbody className="divide-y divide-gray-200">
                  {balanceSheet.assets.accounts.map((account) => (
                    <tr key={account.account_number}>
                      <td className="py-2 text-sm font-mono text-gray-500">
                        {account.account_number}
                      </td>
                      <td className="py-2 text-sm text-gray-900">{account.name}</td>
                      <td className="py-2 text-sm text-right font-mono">
                        {formatCurrency(account.balance)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-gray-900">
                    <td colSpan={2} className="py-2 text-sm font-semibold">
                      Summa tillgångar
                    </td>
                    <td className="py-2 text-sm text-right font-mono font-semibold">
                      {formatCurrency(balanceSheet.assets.total)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Equity & Liabilities */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Eget kapital och skulder
              </h3>

              {/* Equity */}
              {balanceSheet.equity.accounts.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Eget kapital</h4>
                  <table className="min-w-full">
                    <tbody className="divide-y divide-gray-200">
                      {balanceSheet.equity.accounts.map((account) => (
                        <tr key={account.account_number}>
                          <td className="py-2 text-sm font-mono text-gray-500">
                            {account.account_number}
                          </td>
                          <td className="py-2 text-sm text-gray-900">{account.name}</td>
                          <td className="py-2 text-sm text-right font-mono">
                            {formatCurrency(Math.abs(account.balance))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Liabilities */}
              {balanceSheet.liabilities.accounts.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Skulder</h4>
                  <table className="min-w-full">
                    <tbody className="divide-y divide-gray-200">
                      {balanceSheet.liabilities.accounts.map((account) => (
                        <tr key={account.account_number}>
                          <td className="py-2 text-sm font-mono text-gray-500">
                            {account.account_number}
                          </td>
                          <td className="py-2 text-sm text-gray-900">{account.name}</td>
                          <td className="py-2 text-sm text-right font-mono">
                            {formatCurrency(Math.abs(account.balance))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="border-t-2 border-gray-900 pt-2">
                <div className="flex justify-between py-2">
                  <span className="text-sm font-semibold">Summa eget kapital och skulder</span>
                  <span className="text-sm font-mono font-semibold">
                    {formatCurrency(
                      Math.abs(balanceSheet.equity.total + balanceSheet.liabilities.total)
                    )}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Balance check */}
          <div className="mt-6 p-4 bg-gray-50 rounded">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Status:</span>
              <span
                className={`text-sm font-medium ${
                  balanceSheet.balanced ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {balanceSheet.balanced ? '✓ Balanserad' : '✗ Ej balanserad'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* VAT Report */}
      {activeTab === 'vat' && (
        <div className="card">
          <h2 className="text-2xl font-bold mb-6">Momsrapport</h2>
          <p className="text-gray-600 mb-4">
            Sammanställning av utgående moms (försäljning) och ingående moms (inköp).
          </p>

          {/* Period Selection */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">År</label>
                <select
                  value={vatYear}
                  onChange={(e) => setVatYear(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {[0, 1, 2, 3, 4].map((offset) => {
                    const year = new Date().getFullYear() - offset
                    return (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    )
                  })}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Period</label>
                <select
                  value={selectedPeriod ? vatPeriods.indexOf(selectedPeriod) : -1}
                  onChange={(e) => {
                    const index = Number(e.target.value)
                    if (index >= 0 && index < vatPeriods.length) {
                      setSelectedPeriod(vatPeriods[index])
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {vatPeriods.map((period, index) => (
                    <option key={index} value={index}>
                      {period.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {selectedPeriod && (
              <div className="mt-2 text-sm text-gray-600">
                Visar period: {selectedPeriod.start_date} till {selectedPeriod.end_date}
              </div>
            )}
          </div>

          {vatReport && (
            <>
          {/* Debug Info */}
          {vatReport.debug_info && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded">
              <h4 className="text-sm font-semibold text-yellow-900 mb-2">Debug-information:</h4>
              <div className="text-sm text-yellow-800 space-y-1">
                <p>Hittade {vatReport.debug_info.total_vat_accounts_found} momskonton totalt</p>
                <p>Utgående momskonton ({vatReport.debug_info.outgoing_vat_accounts.length}):
                  {vatReport.debug_info.outgoing_vat_accounts.length > 0
                    ? vatReport.debug_info.outgoing_vat_accounts.map(a => ` ${a.number}`).join(',')
                    : ' Inga'}
                </p>
                <p>Ingående momskonton ({vatReport.debug_info.incoming_vat_accounts.length}):
                  {vatReport.debug_info.incoming_vat_accounts.length > 0
                    ? vatReport.debug_info.incoming_vat_accounts.map(a => ` ${a.number}`).join(',')
                    : ' Inga'}
                </p>
                <p>Transaktionsgrupper funna: {vatReport.debug_info.transaction_groups_found}</p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-8 mb-6">
            {/* Outgoing VAT */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Utgående moms (försäljning)</h3>
              <table className="min-w-full">
                <tbody className="divide-y divide-gray-200">
                  {vatReport.outgoing_vat.accounts.map((account) => (
                    <tr key={account.account_number}>
                      <td className="py-2 text-sm font-mono text-gray-500">
                        {account.account_number}
                      </td>
                      <td className="py-2 text-sm text-gray-900">{account.name}</td>
                      <td className="py-2 text-sm text-right font-mono">
                        {formatCurrency(account.amount)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-gray-900">
                    <td colSpan={2} className="py-2 text-sm font-semibold">
                      Summa utgående moms
                    </td>
                    <td className="py-2 text-sm text-right font-mono font-semibold">
                      {formatCurrency(vatReport.outgoing_vat.total)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Incoming VAT */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Ingående moms (inköp)</h3>
              <table className="min-w-full">
                <tbody className="divide-y divide-gray-200">
                  {vatReport.incoming_vat.accounts.map((account) => (
                    <tr key={account.account_number}>
                      <td className="py-2 text-sm font-mono text-gray-500">
                        {account.account_number}
                      </td>
                      <td className="py-2 text-sm text-gray-900">{account.name}</td>
                      <td className="py-2 text-sm text-right font-mono">
                        {formatCurrency(account.amount)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t-2 border-gray-900">
                    <td colSpan={2} className="py-2 text-sm font-semibold">
                      Summa ingående moms
                    </td>
                    <td className="py-2 text-sm text-right font-mono font-semibold">
                      {formatCurrency(vatReport.incoming_vat.total)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Net VAT */}
          <div className="border-t-4 border-gray-900 pt-4">
            <div className="flex justify-between items-center">
              <span className="text-xl font-bold">
                {vatReport.pay_or_refund === 'pay' && 'Moms att betala till Skatteverket'}
                {vatReport.pay_or_refund === 'refund' && 'Moms att få tillbaka från Skatteverket'}
                {vatReport.pay_or_refund === 'zero' && 'Ingen moms att betala eller få tillbaka'}
              </span>
              <span
                className={`text-xl font-bold font-mono ${
                  vatReport.pay_or_refund === 'pay'
                    ? 'text-red-600'
                    : vatReport.pay_or_refund === 'refund'
                    ? 'text-green-600'
                    : 'text-gray-600'
                }`}
              >
                {formatCurrency(Math.abs(vatReport.net_vat))}
              </span>
            </div>
          </div>

          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">Om momsrapporten</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Utgående moms kommer från försäljningsfakturor (konto 2610-2619)</li>
              <li>• Ingående moms kommer från inköpsfakturor (konto 2640-2649)</li>
              <li>
                • Nettomoms = Utgående moms - Ingående moms (positivt värde = betala, negativt =
                återfå)
              </li>
              <li>• Använd denna rapport som underlag för din momsdeklaration</li>
            </ul>
          </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
