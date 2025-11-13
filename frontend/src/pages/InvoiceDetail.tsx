import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, DollarSign, Download } from 'lucide-react'
import { invoiceApi, accountApi, companyApi, customerApi } from '@/services/api'
import type { Invoice, Account, Customer } from '@/types'

export default function InvoiceDetail() {
  const { invoiceId } = useParams<{ invoiceId: string }>()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadInvoice()
    loadAccounts()
  }, [invoiceId])

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
    try {
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) return
      const company = companiesRes.data[0]
      const accountsRes = await accountApi.list(company.id)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    }
  }

  const handleSendInvoice = async () => {
    if (!confirm('Skicka denna faktura? En verifikation kommer att skapas.')) return

    try {
      await invoiceApi.send(parseInt(invoiceId!))
      await loadInvoice()
      alert('Fakturan har skickats och bokförts')
    } catch (error: any) {
      console.error('Failed to send invoice:', error)
      alert(`Kunde inte skicka fakturan: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleMarkPaid = async () => {
    const paidDate = prompt('Ange betalningsdatum (ÅÅÅÅ-MM-DD):', new Date().toISOString().split('T')[0])
    if (!paidDate) return

    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    try {
      await invoiceApi.markPaid(parseInt(invoiceId!), {
        paid_date: paidDate,
        paid_amount: invoice!.total_amount - invoice!.paid_amount,
        bank_account_id: bankAccount.id
      })
      await loadInvoice()
      alert('Fakturan har markerats som betald och en betalningsverifikation har skapats')
    } catch (error: any) {
      console.error('Failed to mark paid:', error)
      alert(`Kunde inte markera som betald: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDownloadPdf = async () => {
    if (!invoice) return

    try {
      // Use axios to download with authentication
      const response = await api.get(`/api/invoices/${invoice.id}/pdf`, {
        responseType: 'blob' // Important for file downloads
      })

      // Create blob URL and download
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `faktura_${invoice.invoice_series}${invoice.invoice_number}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download PDF:', error)
      alert('Kunde inte ladda ner PDF')
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 2,
    }).format(amount)
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
              Faktura {invoice.invoice_series}{invoice.invoice_number}
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
                  {invoice.invoice_series}{invoice.invoice_number}
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
              {invoice.status === 'draft' && (
                <button
                  onClick={handleSendInvoice}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  <FileText className="w-4 h-4" />
                  Skicka och bokför
                </button>
              )}
              {invoice.status !== 'paid' && invoice.status !== 'draft' && (
                <button
                  onClick={handleMarkPaid}
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
    </div>
  )
}
