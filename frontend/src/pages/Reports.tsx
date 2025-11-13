import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { companyApi, reportApi } from '@/services/api'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import type { Company, BalanceSheet, IncomeStatement, GeneralLedger, VATReport, VATPeriod } from '@/types'

type ReportTab = 'balance' | 'income' | 'general-ledger' | 'vat'

export default function Reports() {
  const [company, setCompany] = useState<Company | null>(null)
  const [activeTab, setActiveTab] = useState<ReportTab>('income')
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null)
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null)
  const [generalLedger, setGeneralLedger] = useState<GeneralLedger | null>(null)
  const [vatReport, setVATReport] = useState<VATReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [vatPeriods, setVatPeriods] = useState<VATPeriod[]>([])
  const [selectedPeriod, setSelectedPeriod] = useState<VATPeriod | null>(null)
  const [vatYear, setVatYear] = useState(new Date().getFullYear())
  const [excludeVatSettlements, setExcludeVatSettlements] = useState(true)
  const [showVerificationsModal, setShowVerificationsModal] = useState(false)
  const { selectedFiscalYear, loadFiscalYears } = useFiscalYear()

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (company) {
      loadFiscalYears(company.id)
      loadVatPeriods()
    }
  }, [company, vatYear])

  useEffect(() => {
    if (company && selectedPeriod) {
      loadVatReport()
    }
  }, [selectedPeriod, excludeVatSettlements])

  useEffect(() => {
    if (company && selectedFiscalYear && activeTab === 'general-ledger') {
      loadGeneralLedger()
    }
  }, [company, selectedFiscalYear, activeTab])

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
        selectedPeriod.end_date,
        excludeVatSettlements
      )
      setVATReport(vatRes.data)
    } catch (error) {
      console.error('Failed to load VAT report:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadGeneralLedger = async () => {
    if (!company || !selectedFiscalYear) return

    try {
      setLoading(true)
      const ledgerRes = await reportApi.generalLedger(company.id, selectedFiscalYear.id)
      setGeneralLedger(ledgerRes.data)
    } catch (error) {
      console.error('Failed to load general ledger:', error)
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
            onClick={() => setActiveTab('general-ledger')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'general-ledger'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Huvudbok
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

      {/* General Ledger */}
      {activeTab === 'general-ledger' && generalLedger && (
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold">Huvudbok</h2>
              <p className="text-sm text-gray-600 mt-1">
                Period: {new Date(generalLedger.start_date).toLocaleDateString('sv-SE')} - {new Date(generalLedger.end_date).toLocaleDateString('sv-SE')}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">Antal konton: {generalLedger.account_count}</p>
            </div>
          </div>

          {generalLedger.accounts.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Inga transaktioner för vald period</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Konto</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Kontonamn</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">IB</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Debet</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Kredit</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">UB</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Trans</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {generalLedger.accounts.map((account, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono text-gray-900 whitespace-nowrap">
                        <Link
                          to={`/accounts/${account.account_number}/ledger`}
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {account.account_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {account.account_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono whitespace-nowrap text-gray-600">
                        {formatCurrency(account.opening_balance)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono whitespace-nowrap">
                        {account.period_debit > 0 ? formatCurrency(account.period_debit) : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono whitespace-nowrap">
                        {account.period_credit > 0 ? formatCurrency(account.period_credit) : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono whitespace-nowrap font-semibold">
                        {formatCurrency(account.closing_balance)}
                      </td>
                      <td className="px-4 py-3 text-sm text-center text-gray-500">
                        {account.transaction_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
            <div className="mt-4 pt-4 border-t border-gray-300">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={excludeVatSettlements}
                  onChange={(e) => setExcludeVatSettlements(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm font-medium text-gray-700">
                  Exkludera momsavräkningar
                </span>
              </label>
              <p className="ml-6 mt-1 text-xs text-gray-500">
                Visa endast moms från affärstransaktioner, utan momsdeklarationer som nollställer momskontona
              </p>
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
              <div className="text-sm text-yellow-800 space-y-2">
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

                {vatReport.debug_info.accounts_with_transactions && vatReport.debug_info.accounts_with_transactions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-yellow-300">
                    <p className="font-semibold mb-2">⚠️ Konton som HAR transaktioner men INTE räknas som moms:</p>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      {vatReport.debug_info.accounts_with_transactions.map((acc, idx) => (
                        <li key={idx}>
                          <strong>{acc.number}</strong> - {acc.name}
                          <span className="ml-2 text-xs">
                            (Debet: {formatCurrency(acc.debit)}, Kredit: {formatCurrency(acc.credit)})
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {vatReport.debug_info.verifications && vatReport.debug_info.verifications.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-yellow-300">
                    <button
                      onClick={() => setShowVerificationsModal(true)}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      Visa alla {vatReport.debug_info.verifications.length} verifikationer med moms
                    </button>
                  </div>
                )}
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

          {/* SKV 3800 Declaration Form */}
          {vatReport.skv_3800 && (
            <div className="mt-8 p-6 bg-green-50 border-2 border-green-300 rounded-lg">
              <h3 className="text-xl font-bold text-green-900 mb-4">
                📋 Momsdeklaration SKV 3800 - Rutor att fylla i
              </h3>
              <p className="text-sm text-green-800 mb-4">
                Använd dessa siffror när du fyller i din momsdeklaration på Skatteverket.se
              </p>

              <div className="space-y-4">
                {/* 25% VAT */}
                {vatReport.skv_3800.outgoing_25.vat > 0 && (
                  <div className="bg-white p-4 rounded border border-green-200">
                    <h4 className="font-semibold text-gray-900 mb-2">Moms 25%</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_25.box_sales}: Försäljning 25%
                        </span>
                        <p className="text-lg font-mono font-bold">
                          {formatCurrency(vatReport.skv_3800.outgoing_25.sales)}
                        </p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_25.box_vat}: Utgående moms 25%
                        </span>
                        <p className="text-lg font-mono font-bold text-green-700">
                          {formatCurrency(vatReport.skv_3800.outgoing_25.vat)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* 12% VAT */}
                {vatReport.skv_3800.outgoing_12.vat > 0 && (
                  <div className="bg-white p-4 rounded border border-green-200">
                    <h4 className="font-semibold text-gray-900 mb-2">Moms 12%</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_12.box_sales}: Försäljning 12%
                        </span>
                        <p className="text-lg font-mono font-bold">
                          {formatCurrency(vatReport.skv_3800.outgoing_12.sales)}
                        </p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_12.box_vat}: Utgående moms 12%
                        </span>
                        <p className="text-lg font-mono font-bold text-green-700">
                          {formatCurrency(vatReport.skv_3800.outgoing_12.vat)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* 6% VAT */}
                {vatReport.skv_3800.outgoing_6.vat > 0 && (
                  <div className="bg-white p-4 rounded border border-green-200">
                    <h4 className="font-semibold text-gray-900 mb-2">Moms 6%</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_6.box_sales}: Försäljning 6%
                        </span>
                        <p className="text-lg font-mono font-bold">
                          {formatCurrency(vatReport.skv_3800.outgoing_6.sales)}
                        </p>
                      </div>
                      <div>
                        <span className="text-sm text-gray-600">
                          Ruta {vatReport.skv_3800.outgoing_6.box_vat}: Utgående moms 6%
                        </span>
                        <p className="text-lg font-mono font-bold text-green-700">
                          {formatCurrency(vatReport.skv_3800.outgoing_6.vat)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Incoming VAT */}
                <div className="bg-white p-4 rounded border border-green-200">
                  <h4 className="font-semibold text-gray-900 mb-2">Ingående moms</h4>
                  <div>
                    <span className="text-sm text-gray-600">
                      Ruta {vatReport.skv_3800.incoming_total.box}: Ingående moms
                    </span>
                    <p className="text-lg font-mono font-bold text-blue-700">
                      {formatCurrency(vatReport.skv_3800.incoming_total.vat)}
                    </p>
                  </div>
                </div>

                {/* Net VAT */}
                <div className="bg-white p-4 rounded border-2 border-gray-900">
                  <h4 className="font-semibold text-gray-900 mb-2">Att betala/få tillbaka</h4>
                  <div>
                    <span className="text-sm text-gray-600">
                      Ruta {vatReport.skv_3800.net_vat.box}: Moms att betala (eller återfå med minus)
                    </span>
                    <p className={`text-xl font-mono font-bold ${
                      vatReport.skv_3800.net_vat.amount > 0 ? 'text-red-700' : 'text-green-700'
                    }`}>
                      {formatCurrency(vatReport.skv_3800.net_vat.amount)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-4 p-3 bg-yellow-50 border border-yellow-300 rounded">
                <p className="text-sm text-yellow-900">
                  <strong>💡 Tips:</strong> Gå till{' '}
                  <a
                    href="https://www.skatteverket.se"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline font-semibold"
                  >
                    Skatteverket.se
                  </a>{' '}
                  → Mina sidor → Momsdeklaration och fyll i rutorna ovan.
                </p>
              </div>

              {/* Download XML button */}
              <div className="mt-4">
                <button
                  onClick={() => {
                    if (!company || !selectedPeriod) return
                    const url = new URL('/api/reports/vat-report-xml', import.meta.env.VITE_API_URL || 'http://localhost:8000')
                    url.searchParams.append('company_id', company.id.toString())
                    url.searchParams.append('start_date', selectedPeriod.start_date)
                    url.searchParams.append('end_date', selectedPeriod.end_date)
                    url.searchParams.append('exclude_vat_settlements', excludeVatSettlements.toString())
                    window.open(url.toString(), '_blank')
                  }}
                  className="w-full px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Ladda ner XML-fil för uppladdning till Skatteverket
                </button>
                <p className="mt-2 text-xs text-center text-gray-600">
                  Filen är klar att laddas upp under "Lämna momsdeklaration" på Skatteverket.se
                </p>
              </div>
            </div>
          )}

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

      {/* Verifications Modal */}
      {showVerificationsModal && vatReport?.debug_info?.verifications && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
              <h3 className="text-xl font-bold">
                Verifikationer i momsrapporten ({vatReport.debug_info.verifications.length} st)
              </h3>
              <button
                onClick={() => setShowVerificationsModal(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
              >
                ×
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <div className="space-y-4">
                {vatReport.debug_info.verifications.map((ver) => (
                  <div key={ver.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-semibold text-lg">
                          {ver.series}-{ver.verification_number}
                        </span>
                        <span className="ml-3 text-sm text-gray-600">
                          {new Date(ver.transaction_date).toLocaleDateString('sv-SE')}
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          setShowVerificationsModal(false)
                          // Navigate to verification if needed
                          window.location.href = `/verifications#${ver.id}`
                        }}
                        className="text-sm text-blue-600 hover:text-blue-800"
                      >
                        Visa verifikation →
                      </button>
                    </div>

                    <p className="text-sm text-gray-700 mb-3">{ver.description}</p>

                    {/* All Transaction Lines */}
                    <div className="bg-gray-50 rounded p-3">
                      <p className="text-xs font-semibold text-gray-600 mb-2">
                        Alla konteringar (momskonton markerade i gult):
                      </p>
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="text-xs text-gray-500">
                            <th className="text-left">Konto</th>
                            <th className="text-left">Namn</th>
                            <th className="text-right">Debet</th>
                            <th className="text-right">Kredit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ver.transaction_lines.map((line, idx) => (
                            <tr
                              key={idx}
                              className={`border-t border-gray-200 ${
                                line.is_vat_account ? 'bg-yellow-100' : ''
                              }`}
                            >
                              <td className="py-1 font-mono">{line.account_number}</td>
                              <td className="py-1">{line.account_name}</td>
                              <td className="py-1 text-right font-mono">
                                {line.debit > 0 ? formatCurrency(line.debit) : '-'}
                              </td>
                              <td className="py-1 text-right font-mono">
                                {line.credit > 0 ? formatCurrency(line.credit) : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setShowVerificationsModal(false)}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors"
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
