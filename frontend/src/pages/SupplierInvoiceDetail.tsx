import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, DollarSign, BookOpen } from 'lucide-react'
import { supplierInvoiceApi, accountApi, supplierApi, attachmentApi } from '@/services/api'
import type { SupplierInvoice, Account, Supplier, EntityAttachment } from '@/types'
import { InvoiceStatus, PaymentStatus } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { getErrorMessage } from '@/utils/errors'
import AttachmentManager from '@/components/AttachmentManager'

export default function SupplierInvoiceDetail() {
  const { invoiceId } = useParams<{ invoiceId: string }>()
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [invoice, setInvoice] = useState<SupplierInvoice | null>(null)
  const [supplier, setSupplier] = useState<Supplier | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [attachments, setAttachments] = useState<EntityAttachment[]>([])
  const [loading, setLoading] = useState(true)

  const loadInvoice = useCallback(async () => {
    try {
      const response = await supplierInvoiceApi.get(parseInt(invoiceId!))
      setInvoice(response.data)

      // Load supplier details
      if (response.data.supplier_id) {
        const supplierRes = await supplierApi.get(response.data.supplier_id)
        setSupplier(supplierRes.data)
      }

      // Load attachments
      const attachmentsRes = await supplierInvoiceApi.listAttachments(parseInt(invoiceId!))
      setAttachments(attachmentsRes.data)

      setLoading(false)
    } catch (error) {
      console.error('Failed to load invoice:', error)
      alert('Kunde inte ladda fakturan')
      navigate('/invoices')
    }
  }, [invoiceId, navigate])

  const loadAccounts = useCallback(async () => {
    if (!selectedCompany || !selectedFiscalYear) return

    try {
      const accountsRes = await accountApi.list(selectedCompany.id, selectedFiscalYear.id)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    }
  }, [selectedCompany, selectedFiscalYear])

  useEffect(() => {
    loadInvoice()
    loadAccounts()
  }, [loadInvoice, loadAccounts])

  const handleRegister = async () => {
    const isAccrualMethod = selectedCompany?.accounting_basis === 'accrual'
    const confirmMessage = isAccrualMethod
      ? 'Registrera denna leverantörsfaktura? En verifikation kommer att skapas.'
      : 'Registrera denna leverantörsfaktura?'

    if (!confirm(confirmMessage)) return

    try {
      await supplierInvoiceApi.register(parseInt(invoiceId!))
      await loadInvoice()
      const successMessage = isAccrualMethod
        ? 'Leverantörsfakturan har registrerats och en verifikation har skapats'
        : 'Leverantörsfakturan har registrerats'
      alert(successMessage)
    } catch (error) {
      console.error('Failed to register:', error)
      alert(`Kunde inte registrera: ${getErrorMessage(error, 'Unknown error')}`)
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
      await supplierInvoiceApi.markPaid(parseInt(invoiceId!), {
        paid_date: paidDate,
        paid_amount: invoice!.total_amount,
        bank_account_id: bankAccount.id
      })
      await loadInvoice()
      alert('Fakturan har markerats som betald och en betalningsverifikation har skapats')
    } catch (error) {
      console.error('Failed to mark paid:', error)
      alert(`Kunde inte markera som betald: ${getErrorMessage(error, 'Unknown error')}`)
    }
  }

  // Attachment handlers for AttachmentManager
  const handleUploadAttachment = async (file: File) => {
    if (!selectedCompany) throw new Error('No company selected')

    // Upload file and link to supplier invoice
    const uploadRes = await attachmentApi.upload(selectedCompany.id, file)
    await supplierInvoiceApi.linkAttachment(parseInt(invoiceId!), uploadRes.data.id)

    // Reload attachments
    const attachmentsRes = await supplierInvoiceApi.listAttachments(parseInt(invoiceId!))
    setAttachments(attachmentsRes.data)
  }

  const handleDeleteAttachment = async (attachment: EntityAttachment) => {
    await supplierInvoiceApi.unlinkAttachment(parseInt(invoiceId!), attachment.attachment_id)
    setAttachments(attachments.filter(a => a.attachment_id !== attachment.attachment_id))
  }

  const handleDownloadAttachment = async (attachment: EntityAttachment) => {
    const response = await attachmentApi.download(attachment.attachment_id)
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', attachment.original_filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
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
      sent: 'Bokförd',
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
              Leverantörsfaktura #{invoice.our_invoice_number || invoice.id}
            </h1>
            <p className="text-gray-600">
              {supplier?.name} - {invoice.supplier_invoice_number}
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
                <dt className="text-sm font-medium text-gray-500">Leverantör</dt>
                <dd className="mt-1 text-sm text-gray-900">{supplier?.name || '-'}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Leverantörens fakturanr</dt>
                <dd className="mt-1 text-sm text-gray-900">{invoice.supplier_invoice_number}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Vårt fakturanummer</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {invoice.our_invoice_number || '-'}
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
              {invoice.ocr_number && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">OCR-nummer</dt>
                  <dd className="mt-1 text-sm text-gray-900">{invoice.ocr_number}</dd>
                </div>
              )}
              {invoice.reference && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Referens</dt>
                  <dd className="mt-1 text-sm text-gray-900">{invoice.reference}</dd>
                </div>
              )}
            </dl>
            {invoice.notes && (
              <div className="mt-4">
                <dt className="text-sm font-medium text-gray-500">Anteckningar</dt>
                <dd className="mt-1 text-sm text-gray-900">{invoice.notes}</dd>
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
                  {invoice.supplier_invoice_lines.map((line, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">{line.description}</td>
                      <td className="px-4 py-3 text-sm text-right font-mono">{line.quantity}</td>
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

          {/* Attachments */}
          <AttachmentManager
            attachments={attachments}
            config={{
              allowUpload: true,
              allowDelete: true,
            }}
            labels={{
              title: 'Bilagor',
              emptyState: 'Inga bilagor uppladdade',
              uploadButton: 'Välj fil att ladda upp',
              addMoreButton: 'Lägg till bilaga',
              deleteConfirm: (f) => `Ta bort bilagan "${f}"?`,
              uploadSuccess: 'Bilagan har laddats upp',
              uploadError: 'Kunde inte ladda upp bilagan',
              deleteError: 'Kunde inte ta bort bilagan',
              downloadError: 'Kunde inte ladda ner bilagan',
            }}
            onUpload={handleUploadAttachment}
            onDelete={handleDeleteAttachment}
            onDownload={handleDownloadAttachment}
          />
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Åtgärder</h2>
            <div className="space-y-2">
              {invoice.status === InvoiceStatus.DRAFT && (
                <button
                  onClick={handleRegister}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  <BookOpen className="w-4 h-4" />
                  {selectedCompany?.accounting_basis === 'accrual' ? 'Registrera och bokför' : 'Registrera'}
                </button>
              )}
              {invoice.status === InvoiceStatus.ISSUED && invoice.payment_status !== PaymentStatus.PAID && (
                <button
                  onClick={handleMarkPaid}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
                >
                  <DollarSign className="w-4 h-4" />
                  Markera som betald
                </button>
              )}
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
                  <dt className="text-gray-500">Kvarstår att betala</dt>
                  <dd className="text-red-600 font-semibold font-mono">
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
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
