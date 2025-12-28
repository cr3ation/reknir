import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, Lock, CheckCircle, AlertCircle } from 'lucide-react'
import { verificationApi, accountApi, attachmentApi } from '@/services/api'
import type { Verification, Account, EntityAttachment } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import AttachmentManager from '@/components/AttachmentManager'

export default function VerificationDetail() {
  const { verificationId } = useParams<{ verificationId: string }>()
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [verification, setVerification] = useState<Verification | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [attachments, setAttachments] = useState<EntityAttachment[]>([])
  const [loading, setLoading] = useState(true)

  const loadVerification = useCallback(async () => {
    try {
      const response = await verificationApi.get(parseInt(verificationId!))
      setVerification(response.data)

      // Load attachments
      const attachmentsRes = await verificationApi.listAttachments(parseInt(verificationId!))
      setAttachments(attachmentsRes.data)

      setLoading(false)
    } catch (error) {
      console.error('Failed to load verification:', error)
      alert('Kunde inte ladda verifikationen')
      navigate('/verifications')
    }
  }, [verificationId, navigate])

  const loadAccounts = useCallback(async () => {
    if (!selectedCompany || !selectedFiscalYear) return

    try {
      // Fetch all accounts including inactive ones to properly check status
      const accountsRes = await accountApi.list(selectedCompany.id, selectedFiscalYear.id, { active_only: false })
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load accounts:', error)
    }
  }, [selectedCompany, selectedFiscalYear])

  useEffect(() => {
    loadVerification()
    loadAccounts()
  }, [loadVerification, loadAccounts])

  // Attachment handlers for AttachmentManager
  const handleUploadAttachment = async (file: File) => {
    if (!selectedCompany) throw new Error('No company selected')

    const uploadRes = await attachmentApi.upload(selectedCompany.id, file)
    await verificationApi.linkAttachment(parseInt(verificationId!), uploadRes.data.id)

    const attachmentsRes = await verificationApi.listAttachments(parseInt(verificationId!))
    setAttachments(attachmentsRes.data)
  }

  const handleDeleteAttachment = async (attachment: EntityAttachment) => {
    await verificationApi.unlinkAttachment(parseInt(verificationId!), attachment.attachment_id)
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

  const getAccountInfo = (accountId: number, accountNumber?: number, accountName?: string) => {
    // Use account info from transaction line if available (handles inactive accounts)
    if (accountNumber && accountName) {
      const account = accounts.find(a => a.id === accountId)
      const isInactive = account && !account.active
      return {
        text: `${accountNumber} - ${accountName}`,
        isInactive,
        isMissing: false
      }
    }

    // Fallback to lookup in accounts list
    const account = accounts.find(a => a.id === accountId)
    if (account) {
      return {
        text: `${account.account_number} - ${account.name}`,
        isInactive: !account.active,
        isMissing: false
      }
    }

    // Account not found in database (data integrity issue)
    return {
      text: `${accountNumber || accountId} (saknas i kontoplanen)`,
      isInactive: false,
      isMissing: true
    }
  }

  const calculateTotals = () => {
    if (!verification) return { debit: 0, credit: 0 }

    const debitTotal = verification.transaction_lines.reduce(
      (sum, line) => sum + parseFloat(line.debit.toString()),
      0
    )
    const creditTotal = verification.transaction_lines.reduce(
      (sum, line) => sum + parseFloat(line.credit.toString()),
      0
    )

    return { debit: debitTotal, credit: creditTotal }
  }

  if (loading || !verification) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar...</p>
      </div>
    )
  }

  const totals = calculateTotals()
  const isBalanced = Math.abs(totals.debit - totals.credit) < 0.01

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/verifications" className="text-gray-600 hover:text-gray-900">
            <ArrowLeft className="w-6 h-6" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold">
              Verifikation {verification.series}{verification.verification_number}
            </h1>
            <p className="text-gray-600">{verification.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {verification.locked ? (
            <div className="flex items-center gap-2 px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm font-semibold">
              <Lock className="w-4 h-4" />
              Låst
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
              <CheckCircle className="w-4 h-4" />
              Olåst
            </div>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Information */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Information</h2>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Verifikationsnummer</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {verification.series}{verification.verification_number}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Transaktionsdatum</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(verification.transaction_date)}
                </dd>
              </div>
              {verification.registration_date && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Registreringsdatum</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {formatDate(verification.registration_date)}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-sm font-medium text-gray-500">Status</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {verification.locked ? 'Låst' : 'Olåst'}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-sm font-medium text-gray-500">Beskrivning</dt>
                <dd className="mt-1 text-sm text-gray-900">{verification.description}</dd>
              </div>
            </dl>
          </div>

          {/* Transaction Lines */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Transaktionsrader</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Konto
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Beskrivning
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Debet
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Kredit
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {verification.transaction_lines.map((line, index) => {
                    const accountInfo = getAccountInfo(line.account_id, line.account_number, line.account_name)
                    return (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">
                        {accountInfo.isInactive && (
                          <span className="text-amber-600 mr-1" title="Inaktivt konto">⚠</span>
                        )}
                        {accountInfo.isMissing && (
                          <span className="text-red-600 mr-1" title="Konto saknas">⛔</span>
                        )}
                        <span className={accountInfo.isInactive ? 'text-gray-600' : ''}>
                          {accountInfo.text}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {line.description || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono">
                        {parseFloat(line.debit.toString()) > 0
                          ? formatCurrency(parseFloat(line.debit.toString()))
                          : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-mono">
                        {parseFloat(line.credit.toString()) > 0
                          ? formatCurrency(parseFloat(line.credit.toString()))
                          : '-'}
                      </td>
                    </tr>
                    )
                  })}
                  {/* Totals Row */}
                  <tr className="bg-gray-50 font-semibold">
                    <td colSpan={2} className="px-4 py-3 text-sm">
                      Summa
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {formatCurrency(totals.debit)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {formatCurrency(totals.credit)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Balance Check */}
            <div className="mt-4 p-4 rounded-md bg-gray-50">
              {isBalanced ? (
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">Verifikationen är balanserad</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-red-700">
                  <AlertCircle className="w-5 h-5" />
                  <span className="font-medium">
                    Varning: Verifikationen är inte balanserad! Differens:{' '}
                    {formatCurrency(totals.debit - totals.credit)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Attachments */}
          <AttachmentManager
            attachments={attachments}
            config={{
              allowUpload: !verification.locked,
              allowDelete: !verification.locked,
            }}
            labels={{
              title: 'Bokföringsunderlag',
              emptyState: 'Inga underlag uppladdade',
              uploadButton: 'Välj fil att ladda upp',
              addMoreButton: 'Lägg till underlag',
              deleteConfirm: (f) => `Ta bort underlaget "${f}"?`,
              uploadSuccess: 'Underlaget har laddats upp',
              uploadError: 'Kunde inte ladda upp underlaget',
              deleteError: 'Kunde inte ta bort underlaget',
              downloadError: 'Kunde inte ladda ner underlaget',
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
              {!verification.locked && (
                <Link
                  to="/verifications"
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  <FileText className="w-4 h-4" />
                  Redigera
                </Link>
              )}
              {verification.locked && (
                <p className="text-sm text-gray-600">
                  Låsta verifikationer kan inte redigeras.
                </p>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Sammanfattning</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Antal rader</dt>
                <dd className="text-gray-900 font-semibold">
                  {verification.transaction_lines.length}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Total debet</dt>
                <dd className="text-gray-900 font-semibold font-mono">
                  {formatCurrency(totals.debit)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Total kredit</dt>
                <dd className="text-gray-900 font-semibold font-mono">
                  {formatCurrency(totals.credit)}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
