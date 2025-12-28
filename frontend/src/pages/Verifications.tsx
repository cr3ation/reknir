import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Edit, Trash2, Lock, CheckCircle, AlertCircle, FileText } from 'lucide-react'
import { verificationApi, accountApi, postingTemplateApi } from '@/services/api'
import type { VerificationListItem, Account, Verification, PostingTemplate } from '@/types'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { useCompany } from '@/contexts/CompanyContext'
import { getErrorMessage } from '@/utils/errors'
import FiscalYearSelector from '@/components/FiscalYearSelector'

export default function Verifications() {
  const navigate = useNavigate()
  const { selectedCompany } = useCompany()
  const [allVerifications, setAllVerifications] = useState<VerificationListItem[]>([])
  const [verifications, setVerifications] = useState<VerificationListItem[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingVerification, setEditingVerification] = useState<Verification | null>(null)
  const { selectedFiscalYear } = useFiscalYear()

  const loadData = useCallback(async () => {
    if (!selectedCompany) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)

      // Load verifications
      const verificationsRes = await verificationApi.list(selectedCompany.id)
      setAllVerifications(verificationsRes.data)

      // Load accounts for selected fiscal year
      if (selectedFiscalYear) {
        const accountsRes = await accountApi.list(selectedCompany.id, selectedFiscalYear.id)
        setAccounts(accountsRes.data)
      }
    } catch (error) {
      console.error('Failed to load verifications:', error)
    } finally {
      setLoading(false)
    }
  }, [selectedCompany, selectedFiscalYear])

  const filterVerificationsByFiscalYear = useCallback(() => {
    if (!selectedFiscalYear) {
      setVerifications(allVerifications)
      return
    }

    // Filter verifications by fiscal year date range
    const filtered = allVerifications.filter((v) => {
      const transactionDate = new Date(v.transaction_date)
      const startDate = new Date(selectedFiscalYear.start_date)
      const endDate = new Date(selectedFiscalYear.end_date)
      return transactionDate >= startDate && transactionDate <= endDate
    })

    setVerifications(filtered)
  }, [selectedFiscalYear, allVerifications])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    filterVerificationsByFiscalYear()
  }, [filterVerificationsByFiscalYear])

  const handleDelete = async (id: number) => {
    if (!confirm(
      'VARNING: Radering av verifikationer är endast tillåtet i utvecklingsläge!\n\n' +
      'I produktion ska du istället använda korrigerande verifikationer enligt god redovisningssed.\n\n' +
      'Är du säker på att du vill radera denna verifikation?'
    )) return

    try {
      await verificationApi.delete(id)
      await loadData()
    } catch (error) {
      console.error('Failed to delete verification:', error)
      alert(getErrorMessage(error, 'Kunde inte radera verifikationen'))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar verifikationer...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Verifikationer</h1>
        <div className="flex items-center gap-4">
          <FiscalYearSelector />
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4 mr-2" />
            Ny verifikation
          </button>
        </div>
      </div>

      {verifications.length === 0 ? (
        <div className="card">
          <p className="text-gray-600">
            Inga verifikationer ännu. Skapa din första verifikation för att registrera
            transaktioner!
          </p>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Ver.nr
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Serie
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Datum
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Beskrivning
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Belopp
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                  Åtgärder
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {verifications.map((verification) => (
                <tr
                  key={verification.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/verifications/${verification.id}`)}
                >
                  <td className="px-4 py-3 text-sm font-medium">
                    {verification.verification_number}
                  </td>
                  <td className="px-4 py-3 text-sm">{verification.series}</td>
                  <td className="px-4 py-3 text-sm">{verification.transaction_date}</td>
                  <td className="px-4 py-3 text-sm max-w-md truncate">
                    {verification.description}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-mono">
                    {verification.total_amount.toLocaleString('sv-SE', {
                      style: 'currency',
                      currency: 'SEK',
                    })}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {verification.locked ? (
                      <span className="inline-flex items-center text-gray-600" title="Låst">
                        <Lock className="w-4 h-4" />
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-green-600" title="Olåst">
                        <CheckCircle className="w-4 h-4" />
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {!verification.locked && (
                        <>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              // Load full verification and edit
                              verificationApi.get(verification.id).then((res) => {
                                setEditingVerification(res.data)
                                setShowCreateModal(true)
                              })
                            }}
                            className="p-1 text-blue-600 hover:text-blue-800"
                            title="Redigera"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDelete(verification.id)
                            }}
                            className="p-1 text-red-600 hover:text-red-800"
                            title="Radera"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showCreateModal && selectedCompany && selectedFiscalYear && (
        <CreateVerificationModal
          companyId={selectedCompany.id}
          fiscalYearId={selectedFiscalYear.id}
          accounts={accounts}
          verification={editingVerification}
          onClose={() => {
            setShowCreateModal(false)
            setEditingVerification(null)
          }}
          onSuccess={() => {
            setShowCreateModal(false)
            setEditingVerification(null)
            loadData()
          }}
        />
      )}
    </div>
  )
}



// Create/Edit Verification Modal Component
interface CreateVerificationModalProps {
  companyId: number
  fiscalYearId: number
  accounts: Account[]
  verification: Verification | null
  onClose: () => void
  onSuccess: () => void
}

function CreateVerificationModal({
  companyId,
  fiscalYearId,
  accounts,
  verification,
  onClose,
  onSuccess,
}: CreateVerificationModalProps) {
  const isEditing = verification !== null

  const [formData, setFormData] = useState({
    series: verification?.series || 'A',
    transaction_date: verification?.transaction_date || new Date().toISOString().split('T')[0],
    description: verification?.description || '',
  })

  const [lines, setLines] = useState(
    verification?.transaction_lines || [
      { account_id: 0, debit: 0, credit: 0, description: '' },
      { account_id: 0, debit: 0, credit: 0, description: '' },
    ]
  )

  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [templates, setTemplates] = useState<PostingTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)

  // Load templates when component mounts
  useEffect(() => {
    if (!isEditing) {
      loadTemplates()
    }
  }, [isEditing])

  const loadTemplates = async () => {
    try {
      setTemplatesLoading(true)
      const response = await postingTemplateApi.list(companyId)
      setTemplates(response.data)
    } catch (error) {
      console.error('Failed to load templates:', error)
    } finally {
      setTemplatesLoading(false)
    }
  }

  // Apply template using the new API
  const applyTemplate = async (templateId: number, amount: number) => {
    try {
      setLoading(true)
      const executionResult = await postingTemplateApi.execute(templateId, {
        amount,
        fiscal_year_id: fiscalYearId
      })
      const result = executionResult.data

      // Apply template metadata
      setFormData({
        ...formData,
        description: result.template_name // Use template name as default description
      })

      // Convert template execution result to transaction lines
      const newLines = result.posting_lines.map((line) => ({
        account_id: line.account_id,
        debit: line.debit,
        credit: line.credit,
        description: line.description || '',
      }))

      setLines(newLines)
      setShowTemplates(false)
    } catch (error: any) {
      console.error('Failed to execute template:', error)
      setError(error.response?.data?.detail || 'Kunde inte tillämpa mall')
    } finally {
      setLoading(false)
    }
  }

  const addLine = () => {
    setLines([...lines, { account_id: 0, debit: 0, credit: 0, description: '' }])
  }

  const removeLine = (index: number) => {
    if (lines.length <= 2) return // Keep at least 2 lines
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: string, value: string | number) => {
    const newLines = [...lines]
    newLines[index] = { ...newLines[index], [field]: value }
    setLines(newLines)
  }

  const totalDebit = lines.reduce((sum, line) => sum + (Number(line.debit) || 0), 0)
  const totalCredit = lines.reduce((sum, line) => sum + (Number(line.credit) || 0), 0)
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    if (!isBalanced) {
      setError('Verifikationen är inte i balans! Debet måste vara lika med kredit.')
      setLoading(false)
      return
    }

    try {
      const data = {
        company_id: companyId,
        fiscal_year_id: fiscalYearId,
        ...formData,
        transaction_lines: lines.map((line) => ({
          account_id: Number(line.account_id),
          debit: Number(line.debit) || 0,
          credit: Number(line.credit) || 0,
          description: line.description || undefined,
        })),
      }

      if (isEditing) {
        await verificationApi.update(verification.id!, {
          description: formData.description,
          transaction_date: formData.transaction_date,
        })
      } else {
        await verificationApi.create(data)
      }

      onSuccess()
    } catch (err) {
      setError(getErrorMessage(err, 'Ett fel uppstod'))
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full my-8 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="text-2xl font-bold">
            {isEditing ? 'Redigera verifikation' : 'Ny verifikation'}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4">
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center">
              <AlertCircle className="w-5 h-5 mr-2" />
              {error}
            </div>
          )}

          {/* Template Selection */}
          {!isEditing && accounts.length > 0 && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-blue-600 mr-2" />
                  <h3 className="font-medium text-blue-900">Mallar för vanliga transaktioner</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setShowTemplates(!showTemplates)}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  {showTemplates ? 'Dölj mallar' : 'Visa mallar'}
                </button>
              </div>

              {showTemplates && (
                <div className="mt-3">
                  {templatesLoading ? (
                    <div className="text-center py-4">
                      <p className="text-sm text-gray-500">Laddar mallar...</p>
                    </div>
                  ) : templates.length === 0 ? (
                    <div className="text-center py-4 bg-gray-50 rounded border">
                      <p className="text-sm text-gray-600">Inga mallar hittades</p>
                      <p className="text-xs text-gray-500 mt-1">Skapa mallar i administrationen för att använda dem här</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      {templates.filter(t => t.id != null).map((template) => (
                        <div key={template.id} className="bg-white p-3 rounded border border-blue-200">
                          <h4 className="font-medium text-sm mb-1">{template.name}</h4>
                          <p className="text-xs text-gray-600 mb-2">{template.description}</p>
                          <p className="text-xs text-gray-500 mb-2">
                            {template.template_lines.length} rader {template.updated_at && `• Senast uppdaterad: ${new Date(template.updated_at).toLocaleDateString('sv-SE')}`}
                          </p>
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              placeholder="Total"
                              className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
                              id={`template-amount-${template.id}`}
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const amountInput = document.getElementById(
                                  `template-amount-${template.id}`
                                ) as HTMLInputElement
                                const amount = Number(amountInput.value) || 1000
                                applyTemplate(template.id!, amount)
                              }}
                              className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                              disabled={loading}
                            >
                              {loading ? 'Tillämpar...' : 'Använd'}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Serie *
              </label>
              <input
                type="text"
                required
                maxLength={10}
                value={formData.series}
                onChange={(e) => setFormData({ ...formData, series: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                disabled={isEditing}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Datum *
              </label>
              <input
                type="date"
                required
                value={formData.transaction_date}
                onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Beskrivning *
              </label>
              <input
                type="text"
                required
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="t.ex. Inköp av material"
              />
            </div>
          </div>

          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium">Transaktionsrader</h3>
              <button
                type="button"
                onClick={addLine}
                className="text-sm text-indigo-600 hover:text-indigo-800"
                disabled={isEditing}
              >
                + Lägg till rad
              </button>
            </div>

            {accounts.length === 0 && (
              <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
                <p className="text-yellow-800 text-sm">
                  ⚠️ Inga konton hittades. Kontrollera att BAS-kontoplanen är importerad.
                </p>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                      Konto *
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                      Beskrivning
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">
                      Debet
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">
                      Kredit
                    </th>
                    {!isEditing && (
                      <th className="px-4 py-2 text-center text-xs font-medium text-gray-500">
                        Åtgärd
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {lines.map((line, index) => {
                    // When editing, include the account from the line even if it's inactive
                    const accountExists = accounts.find(a => a.id === line.account_id)
                    const lineHasAccount = line.account_number && line.account_name

                    return (
                    <tr key={index}>
                      <td className="px-4 py-2">
                        <select
                          required
                          value={line.account_id}
                          onChange={(e) => updateLine(index, 'account_id', e.target.value)}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                          disabled={isEditing}
                        >
                          <option value={0}>Välj konto...</option>
                          {/* Show the line's account first if it's not in the active accounts list (inactive) */}
                          {isEditing && !accountExists && lineHasAccount && (
                            <option key={line.account_id} value={line.account_id}>
                              ⚠ {line.account_number} - {line.account_name}
                            </option>
                          )}
                          {/* Show all active accounts */}
                          {accounts.map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.account_number} - {account.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={line.description}
                          onChange={(e) => updateLine(index, 'description', e.target.value)}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                          placeholder="Radtext (valfritt)"
                          disabled={isEditing}
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.debit || ''}
                          onChange={(e) => updateLine(index, 'debit', e.target.value)}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm text-right"
                          disabled={isEditing}
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={line.credit || ''}
                          onChange={(e) => updateLine(index, 'credit', e.target.value)}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm text-right"
                          disabled={isEditing}
                        />
                      </td>
                      {!isEditing && (
                        <td className="px-4 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => removeLine(index)}
                            className="text-red-600 hover:text-red-800 disabled:opacity-50"
                            disabled={lines.length <= 2}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                    )
                  })}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={2} className="px-4 py-2 text-right font-medium">
                      Totalt:
                    </td>
                    <td className="px-4 py-2 text-right font-mono font-bold">
                      {totalDebit.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right font-mono font-bold">
                      {totalCredit.toFixed(2)}
                    </td>
                    {!isEditing && <td></td>}
                  </tr>
                  <tr>
                    <td colSpan={!isEditing ? 5 : 4} className="px-4 py-2 text-center">
                      {isBalanced ? (
                        <span className="inline-flex items-center text-green-600 font-medium">
                          <CheckCircle className="w-4 h-4 mr-2" />
                          I balans
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-red-600 font-medium">
                          <AlertCircle className="w-4 h-4 mr-2" />
                          Ej i balans (skillnad: {Math.abs(totalDebit - totalCredit).toFixed(2)})
                        </span>
                      )}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 sticky bottom-0 bg-white">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Avbryt
            </button>
            <button
              type="submit"
              disabled={loading || !isBalanced || isEditing}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? 'Sparar...'
                : isEditing
                ? 'Kan inte redigera verifikationer'
                : 'Skapa verifikation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
