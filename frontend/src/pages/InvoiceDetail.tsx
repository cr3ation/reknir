import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, DollarSign, Download } from 'lucide-react'
import api, { invoiceApi, accountApi, customerApi } from '@/services/api'
import type { Invoice, Account, Customer } from '@/types'
import { InvoiceStatus, PaymentStatus } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'

export default function InvoiceDetail() {
  const { invoiceId } = useParams<{ invoiceId: string }>()
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  // Payment modal state
  const [showPaymentModal, setShowPaymentModal] = useState(false)
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0])
  const [payingInvoice, setPayingInvoice] = useState(false)

  useEffect(() => {
    loadInvoice()
    loadAccounts()
  }, [invoiceId, selectedCompany])

  const loadInvoice = async () => {
    try {
      const response = await invoiceApi.get(parseInt(invoiceId!))
      setInvoice(response.data)

      // Load customer details
      if (response.data.customer_id) {
        const customerRes = await customerApi.get(response.data.customer_id)
        setCustomer(customerRes.data)
      }

      setLoading(false)
    } catch (error) {
      console.error('Failed to load invoice:', error)
      alert('Kunde inte ladda fakturan')
      navigate('/invoices')
    }
  }

  const loadAccounts = async () => {
    if (!selectedCompany || !selectedFiscalYear) return

    try {
      const accountsRes = await accountApi.list(selectedCompany.id, selectedFiscalYear.id)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    }
  }

  const handleSendInvoice = async () => {
    const isAccrualMethod = selectedCompany?.accounting_basis === 'accrual'
    const confirmMessage = isAccrualMethod
      ? 'Skicka denna faktura? En verifikation kommer att skapas.'
      : 'Skicka denna faktura?'

    if (!confirm(confirmMessage)) return

    try {
      await invoiceApi.send(parseInt(invoiceId!))
      await loadInvoice()
      const successMessage = isAccrualMethod
        ? 'Fakturan har skickats och bokförts'
        : 'Fakturan har skickats'
      alert(successMessage)
    } catch (error: any) {
      console.error('Failed to send invoice:', error)
      alert(`Kunde inte skicka fakturan: ${error.response?.data?.detail || error.message}`)
    }
  }

  const openPaymentModal = () => {
    setPaymentDate(new Date().toISOString().split('T')[0])
    setShowPaymentModal(true)
  }

  const handleMarkPaid = async () => {
    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    setPayingInvoice(true)
    try {
      await invoiceApi.markPaid(parseInt(invoiceId!), {
        paid_date: paymentDate,
        paid_amount: invoice!.total_amount - invoice!.paid_amount,
        bank_account_id: bankAccount.id
      })
      setShowPaymentModal(false)
      await loadInvoice()
      alert('Fakturan har markerats som betald och en betalningsverifikation har skapats')
    } catch (error: any) {
      console.error('Failed to mark paid:', error)
      alert(`Kunde inte markera som betald: ${error.response?.data?.detail || error.message}`)
    } finally {
      setPayingInvoice(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!invoice) return

    try {
      // Use axios to download with authentication
      const response = await api.get(`/invoices/${invoice.id}/pdf`, {
        responseType: 'blob' // Important for file downloads
      })

      // Create blob URL and download
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `faktura_${invoice.invoice_number}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download PDF:', error)
      alert('Kunde inte ladda ner PDF')
    }
  }

  const formatCurrency = (amount: number | undefined) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 2,
    }).format(amount || 0)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('sv-SE')
  }

  const getStatusBadge = (status: string) => {
    const badges = {
      draft: 'bg-gray-100 text-gray-800',
      sent: 'bg-blue-100 text-blue-800',
      paid: 'bg-green-100 text-green-800',
      partial: 'bg-yellow-100 text-yellow-800',
      overdue: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-400 text-gray-900',
    }
    const labels = {
      draft: 'Utkast',
      sent: 'Skickad',
      paid: 'Betald',
      partial: 'Delvis betald',
      overdue: 'Förfallen',
      cancelled: 'Avbruten',
    }
    return (
      <span className={`px-3 py-1 text-sm font-semibold rounded-full ${badges[status as keyof typeof badges]}`}>
        {labels[status as keyof typeof labels]}
      </span>
    )
  }

  if (loading || !invoice) {
    return <div className="flex items-center justify-center h-64"><p className="text-gray-500">Laddar...</p></div>
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/invoices" className="text-gray-600 hover:text-gray-900">
            <ArrowLeft className="w-6 h-6" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold">
              Faktura {invoice.invoice_number}
            </h1>
            <p className="text-gray-600">
              {customer?.name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {getStatusBadge(invoice.status)}
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Fakturainformation</h2>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Kund</dt>
                <dd className="mt-1 text-sm text-gray-900">{customer?.name || '-'}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Fakturanummer</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {invoice.invoice_number}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Fakturadatum</dt>
                <dd className="mt-1 text-sm text-gray-900">{formatDate(invoice.invoice_date)}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Förfallodatum</dt>
                <dd className="mt-1 text-sm text-gray-900">{formatDate(invoice.due_date)}</dd>
              </div>
              {invoice.paid_date && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Betaldatum</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(invoice.paid_date)}</dd>
                </div>
              )}
              {invoice.reference && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Er referens</dt>
                  <dd className="mt-1 text-sm text-gray-900">{invoice.reference}</dd>
                </div>
              )}
              {invoice.our_reference && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Vår referens</dt>
                  <dd className="mt-1 text-sm text-gray-900">{invoice.our_reference}</dd>
                </div>
              )}
            </dl>
            {invoice.notes && (
              <div className="mt-4">
                <dt className="text-sm font-medium text-gray-500">Anteckningar (interna)</dt>
                <dd className="mt-1 text-sm text-gray-900">{invoice.notes}</dd>
              </div>
            )}
            {invoice.message && (
              <div className="mt-4">
                <dt className="text-sm font-medium text-gray-500">Meddelande (på faktura)</dt>
                <dd className="mt-1 text-sm text-gray-900">{invoice.message}</dd>
              </div>
            )}
          </div>

          {/* Verifications & Payment History */}
          {(invoice.invoice_verification_id || (invoice.payments && invoice.payments.length > 0)) && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4">Verifikationer & Betalningshistorik</h2>

              {/* Invoice Verification */}
              {invoice.invoice_verification_id && (
                <div className="mb-4">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">Fakturaverifikation</h3>
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                        <FileText className="w-4 h-4 text-blue-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          Bokföringsverifikation
                        </p>
                        <p className="text-xs text-gray-500">
                          Skapad vid utskick av faktura
                        </p>
                      </div>
                    </div>
                    <Link
                      to={`/verifications/${invoice.invoice_verification_id}`}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      Visa verifikation →
                    </Link>
                  </div>
                </div>
              )}

              {/* Payment History */}
              {invoice.payments && invoice.payments.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-500 mb-2">Betalningar</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Datum
                          </th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                            Belopp
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                            Referens
                          </th>
                          <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                            Verifikation
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 bg-white">
                        {invoice.payments.map((payment) => (
                          <tr key={payment.id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm">
                              {formatDate(payment.payment_date)}
                            </td>
                            <td className="px-4 py-3 text-sm text-right font-mono">
                              {formatCurrency(payment.amount)}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-500">
                              {payment.reference || '-'}
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                              {payment.verification_id ? (
                                <Link
                                  to={`/verifications/${payment.verification_id}`}
                                  className="text-purple-600 hover:text-purple-800 font-medium"
                                >
                                  Visa →
                                </Link>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50">
                        <tr>
                          <td className="px-4 py-2 text-sm font-semibold">
                            Totalt betalt
                          </td>
                          <td className="px-4 py-2 text-sm text-right font-mono font-semibold">
                            {formatCurrency(invoice.paid_amount)}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
              )}

              {/* No payments yet */}
              {(!invoice.payments || invoice.payments.length === 0) && !invoice.invoice_verification_id && (
                <p className="text-sm text-gray-500">Inga verifikationer kopplade till denna faktura ännu.</p>
              )}
            </div>
          )}

          {/* Invoice Lines */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Fakturarader</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Beskrivning
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Antal
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      À pris
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Moms %
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {invoice.invoice_lines.map((line, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">{line.description}</td>
                      <td className="px-4 py-3 text-sm text-right font-mono">
                        {line.quantity} {line.unit}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono">
                        {formatCurrency(line.unit_price)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono">{line.vat_rate}%</td>
                      <td className="px-4 py-3 text-sm text-right font-mono">
                        {formatCurrency(line.total_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={4} className="px-4 py-3 text-sm font-semibold text-right">
                      Netto:
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                      {formatCurrency(invoice.net_amount)}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={4} className="px-4 py-3 text-sm font-semibold text-right">
                      Moms:
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono font-semibold">
                      {formatCurrency(invoice.vat_amount)}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={4} className="px-4 py-3 text-sm font-bold text-right">
                      Totalt:
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono font-bold">
                      {formatCurrency(invoice.total_amount)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Åtgärder</h2>
            <div className="space-y-2">
              {invoice.status === InvoiceStatus.DRAFT && (
                <button
                  onClick={handleSendInvoice}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  <FileText className="w-4 h-4" />
                  {selectedCompany?.accounting_basis === 'accrual' ? 'Skicka och bokför' : 'Skicka'}
                </button>
              )}
              {invoice.status === InvoiceStatus.ISSUED && invoice.payment_status !== PaymentStatus.PAID && (
                <button
                  onClick={openPaymentModal}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
                >
                  <DollarSign className="w-4 h-4" />
                  Markera som betald
                </button>
              )}
              <button
                onClick={handleDownloadPdf}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <Download className="w-4 h-4" />
                Ladda ner PDF
              </button>
              {invoice.invoice_verification_id && (
                <Link
                  to={`/verifications/${invoice.invoice_verification_id}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                >
                  <FileText className="w-4 h-4" />
                  Visa bokföringsverifikation
                </Link>
              )}
              {invoice.payment_verification_id && (
                <Link
                  to={`/verifications/${invoice.payment_verification_id}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                >
                  <FileText className="w-4 h-4" />
                  Visa betalningsverifikation
                </Link>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Sammanfattning</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Status</dt>
                <dd className="text-gray-900 font-semibold">
                  {getStatusBadge(invoice.status)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Totalt belopp</dt>
                <dd className="text-gray-900 font-semibold font-mono">
                  {formatCurrency(invoice.total_amount)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Betalt belopp</dt>
                <dd className="text-gray-900 font-semibold font-mono">
                  {formatCurrency(invoice.paid_amount)}
                </dd>
              </div>
              {invoice.total_amount > invoice.paid_amount && (
                <div>
                  <dt className="text-gray-500">Kvarstår att få in</dt>
                  <dd className="text-green-600 font-semibold font-mono">
                    {formatCurrency(invoice.total_amount - invoice.paid_amount)}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Info */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Information</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Skapad</dt>
                <dd className="text-gray-900">{formatDate(invoice.created_at)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Senast uppdaterad</dt>
                <dd className="text-gray-900">{formatDate(invoice.updated_at)}</dd>
              </div>
              {invoice.sent_at && (
                <div>
                  <dt className="text-gray-500">Skickad</dt>
                  <dd className="text-gray-900">{formatDate(invoice.sent_at)}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>

      {/* Payment Modal */}
      {showPaymentModal && invoice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
            {/* Header */}
            <div className="bg-purple-50 px-6 py-4 border-b border-purple-100">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                  <DollarSign className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Markera faktura som betald
                  </h3>
                  <p className="text-sm text-gray-600">
                    {invoice.invoice_number} - {customer?.name}
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-4">
              <p className="text-gray-700 mb-4">
                En betalningsverifikation kommer att skapas automatiskt.
              </p>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Betalningsdatum
                </label>
                <input
                  type="date"
                  value={paymentDate}
                  onChange={(e) => setPaymentDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Fakturabelopp:</span>
                  <span className="font-semibold">
                    {invoice.total_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Redan betalt:</span>
                  <span>
                    {invoice.paid_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-semibold border-t pt-1 mt-1">
                  <span className="text-gray-700">Att betala:</span>
                  <span className="text-purple-600">
                    {(invoice.total_amount - invoice.paid_amount).toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setShowPaymentModal(false)}
                disabled={payingInvoice}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={handleMarkPaid}
                disabled={payingInvoice}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 border border-transparent rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {payingInvoice ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Sparar...</span>
                  </>
                ) : (
                  <>
                    <DollarSign className="w-4 h-4" />
                    <span>Markera som betald</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
