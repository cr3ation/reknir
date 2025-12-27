import { useEffect, useState } from 'react'
import { Download, Plus, X, Eye, DollarSign, Send, FileText } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api, { invoiceApi, supplierInvoiceApi, customerApi, supplierApi, accountApi } from '@/services/api'
import type { InvoiceListItem, SupplierInvoiceListItem, Customer, Supplier, Account, InvoiceLine } from '@/types'
import { InvoiceStatus, PaymentStatus } from '@/types'
import { getErrorMessage } from '@/utils/errors'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import FiscalYearSelector from '@/components/FiscalYearSelector'

export default function Invoices() {
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([])
  const [supplierInvoices, setSupplierInvoices] = useState<SupplierInvoiceListItem[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateInvoiceModal, setShowCreateInvoiceModal] = useState(false)
  const [showCreateSupplierInvoiceModal, setShowCreateSupplierInvoiceModal] = useState(false)
  // Confirmation modal states
  const [confirmSendInvoice, setConfirmSendInvoice] = useState<InvoiceListItem | null>(null)
  const [confirmRegisterSupplierInvoice, setConfirmRegisterSupplierInvoice] = useState<SupplierInvoiceListItem | null>(null)
  const [sendingInvoice, setSendingInvoice] = useState(false)
  const [registeringSupplierInvoice, setRegisteringSupplierInvoice] = useState(false)
  // Payment modal states
  const [confirmPayInvoice, setConfirmPayInvoice] = useState<InvoiceListItem | null>(null)
  const [confirmPaySupplierInvoice, setConfirmPaySupplierInvoice] = useState<SupplierInvoiceListItem | null>(null)
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0])
  const [payingInvoice, setPayingInvoice] = useState(false)
  const [payingSupplierInvoice, setPayingSupplierInvoice] = useState(false)

  useEffect(() => {
    loadInvoices()
  }, [selectedCompany, selectedFiscalYear])

  const loadInvoices = async () => {
    if (!selectedCompany || !selectedFiscalYear) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      const [outgoingRes, incomingRes, customersRes, suppliersRes, accountsRes] = await Promise.all([
        invoiceApi.list(selectedCompany.id, { fiscal_year_id: selectedFiscalYear.id }),
        supplierInvoiceApi.list(selectedCompany.id, { fiscal_year_id: selectedFiscalYear.id }),
        customerApi.list(selectedCompany.id),
        supplierApi.list(selectedCompany.id),
        accountApi.list(selectedCompany.id, selectedFiscalYear.id),
      ])
      setInvoices(outgoingRes.data)
      setSupplierInvoices(incomingRes.data)
      setCustomers(customersRes.data)
      setSuppliers(suppliersRes.data)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load invoices:', error)
    } finally {
      setLoading(false)
    }
  }

  const downloadInvoicePdf = async (invoiceId: number, invoiceNumber: string, series: string) => {
    try {
      // Use axios to download with authentication
      const response = await api.get(`/invoices/${invoiceId}/pdf`, {
        responseType: 'blob'
      })

      // Create blob URL and download
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `faktura_${series}${invoiceNumber}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download PDF:', error)
      alert('Kunde inte ladda ner PDF')
    }
  }

  const handleSendInvoice = async () => {
    if (!confirmSendInvoice) return

    setSendingInvoice(true)
    try {
      await invoiceApi.send(confirmSendInvoice.id)
      await loadInvoices()
      setConfirmSendInvoice(null)
    } catch (error) {
      console.error('Failed to send invoice:', error)
      alert('Kunde inte skicka fakturan')
    } finally {
      setSendingInvoice(false)
    }
  }

  const handleRegisterSupplierInvoice = async () => {
    if (!confirmRegisterSupplierInvoice) return

    setRegisteringSupplierInvoice(true)
    try {
      await supplierInvoiceApi.register(confirmRegisterSupplierInvoice.id)
      await loadInvoices()
      setConfirmRegisterSupplierInvoice(null)
    } catch (error) {
      console.error('Failed to register supplier invoice:', error)
      alert('Kunde inte bokföra leverantörsfakturan')
    } finally {
      setRegisteringSupplierInvoice(false)
    }
  }

  const handlePayInvoice = async () => {
    if (!confirmPayInvoice) return

    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    const remainingAmount = confirmPayInvoice.total_amount - confirmPayInvoice.paid_amount

    setPayingInvoice(true)
    try {
      await invoiceApi.markPaid(confirmPayInvoice.id, {
        paid_date: paymentDate,
        paid_amount: remainingAmount,
        bank_account_id: bankAccount.id
      })
      await loadInvoices()
      setConfirmPayInvoice(null)
      alert('Fakturan har markerats som betald och en betalningsverifikation har skapats')
    } catch (error) {
      console.error('Failed to mark invoice as paid:', error)
      alert(`Kunde inte markera som betald: ${getErrorMessage(error, 'Unknown error')}`)
    } finally {
      setPayingInvoice(false)
    }
  }

  const handlePaySupplierInvoice = async () => {
    if (!confirmPaySupplierInvoice) return

    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    const remainingAmount = confirmPaySupplierInvoice.total_amount - confirmPaySupplierInvoice.paid_amount

    setPayingSupplierInvoice(true)
    try {
      await supplierInvoiceApi.markPaid(confirmPaySupplierInvoice.id, {
        paid_date: paymentDate,
        paid_amount: remainingAmount,
        bank_account_id: bankAccount.id
      })
      await loadInvoices()
      setConfirmPaySupplierInvoice(null)
      alert('Leverantörsfakturan har markerats som betald och en betalningsverifikation har skapats')
    } catch (error) {
      console.error('Failed to mark supplier invoice as paid:', error)
      alert(`Kunde inte markera som betald: ${getErrorMessage(error, 'Unknown error')}`)
    } finally {
      setPayingSupplierInvoice(false)
    }
  }

  const getStatusBadge = (status: InvoiceStatus, paymentStatus: PaymentStatus, dueDate: string) => {
    // Check if overdue: issued + not paid + due_date < today
    const isOverdue = status === InvoiceStatus.ISSUED &&
                      paymentStatus !== PaymentStatus.PAID &&
                      new Date(dueDate) < new Date()

    // Document status styling
    const statusConfig = {
      [InvoiceStatus.DRAFT]: { color: 'bg-gray-200 text-gray-800', label: 'UTKAST' },
      [InvoiceStatus.ISSUED]: { color: 'bg-blue-200 text-blue-800', label: 'SKICKAD' },
      [InvoiceStatus.CANCELLED]: { color: 'bg-gray-400 text-gray-900', label: 'MAKULERAD' },
    }

    // Payment status styling
    const paymentConfig = {
      [PaymentStatus.UNPAID]: { color: 'bg-yellow-100 text-yellow-800', label: 'OBETALD' },
      [PaymentStatus.PARTIALLY_PAID]: { color: 'bg-orange-200 text-orange-800', label: 'DELBETALD' },
      [PaymentStatus.PAID]: { color: 'bg-green-200 text-green-800', label: 'BETALD' },
    }

    const statusStyle = statusConfig[status] || { color: 'bg-gray-200', label: status }
    const paymentStyle = paymentConfig[paymentStatus] || { color: 'bg-gray-200', label: paymentStatus }

    return (
      <div className="flex gap-1 flex-wrap">
        <span className={`px-2 py-1 text-xs rounded ${statusStyle.color}`}>
          {statusStyle.label}
        </span>
        {status !== InvoiceStatus.DRAFT && status !== InvoiceStatus.CANCELLED && (
          <span className={`px-2 py-1 text-xs rounded ${isOverdue ? 'bg-red-200 text-red-800' : paymentStyle.color}`}>
            {isOverdue ? 'FÖRFALLEN' : paymentStyle.label}
          </span>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar fakturor...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <h1 className="text-3xl font-bold">Fakturor</h1>
        <FiscalYearSelector />
      </div>

      {/* Outgoing Invoices */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">Kundfakturor (Utgående)</h2>
          <button
            onClick={() => setShowCreateInvoiceModal(true)}
            className="btn btn-primary inline-flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            Ny faktura
          </button>
        </div>

        {invoices.length === 0 ? (
          <div className="card">
            <p className="text-gray-600">Inga kundfakturor ännu. Skapa din första faktura!</p>
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fakturanr
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Kund
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Belopp
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Betalt
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Åtgärder
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">
                      {invoice.invoice_series}{invoice.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm">{invoice.invoice_date}</td>
                    <td className="px-4 py-3 text-sm">{invoice.customer_name}</td>
                    <td className="px-4 py-3 text-sm">{getStatusBadge(invoice.status, invoice.payment_status, invoice.due_date)}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.total_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.paid_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => navigate(`/invoices/${invoice.id}`)}
                          className="p-1 text-gray-600 hover:text-gray-800"
                          title="Visa detaljer"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {invoice.status === InvoiceStatus.DRAFT && (
                          <button
                            onClick={() => setConfirmSendInvoice(invoice)}
                            className="inline-flex items-center px-3 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
                            title={selectedCompany?.accounting_basis === 'accrual' ? 'Skicka och bokför faktura' : 'Skicka faktura'}
                          >
                            Skicka
                          </button>
                        )}
                        {invoice.status === InvoiceStatus.ISSUED && invoice.payment_status !== PaymentStatus.PAID && (
                          <button
                            onClick={() => {
                              setPaymentDate(new Date().toISOString().split('T')[0])
                              setConfirmPayInvoice(invoice)
                            }}
                            className="p-1 text-purple-600 hover:text-purple-800"
                            title="Markera som betald"
                          >
                            <DollarSign className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => downloadInvoicePdf(invoice.id, String(invoice.invoice_number), invoice.invoice_series)}
                          className="inline-flex items-center px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
                          title="Ladda ner PDF"
                        >
                          <Download className="w-4 h-4 mr-1" />
                          PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Supplier Invoices */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">Leverantörsfakturor (Inkommande)</h2>
          <button
            onClick={() => setShowCreateSupplierInvoiceModal(true)}
            className="btn btn-primary inline-flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            Registrera faktura
          </button>
        </div>

        {supplierInvoices.length === 0 ? (
          <div className="card">
            <p className="text-gray-600">Inga leverantörsfakturor ännu.</p>
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fakturanr
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Leverantör
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Belopp
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Betalt
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                    Åtgärder
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {supplierInvoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">
                      {invoice.supplier_invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm">{invoice.invoice_date}</td>
                    <td className="px-4 py-3 text-sm">{invoice.supplier_name}</td>
                    <td className="px-4 py-3 text-sm">{getStatusBadge(invoice.status, invoice.payment_status, invoice.due_date)}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.total_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.paid_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => navigate(`/supplier-invoices/${invoice.id}`)}
                          className="p-1 text-gray-600 hover:text-gray-800"
                          title="Visa detaljer"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {invoice.status === InvoiceStatus.DRAFT && (
                          <button
                            onClick={() => setConfirmRegisterSupplierInvoice(invoice)}
                            className="inline-flex items-center px-3 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
                            title="Bokför faktura"
                          >
                            Bokför
                          </button>
                        )}
                        {invoice.status === InvoiceStatus.ISSUED && invoice.payment_status !== PaymentStatus.PAID && (
                          <button
                            onClick={() => {
                              setPaymentDate(new Date().toISOString().split('T')[0])
                              setConfirmPaySupplierInvoice(invoice)
                            }}
                            className="p-1 text-purple-600 hover:text-purple-800"
                            title="Markera som betald"
                          >
                            <DollarSign className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Invoice Modal */}
      {showCreateInvoiceModal && selectedCompany && (
        <CreateInvoiceModal
          companyId={selectedCompany.id}
          customers={customers}
          accounts={accounts}
          onClose={() => setShowCreateInvoiceModal(false)}
          onSuccess={() => {
            setShowCreateInvoiceModal(false)
            loadInvoices()
          }}
        />
      )}

      {/* Create Supplier Invoice Modal */}
      {showCreateSupplierInvoiceModal && selectedCompany && (
        <CreateSupplierInvoiceModal
          companyId={selectedCompany.id}
          suppliers={suppliers}
          accounts={accounts}
          onClose={() => setShowCreateSupplierInvoiceModal(false)}
          onSuccess={() => {
            setShowCreateSupplierInvoiceModal(false)
            loadInvoices()
          }}
        />
      )}

      {/* Send Invoice Confirmation Modal */}
      {confirmSendInvoice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
            {/* Header */}
            <div className="bg-indigo-50 px-6 py-4 border-b border-indigo-100">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                  <Send className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Skicka faktura
                  </h3>
                  <p className="text-sm text-gray-600">
                    {confirmSendInvoice.invoice_series}{confirmSendInvoice.invoice_number} - {confirmSendInvoice.customer_name}
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-4">
              <p className="text-gray-700">
                Vill du skicka denna faktura?
              </p>
              <p className="text-sm text-gray-500 mt-2">
                {selectedCompany?.accounting_basis === 'accrual'
                  ? 'En verifikation kommer att skapas automatiskt och fakturan markeras som skickad.'
                  : 'Fakturan markeras som skickad.'}
              </p>
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Belopp:</span>
                  <span className="font-semibold">
                    {confirmSendInvoice.total_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmSendInvoice(null)}
                disabled={sendingInvoice}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={handleSendInvoice}
                disabled={sendingInvoice}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {sendingInvoice ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Skickar...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Skicka faktura</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Supplier Invoice Confirmation Modal */}
      {confirmRegisterSupplierInvoice && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
            {/* Header */}
            <div className="bg-indigo-50 px-6 py-4 border-b border-indigo-100">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Bokför leverantörsfaktura
                  </h3>
                  <p className="text-sm text-gray-600">
                    {confirmRegisterSupplierInvoice.supplier_invoice_number} - {confirmRegisterSupplierInvoice.supplier_name}
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-4">
              <p className="text-gray-700">
                Vill du bokföra denna leverantörsfaktura?
              </p>
              <p className="text-sm text-gray-500 mt-2">
                En verifikation kommer att skapas automatiskt med kostnad och ingående moms.
              </p>
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Belopp:</span>
                  <span className="font-semibold">
                    {confirmRegisterSupplierInvoice.total_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmRegisterSupplierInvoice(null)}
                disabled={registeringSupplierInvoice}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={handleRegisterSupplierInvoice}
                disabled={registeringSupplierInvoice}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {registeringSupplierInvoice ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Bokför...</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    <span>Bokför faktura</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pay Invoice Confirmation Modal */}
      {confirmPayInvoice && (
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
                    {confirmPayInvoice.invoice_series}{confirmPayInvoice.invoice_number} - {confirmPayInvoice.customer_name}
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
                    {confirmPayInvoice.total_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Redan betalt:</span>
                  <span>
                    {confirmPayInvoice.paid_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-semibold border-t pt-1 mt-1">
                  <span className="text-gray-700">Att betala:</span>
                  <span className="text-purple-600">
                    {(confirmPayInvoice.total_amount - confirmPayInvoice.paid_amount).toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmPayInvoice(null)}
                disabled={payingInvoice}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={handlePayInvoice}
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

      {/* Pay Supplier Invoice Confirmation Modal */}
      {confirmPaySupplierInvoice && (
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
                    Markera leverantörsfaktura som betald
                  </h3>
                  <p className="text-sm text-gray-600">
                    {confirmPaySupplierInvoice.supplier_invoice_number} - {confirmPaySupplierInvoice.supplier_name}
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
                    {confirmPaySupplierInvoice.total_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Redan betalt:</span>
                  <span>
                    {confirmPaySupplierInvoice.paid_amount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-semibold border-t pt-1 mt-1">
                  <span className="text-gray-700">Att betala:</span>
                  <span className="text-purple-600">
                    {(confirmPaySupplierInvoice.total_amount - confirmPaySupplierInvoice.paid_amount).toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmPaySupplierInvoice(null)}
                disabled={payingSupplierInvoice}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Avbryt
              </button>
              <button
                onClick={handlePaySupplierInvoice}
                disabled={payingSupplierInvoice}
                className="px-4 py-2 text-sm font-medium text-white bg-purple-600 border border-transparent rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {payingSupplierInvoice ? (
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

// Create Invoice Modal Component
interface CreateInvoiceModalProps {
  companyId: number
  customers: Customer[]
  accounts: Account[]
  onClose: () => void
  onSuccess: () => void
}

function CreateInvoiceModal({ companyId, customers, accounts, onClose, onSuccess }: CreateInvoiceModalProps) {
  const [customerId, setCustomerId] = useState<number>(0)
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0])
  const [dueDate, setDueDate] = useState('')
  const [reference, setReference] = useState('')
  const [ourReference, setOurReference] = useState('')
  const [message, setMessage] = useState('')
  const [lines, setLines] = useState<InvoiceLine[]>([
    { description: '', quantity: 1, unit: 'st', unit_price: 0, vat_rate: 25 }
  ])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Update due date when customer changes
  useEffect(() => {
    if (customerId > 0) {
      const customer = customers.find(c => c.id === customerId)
      if (customer) {
        const date = new Date(invoiceDate)
        date.setDate(date.getDate() + customer.payment_terms_days)
        setDueDate(date.toISOString().split('T')[0])
      }
    }
  }, [customerId, invoiceDate, customers])

  const addLine = () => {
    setLines([...lines, { description: '', quantity: 1, unit: 'st', unit_price: 0, vat_rate: 25 }])
  }

  const removeLine = (index: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== index))
    }
  }

  const updateLine = (index: number, field: keyof InvoiceLine, value: string | number | undefined) => {
    const newLines = [...lines]
    newLines[index] = { ...newLines[index], [field]: value }
    setLines(newLines)
  }

  const calculateLineTotal = (line: InvoiceLine) => {
    const net = line.quantity * line.unit_price
    const vat = net * (line.vat_rate / 100)
    return net + vat
  }

  const calculateTotals = () => {
    let totalNet = 0
    let totalVat = 0
    lines.forEach(line => {
      const net = line.quantity * line.unit_price
      const vat = net * (line.vat_rate / 100)
      totalNet += net
      totalVat += vat
    })
    return { totalNet, totalVat, totalAmount: totalNet + totalVat }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (customerId === 0) {
      setError('Välj en kund')
      return
    }

    if (lines.some(l => !l.description)) {
      setError('Alla rader måste ha en beskrivning')
      return
    }

    setSaving(true)
    setError(null)

    try {
      await invoiceApi.create({
        company_id: companyId,
        customer_id: customerId,
        invoice_date: invoiceDate,
        due_date: dueDate,
        reference,
        our_reference: ourReference,
        message,
        invoice_series: 'F',
        invoice_lines: lines.map(line => ({
          description: line.description,
          quantity: line.quantity,
          unit: line.unit,
          unit_price: line.unit_price,
          vat_rate: line.vat_rate,
          account_id: line.account_id,
        })),
      })
      onSuccess()
    } catch (err) {
      console.error('Failed to create invoice:', err)
      setError(getErrorMessage(err, 'Kunde inte skapa faktura'))
    } finally {
      setSaving(false)
    }
  }

  const totals = calculateTotals()

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold">Ny kundfaktura</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}

          {/* Customer and dates */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Kund *
              </label>
              <select
                value={customerId}
                onChange={(e) => setCustomerId(parseInt(e.target.value))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              >
                <option value={0}>Välj kund...</option>
                {customers.map(customer => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fakturadatum *
              </label>
              <input
                type="date"
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Förfallodatum *
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Er referens
              </label>
              <input
                type="text"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Vår referens
              </label>
              <input
                type="text"
                value={ourReference}
                onChange={(e) => setOurReference(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Invoice lines */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-lg font-semibold">Fakturarader</h3>
              <button
                type="button"
                onClick={addLine}
                className="text-sm text-indigo-600 hover:text-indigo-800"
              >
                + Lägg till rad
              </button>
            </div>

            <div className="space-y-3">
              {lines.map((line, index) => (
                <div key={index} className="space-y-2 p-3 bg-gray-50 rounded">
                  <div className="grid grid-cols-12 gap-2 items-start">
                    <div className="col-span-4">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Beskrivning *
                      </label>
                      <input
                        type="text"
                        placeholder="Beskrivning av vara/tjänst"
                        value={line.description}
                        onChange={(e) => updateLine(index, 'description', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Antal *
                      </label>
                      <input
                        type="number"
                        placeholder="1"
                        value={line.quantity || ''}
                        onChange={(e) => {
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0
                          updateLine(index, 'quantity', value)
                        }}
                        step="1"
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Enhet
                      </label>
                      <input
                        type="text"
                        placeholder="st"
                        value={line.unit}
                        onChange={(e) => updateLine(index, 'unit', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        À-pris *
                      </label>
                      <input
                        type="number"
                        placeholder="0,00"
                        value={line.unit_price || ''}
                        onChange={(e) => {
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0
                          updateLine(index, 'unit_price', value)
                        }}
                        step="0.01"
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Moms *
                      </label>
                      <select
                        value={line.vat_rate}
                        onChange={(e) => updateLine(index, 'vat_rate', parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value={0}>0%</option>
                        <option value={6}>6%</option>
                        <option value={12}>12%</option>
                        <option value={25}>25%</option>
                      </select>
                    </div>
                    <div className="col-span-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        &nbsp;
                      </label>
                      <div className="flex justify-center">
                        {lines.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeLine(index)}
                            className="text-red-600 hover:text-red-800 p-2"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-12 md:col-span-5">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Intäktskonto
                      </label>
                      <select
                        value={line.account_id || ''}
                        onChange={(e) => updateLine(index, 'account_id', e.target.value ? parseInt(e.target.value) : undefined)}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 text-sm"
                      >
                        <option value="">Auto (baserat på moms)</option>
                        {accounts.filter(a => a.account_number >= 3000 && a.account_number < 4000).map(account => (
                          <option key={account.id} value={account.id}>
                            {account.account_number} - {account.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-12 md:col-span-6 text-right font-mono text-sm">
                      Totalt: {calculateLineTotal(line).toLocaleString('sv-SE')} kr
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Totals */}
          <div className="bg-gray-50 p-4 rounded mb-6">
            <div className="flex justify-between text-sm mb-1">
              <span>Netto:</span>
              <span className="font-mono">{totals.totalNet.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
            <div className="flex justify-between text-sm mb-2">
              <span>Moms:</span>
              <span className="font-mono">{totals.totalVat.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
            <div className="flex justify-between text-lg font-bold border-t pt-2">
              <span>Totalt:</span>
              <span className="font-mono">{totals.totalAmount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
          </div>

          {/* Message */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Meddelande (visas på fakturan)
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="T.ex. betalningsvillkor eller övrig information..."
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Avbryt
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? 'Skapar...' : 'Skapa faktura'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Create Supplier Invoice Modal Component
interface CreateSupplierInvoiceModalProps {
  companyId: number
  suppliers: Supplier[]
  accounts: Account[]
  onClose: () => void
  onSuccess: () => void
}

function CreateSupplierInvoiceModal({ companyId, suppliers, accounts, onClose, onSuccess }: CreateSupplierInvoiceModalProps) {
  const [supplierId, setSupplierId] = useState<number>(0)
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0])
  const [dueDate, setDueDate] = useState('')
  const [ocrNumber, setOcrNumber] = useState('')
  const [reference, setReference] = useState('')
  const [lines, setLines] = useState<InvoiceLine[]>([
    { description: '', quantity: 1, unit: 'st', unit_price: 0, vat_rate: 25 }
  ])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Update due date when supplier changes
  useEffect(() => {
    if (supplierId > 0) {
      const supplier = suppliers.find(s => s.id === supplierId)
      if (supplier) {
        const date = new Date(invoiceDate)
        date.setDate(date.getDate() + supplier.payment_terms_days)
        setDueDate(date.toISOString().split('T')[0])
      }
    }
  }, [supplierId, invoiceDate, suppliers])

  const addLine = () => {
    setLines([...lines, { description: '', quantity: 1, unit: 'st', unit_price: 0, vat_rate: 25 }])
  }

  const removeLine = (index: number) => {
    if (lines.length > 1) {
      setLines(lines.filter((_, i) => i !== index))
    }
  }

  const updateLine = (index: number, field: keyof InvoiceLine, value: string | number | undefined) => {
    const newLines = [...lines]
    newLines[index] = { ...newLines[index], [field]: value }
    setLines(newLines)
  }

  const calculateLineTotal = (line: InvoiceLine) => {
    const net = line.quantity * line.unit_price
    const vat = net * (line.vat_rate / 100)
    return net + vat
  }

  const calculateTotals = () => {
    let totalNet = 0
    let totalVat = 0
    lines.forEach(line => {
      const net = line.quantity * line.unit_price
      const vat = net * (line.vat_rate / 100)
      totalNet += net
      totalVat += vat
    })
    return { totalNet, totalVat, totalAmount: totalNet + totalVat }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (supplierId === 0) {
      setError('Välj en leverantör')
      return
    }

    if (!supplierInvoiceNumber) {
      setError('Ange leverantörens fakturanummer')
      return
    }

    if (lines.some(l => !l.description)) {
      setError('Alla rader måste ha en beskrivning')
      return
    }

    setSaving(true)
    setError(null)

    try {
      await supplierInvoiceApi.create({
        company_id: companyId,
        supplier_id: supplierId,
        supplier_invoice_number: supplierInvoiceNumber,
        invoice_date: invoiceDate,
        due_date: dueDate,
        ocr_number: ocrNumber || undefined,
        reference: reference || undefined,
        supplier_invoice_lines: lines.map(line => ({
          description: line.description,
          quantity: line.quantity,
          unit: line.unit,
          unit_price: line.unit_price,
          vat_rate: line.vat_rate,
          account_id: line.account_id,
        })),
      })
      onSuccess()
    } catch (err) {
      console.error('Failed to create supplier invoice:', err)
      setError(getErrorMessage(err, 'Kunde inte skapa leverantörsfaktura'))
    } finally {
      setSaving(false)
    }
  }

  const totals = calculateTotals()

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold">Registrera leverantörsfaktura</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}

          {/* Supplier and dates */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Leverantör *
              </label>
              <select
                value={supplierId}
                onChange={(e) => setSupplierId(parseInt(e.target.value))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              >
                <option value={0}>Välj leverantör...</option>
                {suppliers.map(supplier => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fakturanummer *
              </label>
              <input
                type="text"
                value={supplierInvoiceNumber}
                onChange={(e) => setSupplierInvoiceNumber(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="Leverantörens fakturanummer"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Fakturadatum *
              </label>
              <input
                type="date"
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Förfallodatum *
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                OCR-nummer
              </label>
              <input
                type="text"
                value={ocrNumber}
                onChange={(e) => setOcrNumber(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Referens
              </label>
              <input
                type="text"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Invoice lines */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-lg font-semibold">Fakturarader</h3>
              <button
                type="button"
                onClick={addLine}
                className="text-sm text-indigo-600 hover:text-indigo-800"
              >
                + Lägg till rad
              </button>
            </div>

            <div className="space-y-3">
              {lines.map((line, index) => (
                <div key={index} className="space-y-2 p-3 bg-gray-50 rounded">
                  <div className="grid grid-cols-12 gap-2 items-start">
                    <div className="col-span-12 md:col-span-6">
                      <input
                        type="text"
                        placeholder="Beskrivning *"
                        value={line.description}
                        onChange={(e) => updateLine(index, 'description', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-4 md:col-span-2">
                      <input
                        type="number"
                        placeholder="Antal"
                        value={line.quantity || ''} // Show empty string instead of 0 for better UX
                        onChange={(e) => {
                          // Handle empty fields as 0, avoid "025000" display issue
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0
                          updateLine(index, 'quantity', value)
                        }}
                        step="0.01"
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-4 md:col-span-2">
                      <input
                        type="number"
                        placeholder="À-pris (kr per enhet)"
                        value={line.unit_price || ''}
                        onChange={(e) => {
                          // Handle empty fields as 0, avoid "025000" display issue
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0
                          updateLine(index, 'unit_price', value)
                        }}
                        step="0.01"
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="col-span-4 md:col-span-2">
                      <select
                        value={line.vat_rate}
                        onChange={(e) => updateLine(index, 'vat_rate', parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value={0}>0%</option>
                        <option value={6}>6%</option>
                        <option value={12}>12%</option>
                        <option value={25}>25%</option>
                      </select>
                    </div>
                    <div className="col-span-1 md:col-span-1 text-right">
                      {lines.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeLine(index)}
                          className="text-red-600 hover:text-red-800 p-2"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-12 md:col-span-6">
                      <select
                        value={line.account_id || ''}
                        onChange={(e) => updateLine(index, 'account_id', e.target.value ? parseInt(e.target.value) : undefined)}
                        className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 text-sm"
                      >
                        <option value="">Auto (6570 - Övriga externa tjänster)</option>
                        {accounts.filter(a => a.account_number >= 4000 && a.account_number < 8000).map(account => (
                          <option key={account.id} value={account.id}>
                            {account.account_number} - {account.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-12 md:col-span-5 text-right font-mono text-sm">
                      Totalt: {calculateLineTotal(line).toLocaleString('sv-SE')} kr
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Totals */}
          <div className="bg-gray-50 p-4 rounded mb-6">
            <div className="flex justify-between text-sm mb-1">
              <span>Netto:</span>
              <span className="font-mono">{totals.totalNet.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
            <div className="flex justify-between text-sm mb-2">
              <span>Moms:</span>
              <span className="font-mono">{totals.totalVat.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
            <div className="flex justify-between text-lg font-bold border-t pt-2">
              <span>Totalt:</span>
              <span className="font-mono">{totals.totalAmount.toLocaleString('sv-SE', { style: 'currency', currency: 'SEK' })}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Avbryt
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? 'Registrerar...' : 'Registrera faktura'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
