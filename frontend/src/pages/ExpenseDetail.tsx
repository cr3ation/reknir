import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Edit2, Check, X, FileText, DollarSign, BookOpen, Download, Upload, Trash2 } from 'lucide-react'
import { expenseApi, accountApi, attachmentApi } from '@/services/api'
import type { Expense, Account, EntityAttachment } from '@/types'
import { useCompany } from '@/contexts/CompanyContext'
import { useFiscalYear } from '@/contexts/FiscalYearContext'

export default function ExpenseDetail() {
  const { expenseId } = useParams<{ expenseId: string }>()
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const { selectedFiscalYear } = useFiscalYear()
  const [expense, setExpense] = useState<Expense | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [attachments, setAttachments] = useState<EntityAttachment[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  const [formData, setFormData] = useState({
    employee_name: '',
    expense_date: '',
    description: '',
    amount: '',
    vat_amount: '',
    expense_account_id: '',
    vat_account_id: '',
  })

  useEffect(() => {
    loadExpense()
    loadAccounts()
  }, [expenseId, selectedCompany])

  const loadExpense = async () => {
    try {
      const response = await expenseApi.get(parseInt(expenseId!))
      setExpense(response.data)
      setFormData({
        employee_name: response.data.employee_name,
        expense_date: response.data.expense_date,
        description: response.data.description,
        amount: response.data.amount.toString(),
        vat_amount: response.data.vat_amount.toString(),
        expense_account_id: response.data.expense_account_id?.toString() || '',
        vat_account_id: response.data.vat_account_id?.toString() || '',
      })

      // Load attachments
      const attachmentsRes = await expenseApi.listAttachments(parseInt(expenseId!))
      setAttachments(attachmentsRes.data)

      setLoading(false)
    } catch (error) {
      console.error('Failed to load expense:', error)
      alert('Kunde inte ladda utlägget')
      navigate('/expenses')
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

  const handleSave = async () => {
    try {
      const payload = {
        employee_name: formData.employee_name,
        expense_date: formData.expense_date,
        description: formData.description,
        amount: parseFloat(formData.amount),
        vat_amount: parseFloat(formData.vat_amount) || 0,
        expense_account_id: formData.expense_account_id ? parseInt(formData.expense_account_id) : null,
        vat_account_id: formData.vat_account_id ? parseInt(formData.vat_account_id) : null,
      }

      const response = await expenseApi.update(parseInt(expenseId!), payload)

      if (selectedFile && selectedCompany) {
        // Upload file and link to expense
        const uploadRes = await attachmentApi.upload(selectedCompany.id, selectedFile)
        await expenseApi.linkAttachment(parseInt(expenseId!), uploadRes.data.id)
      }

      setExpense(response.data)
      setEditing(false)
      setSelectedFile(null)
      await loadExpense()
    } catch (error) {
      console.error('Failed to save expense:', error)
      alert('Kunde inte spara utlägget')
    }
  }

  const handleApprove = async () => {
    try {
      await expenseApi.approve(parseInt(expenseId!))
      await loadExpense()
    } catch (error) {
      console.error('Failed to approve:', error)
      alert('Kunde inte godkänna utlägget')
    }
  }

  const handleReject = async () => {
    try {
      await expenseApi.reject(parseInt(expenseId!))
      await loadExpense()
    } catch (error) {
      console.error('Failed to reject:', error)
      alert('Kunde inte avslå utlägget')
    }
  }

  const handleBook = async () => {
    const liabilityAccounts = accounts.filter(a => a.account_number >= 2890 && a.account_number < 2900)

    if (liabilityAccounts.length === 0) {
      alert('Inget skuldkonto hittades (t.ex. 2890). Lägg till ett konto för anställdas utlägg först.')
      return
    }

    let employeePayableAccountId = liabilityAccounts[0].id
    if (liabilityAccounts.length > 1) {
      const accountOptions = liabilityAccounts.map(a => `${a.account_number} ${a.name}`).join('\n')
      const accountNumber = prompt(
        `Välj skuldkonto för utlägget:\n${accountOptions}\n\nAnge kontonummer:`,
        liabilityAccounts[0].account_number.toString()
      )
      if (!accountNumber) return

      const selectedAccount = liabilityAccounts.find(a => a.account_number.toString() === accountNumber)
      if (!selectedAccount) {
        alert('Ogiltigt kontonummer')
        return
      }
      employeePayableAccountId = selectedAccount.id
    }

    try {
      await expenseApi.book(parseInt(expenseId!), employeePayableAccountId)
      await loadExpense()
      alert('Utlägget har bokförts och en verifikation har skapats')
    } catch (error: any) {
      console.error('Failed to book:', error)
      alert(`Kunde inte bokföra: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleMarkPaid = async () => {
    const paidDate = prompt('Ange utbetalningsdatum (ÅÅÅÅ-MM-DD):', new Date().toISOString().split('T')[0])
    if (!paidDate) return

    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    try {
      await expenseApi.markPaid(parseInt(expenseId!), paidDate, bankAccount.id)
      await loadExpense()
      alert('Utlägget har markerats som utbetalt och en verifikation har skapats')
    } catch (error: any) {
      console.error('Failed to mark paid:', error)
      alert(`Kunde inte markera som utbetald: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDownloadAttachment = async (attachment: EntityAttachment) => {
    try {
      const response = await attachmentApi.download(attachment.attachment_id)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', attachment.original_filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download attachment:', error)
      alert('Kunde inte ladda ner kvittot')
    }
  }

  const handleDeleteAttachment = async (attachment: EntityAttachment) => {
    if (!confirm(`Ta bort kvittot "${attachment.original_filename}"?`)) return
    try {
      await expenseApi.unlinkAttachment(parseInt(expenseId!), attachment.attachment_id)
      setAttachments(attachments.filter(a => a.attachment_id !== attachment.attachment_id))
    } catch (error) {
      console.error('Failed to delete attachment:', error)
      alert('Kunde inte ta bort kvittot')
    }
  }

  const handleUploadAttachment = async () => {
    if (!selectedFile || !selectedCompany) return

    try {
      setUploading(true)
      const uploadRes = await attachmentApi.upload(selectedCompany.id, selectedFile)
      await expenseApi.linkAttachment(parseInt(expenseId!), uploadRes.data.id)

      setSelectedFile(null)
      const attachmentsRes = await expenseApi.listAttachments(parseInt(expenseId!))
      setAttachments(attachmentsRes.data)
      alert('Kvittot har laddats upp')
    } catch (error) {
      console.error('Failed to upload attachment:', error)
      alert('Kunde inte ladda upp kvittot')
    } finally {
      setUploading(false)
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
      submitted: 'bg-blue-100 text-blue-800',
      approved: 'bg-green-100 text-green-800',
      paid: 'bg-purple-100 text-purple-800',
      rejected: 'bg-red-100 text-red-800',
    }
    const labels = {
      draft: 'Utkast',
      submitted: 'Inskickad',
      approved: 'Godkänd',
      paid: 'Utbetald',
      rejected: 'Avslagen',
    }
    return (
      <span className={`px-3 py-1 text-sm font-semibold rounded-full ${badges[status as keyof typeof badges]}`}>
        {labels[status as keyof typeof labels]}
      </span>
    )
  }

  const expenseAccounts = accounts.filter(a => a.account_number >= 4000 && a.account_number < 8000)
  const vatAccounts = accounts.filter(a => a.account_number >= 2640 && a.account_number < 2650)

  // Can edit if not booked (no verification) and not paid
  const canEdit = expense && !expense.verification_id && expense.status !== 'paid'

  if (loading || !expense) {
    return <div className="flex items-center justify-center h-64"><p className="text-gray-500">Laddar...</p></div>
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/expenses" className="text-gray-600 hover:text-gray-900">
            <ArrowLeft className="w-6 h-6" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold">Utlägg #{expense.id}</h1>
            <p className="text-gray-600">{expense.employee_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {getStatusBadge(expense.status)}
          {canEdit && !editing && (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              <Edit2 className="w-4 h-4" />
              Redigera
            </button>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Detaljer</h2>

            {editing ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Medarbetare</label>
                  <input
                    type="text"
                    value={formData.employee_name}
                    onChange={(e) => setFormData({ ...formData, employee_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Datum</label>
                  <input
                    type="date"
                    value={formData.expense_date}
                    onChange={(e) => setFormData({ ...formData, expense_date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Beskrivning</label>
                  <textarea
                    rows={3}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Belopp (inkl. moms)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.amount}
                      onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Momsbelopp</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.vat_amount}
                      onChange={(e) => setFormData({ ...formData, vat_amount: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Kostnadskonto</label>
                    <select
                      value={formData.expense_account_id}
                      onChange={(e) => setFormData({ ...formData, expense_account_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    >
                      <option value="">Välj konto...</option>
                      {expenseAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.account_number} - {account.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Momskonto</label>
                    <select
                      value={formData.vat_account_id}
                      onChange={(e) => setFormData({ ...formData, vat_account_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    >
                      <option value="">Välj konto...</option>
                      {vatAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.account_number} - {account.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={handleSave}
                    className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                  >
                    Spara ändringar
                  </button>
                  <button
                    onClick={() => {
                      setEditing(false)
                      setSelectedFile(null)
                    }}
                    className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
                  >
                    Avbryt
                  </button>
                </div>
              </div>
            ) : (
              <dl className="space-y-3">
                <div>
                  <dt className="text-sm font-medium text-gray-500">Medarbetare</dt>
                  <dd className="mt-1 text-sm text-gray-900">{expense.employee_name}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Datum</dt>
                  <dd className="mt-1 text-sm text-gray-900">{formatDate(expense.expense_date)}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Beskrivning</dt>
                  <dd className="mt-1 text-sm text-gray-900">{expense.description}</dd>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Belopp</dt>
                    <dd className="mt-1 text-lg font-semibold text-gray-900">{formatCurrency(expense.amount)}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Moms</dt>
                    <dd className="mt-1 text-lg font-semibold text-gray-900">{formatCurrency(expense.vat_amount)}</dd>
                  </div>
                </div>
                {expense.expense_account_id && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Kostnadskonto</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {accounts.find(a => a.id === expense.expense_account_id)?.account_number} - {accounts.find(a => a.id === expense.expense_account_id)?.name}
                    </dd>
                  </div>
                )}
                {expense.vat_account_id && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Momskonto</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {accounts.find(a => a.id === expense.vat_account_id)?.account_number} - {accounts.find(a => a.id === expense.vat_account_id)?.name}
                    </dd>
                  </div>
                )}
              </dl>
            )}
          </div>

          {/* Receipt/Attachments */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Kvitto</h2>

            {/* Existing attachments */}
            {attachments.length > 0 && (
              <div className="space-y-2 mb-4">
                {attachments.map((attachment) => (
                  <div key={attachment.link_id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <FileText className="w-6 h-6 text-gray-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{attachment.original_filename}</p>
                      <p className="text-xs text-gray-500">
                        {(attachment.size_bytes / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      onClick={() => handleDownloadAttachment(attachment)}
                      className="p-2 text-blue-600 hover:text-blue-800"
                      title="Ladda ner"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteAttachment(attachment)}
                      className="p-2 text-red-600 hover:text-red-800"
                      title="Ta bort"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Upload new attachment */}
            {selectedFile ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                  <FileText className="w-6 h-6 text-blue-600" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-blue-900">{selectedFile.name}</p>
                    <p className="text-xs text-blue-700">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedFile(null)}
                    className="text-blue-600 hover:text-blue-800"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <button
                  onClick={handleUploadAttachment}
                  disabled={uploading}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
                >
                  {uploading ? 'Laddar upp...' : 'Ladda upp kvitto'}
                </button>
              </div>
            ) : (
              <div>
                {attachments.length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    <Upload className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p className="mb-4">Inget kvitto uppladdat</p>
                  </div>
                )}
                <label className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  {attachments.length > 0 ? 'Lägg till kvitto' : 'Välj fil att ladda upp'}
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.gif"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="hidden"
                  />
                </label>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Åtgärder</h2>
            <div className="space-y-2">
              {expense.status === 'submitted' && (
                <>
                  <button
                    onClick={handleApprove}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                  >
                    <Check className="w-4 h-4" />
                    Godkänn
                  </button>
                  <button
                    onClick={handleReject}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                  >
                    <X className="w-4 h-4" />
                    Avslå
                  </button>
                </>
              )}
              {expense.status === 'approved' && !expense.verification_id && (
                <button
                  onClick={handleBook}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  <BookOpen className="w-4 h-4" />
                  Bokför
                </button>
              )}
              {expense.status === 'approved' && (
                <button
                  onClick={handleMarkPaid}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
                >
                  <DollarSign className="w-4 h-4" />
                  Markera som utbetald
                </button>
              )}
              {expense.verification_id && (
                <Link
                  to={`/verifications/${expense.verification_id}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                >
                  <FileText className="w-4 h-4" />
                  Visa verifikation
                </Link>
              )}
            </div>
          </div>

          {/* Info */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">Information</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Skapad</dt>
                <dd className="text-gray-900">{formatDate(expense.created_at)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Senast uppdaterad</dt>
                <dd className="text-gray-900">{formatDate(expense.updated_at)}</dd>
              </div>
              {expense.approved_date && (
                <div>
                  <dt className="text-gray-500">Godkänd</dt>
                  <dd className="text-gray-900">{formatDate(expense.approved_date)}</dd>
                </div>
              )}
              {expense.paid_date && (
                <div>
                  <dt className="text-gray-500">Utbetald</dt>
                  <dd className="text-gray-900">{formatDate(expense.paid_date)}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
