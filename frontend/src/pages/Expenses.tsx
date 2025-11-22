import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Edit2, Trash2, Check, X, FileText, DollarSign, Upload, Download, Eye, BookOpen } from 'lucide-react'
import { companyApi, expenseApi, accountApi } from '@/services/api'
import type { Expense, ExpenseStatus, Account } from '@/types'

export default function Expenses() {
  const navigate = useNavigate()
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [employeeFilter, setEmployeeFilter] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  // Form state
  const [formData, setFormData] = useState({
    employee_name: '',
    expense_date: new Date().toISOString().split('T')[0],
    description: '',
    amount: '',
    vat_amount: '',
    expense_account_id: '',
    vat_account_id: '',
  })

  useEffect(() => {
    loadExpenses()
    loadAccounts()
  }, [statusFilter, employeeFilter])

  const loadExpenses = async () => {
    try {
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) {
        setLoading(false)
        return
      }
      const company = companiesRes.data[0]

      const params: any = {}
      if (statusFilter !== 'all') {
        params.status_filter = statusFilter
      }
      if (employeeFilter) {
        params.employee_name = employeeFilter
      }

      const expensesRes = await expenseApi.list(company.id, params)
      setExpenses(expensesRes.data)
    } catch (error) {
      console.error('Failed to load expenses:', error)
    } finally {
      setLoading(false)
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

  const handleCreate = () => {
    setEditingExpense(null)
    setSelectedFile(null)
    setFormData({
      employee_name: '',
      expense_date: new Date().toISOString().split('T')[0],
      description: '',
      amount: '',
      vat_amount: '',
      expense_account_id: '',
      vat_account_id: '',
    })
    setShowModal(true)
  }

  const handleEdit = (expense: Expense) => {
    setEditingExpense(expense)
    setSelectedFile(null)
    setFormData({
      employee_name: expense.employee_name,
      expense_date: expense.expense_date,
      description: expense.description,
      amount: expense.amount.toString(),
      vat_amount: expense.vat_amount.toString(),
      expense_account_id: expense.expense_account_id?.toString() || '',
      vat_account_id: expense.vat_account_id?.toString() || '',
    })
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const companiesRes = await companyApi.list()
      const company = companiesRes.data[0]

      const payload = {
        company_id: company.id,
        employee_name: formData.employee_name,
        expense_date: formData.expense_date,
        description: formData.description,
        amount: parseFloat(formData.amount),
        vat_amount: parseFloat(formData.vat_amount) || 0,
        expense_account_id: formData.expense_account_id ? parseInt(formData.expense_account_id) : null,
        vat_account_id: formData.vat_account_id ? parseInt(formData.vat_account_id) : null,
      }

      let expenseId: number
      if (editingExpense) {
        const response = await expenseApi.update(editingExpense.id, payload)
        expenseId = response.data.id
      } else {
        const response = await expenseApi.create(payload)
        expenseId = response.data.id
      }

      // Upload file if selected
      if (selectedFile) {
        await expenseApi.uploadReceipt(expenseId, selectedFile)
      }

      setShowModal(false)
      setSelectedFile(null)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to save expense:', error)
      alert('Kunde inte spara utlägget')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Är du säker på att du vill ta bort detta utlägg?')) return

    try {
      await expenseApi.delete(id)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to delete expense:', error)
      alert('Kunde inte ta bort utlägget')
    }
  }

  const handleSubmitForApproval = async (id: number) => {
    try {
      await expenseApi.submit(id)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to submit expense:', error)
      alert('Kunde inte skicka in utlägget för godkännande')
    }
  }

  const handleApprove = async (id: number) => {
    try {
      await expenseApi.approve(id)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to approve expense:', error)
      alert('Kunde inte godkänna utlägget')
    }
  }

  const handleReject = async (id: number) => {
    try {
      await expenseApi.reject(id)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to reject expense:', error)
      alert('Kunde inte avslå utlägget')
    }
  }

  const handleMarkPaid = async (id: number) => {
    const paidDate = prompt('Ange utbetalningsdatum (ÅÅÅÅ-MM-DD):', new Date().toISOString().split('T')[0])
    if (!paidDate) return

    // Find bank account 1930 (default bank account)
    const bankAccount = accounts.find(a => a.account_number === 1930)

    if (!bankAccount) {
      alert('Bankkonto 1930 hittades inte. Lägg till konto 1930 (Företagskonto/Bankgiro) först.')
      return
    }

    try {
      await expenseApi.markPaid(id, paidDate, bankAccount.id)
      await loadExpenses()
      alert('Utlägget har markerats som utbetalt och en verifikation har skapats')
    } catch (error: any) {
      console.error('Failed to mark expense as paid:', error)
      alert(`Kunde inte markera utlägget som utbetalat: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleBook = async (id: number) => {
    // Find liability accounts (e.g., 2890 Upplupna kostnader)
    const liabilityAccounts = accounts.filter(a =>
      a.account_number >= 2890 && a.account_number < 2900
    )

    if (liabilityAccounts.length === 0) {
      alert('Inget skuldkonto hittades (t.ex. 2890). Lägg till ett konto för anställdas utlägg först.')
      return
    }

    // Use first liability account or prompt if multiple
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
      await expenseApi.book(id, employeePayableAccountId)
      await loadExpenses()
      alert('Utlägget har bokförts och en verifikation har skapats')
    } catch (error: any) {
      console.error('Failed to book expense:', error)
      alert(`Kunde inte bokföra utlägget: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleFileUpload = async (expenseId: number, file: File) => {
    try {
      await expenseApi.uploadReceipt(expenseId, file)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to upload receipt:', error)
      alert('Kunde inte ladda upp kvittot')
    }
  }

  const handleDownloadReceipt = async (expenseId: number, filename: string) => {
    try {
      const response = await expenseApi.downloadReceipt(expenseId)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download receipt:', error)
      alert('Kunde inte ladda ner kvittot')
    }
  }

  const handleDeleteReceipt = async (expenseId: number) => {
    if (!confirm('Är du säker på att du vill ta bort kvittot?')) return

    try {
      await expenseApi.deleteReceipt(expenseId)
      await loadExpenses()
    } catch (error) {
      console.error('Failed to delete receipt:', error)
      alert('Kunde inte ta bort kvittot')
    }
  }

  const getStatusBadge = (status: ExpenseStatus) => {
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
      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${badges[status]}`}>
        {labels[status]}
      </span>
    )
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

  const expenseAccounts = accounts.filter(a =>
    a.account_number >= 4000 && a.account_number < 8000
  )

  const vatAccounts = accounts.filter(a =>
    a.account_number >= 2640 && a.account_number < 2650
  )

  const filteredExpenses = expenses.filter(expense => {
    if (statusFilter !== 'all' && expense.status !== statusFilter) return false
    if (employeeFilter && !expense.employee_name.toLowerCase().includes(employeeFilter.toLowerCase())) return false
    return true
  })

  const totalAmount = filteredExpenses.reduce((sum, e) => sum + Number(e.amount), 0)
  const totalVat = filteredExpenses.reduce((sum, e) => sum + Number(e.vat_amount), 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar utlägg...</p>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-4">Utlägg</h1>
        <p className="text-gray-600">Hantera personalutlägg och kvitton</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Totalt antal utlägg</h3>
          <p className="text-2xl font-bold">{filteredExpenses.length}</p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Total kostnad</h3>
          <p className="text-2xl font-bold">{formatCurrency(totalAmount)}</p>
        </div>
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Varav moms</h3>
          <p className="text-2xl font-bold">{formatCurrency(totalVat)}</p>
        </div>
      </div>

      {/* Filters and Actions */}
      <div className="card mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex gap-4 flex-1">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="all">Alla statusar</option>
                <option value="draft">Utkast</option>
                <option value="submitted">Inskickade</option>
                <option value="approved">Godkända</option>
                <option value="paid">Utbetalade</option>
                <option value="rejected">Avslagna</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Medarbetare</label>
              <input
                type="text"
                value={employeeFilter}
                onChange={(e) => setEmployeeFilter(e.target.value)}
                placeholder="Sök på namn..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleCreate}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              <Plus className="w-4 h-4" />
              Nytt utlägg
            </button>
          </div>
        </div>
      </div>

      {/* Expenses List */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Datum</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Medarbetare</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Beskrivning</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Belopp</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Moms</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Kvitto</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Åtgärder</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {filteredExpenses.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                    Inga utlägg hittades
                  </td>
                </tr>
              ) : (
                filteredExpenses.map((expense) => (
                  <tr key={expense.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{formatDate(expense.expense_date)}</td>
                    <td className="px-4 py-3 text-sm font-medium">{expense.employee_name}</td>
                    <td className="px-4 py-3 text-sm">{expense.description}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {formatCurrency(expense.amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {formatCurrency(expense.vat_amount)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {expense.receipt_filename ? (
                          <>
                            <button
                              onClick={() => handleDownloadReceipt(expense.id, expense.receipt_filename!)}
                              className="p-1 text-blue-600 hover:text-blue-800"
                              title="Ladda ner kvitto"
                            >
                              <Download className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteReceipt(expense.id)}
                              className="p-1 text-red-600 hover:text-red-800"
                              title="Ta bort kvitto"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </>
                        ) : (
                          <label className="cursor-pointer">
                            <input
                              type="file"
                              className="hidden"
                              accept=".jpg,.jpeg,.png,.pdf,.gif"
                              onChange={(e) => {
                                const file = e.target.files?.[0]
                                if (file) handleFileUpload(expense.id, file)
                              }}
                            />
                            <Upload className="w-4 h-4 text-gray-400 hover:text-gray-600" />
                          </label>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">{getStatusBadge(expense.status)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => navigate(`/expenses/${expense.id}`)}
                          className="p-1 text-gray-600 hover:text-gray-800"
                          title="Visa detaljer"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {expense.status === 'draft' && (
                          <>
                            <button
                              onClick={() => handleEdit(expense)}
                              className="p-1 text-indigo-600 hover:text-indigo-800"
                              title="Redigera"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleSubmitForApproval(expense.id)}
                              className="p-1 text-blue-600 hover:text-blue-800"
                              title="Skicka in för godkännande"
                            >
                              <FileText className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDelete(expense.id)}
                              className="p-1 text-red-600 hover:text-red-800"
                              title="Ta bort"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {expense.status === 'submitted' && (
                          <>
                            <button
                              onClick={() => handleEdit(expense)}
                              className="p-1 text-indigo-600 hover:text-indigo-800"
                              title="Redigera"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleApprove(expense.id)}
                              className="p-1 text-green-600 hover:text-green-800"
                              title="Godkänn"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleReject(expense.id)}
                              className="p-1 text-red-600 hover:text-red-800"
                              title="Avslå"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {expense.status === 'approved' && (
                          <>
                            {!expense.verification_id && (
                              <button
                                onClick={() => handleBook(expense.id)}
                                className="p-1 text-indigo-600 hover:text-indigo-800"
                                title="Bokför (skapa verifikation)"
                              >
                                <BookOpen className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              onClick={() => handleMarkPaid(expense.id)}
                              className="p-1 text-purple-600 hover:text-purple-800"
                              title="Markera som utbetald"
                            >
                              <DollarSign className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        {(expense.status === 'paid' || expense.status === 'rejected') && (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-2xl font-bold mb-4">
                {editingExpense ? 'Redigera utlägg' : 'Nytt utlägg'}
              </h2>
              <form onSubmit={handleSubmit}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Medarbetare *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.employee_name}
                      onChange={(e) => setFormData({ ...formData, employee_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Datum *
                    </label>
                    <input
                      type="date"
                      required
                      value={formData.expense_date}
                      onChange={(e) => setFormData({ ...formData, expense_date: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Beskrivning *
                    </label>
                    <textarea
                      required
                      rows={3}
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Belopp (inkl. moms) *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={formData.amount}
                        onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Momsbelopp
                      </label>
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
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Kostnadskonto
                      </label>
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
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Momskonto
                      </label>
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

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Kvitto (bilaga)
                    </label>
                    <div className="flex items-center gap-4">
                      <label className="flex-1 cursor-pointer">
                        <div className="flex items-center gap-2 px-4 py-2 border-2 border-dashed border-gray-300 rounded-md hover:border-primary-500 transition-colors">
                          <Upload className="w-5 h-5 text-gray-400" />
                          <span className="text-sm text-gray-600">
                            {selectedFile ? selectedFile.name : 'Välj fil (JPG, PNG, PDF)'}
                          </span>
                        </div>
                        <input
                          type="file"
                          className="hidden"
                          accept=".jpg,.jpeg,.png,.pdf,.gif"
                          onChange={(e) => {
                            const file = e.target.files?.[0]
                            if (file) setSelectedFile(file)
                          }}
                        />
                      </label>
                      {selectedFile && (
                        <button
                          type="button"
                          onClick={() => setSelectedFile(null)}
                          className="px-3 py-2 text-sm text-red-600 hover:text-red-800"
                        >
                          Ta bort
                        </button>
                      )}
                      {editingExpense?.receipt_filename && !selectedFile && (
                        <span className="text-sm text-green-600">
                          ✓ Kvitto uppladdat
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Godkända format: JPG, JPEG, PNG, GIF, PDF (max 10MB)
                    </p>
                  </div>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                  >
                    {editingExpense ? 'Spara ändringar' : 'Skapa utlägg'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
                  >
                    Avbryt
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
