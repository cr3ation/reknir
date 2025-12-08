import { useEffect, useState } from 'react'
import { Plus, Edit, Trash2, Lock, CheckCircle, AlertCircle, FileText } from 'lucide-react'
import { verificationApi, accountApi } from '@/services/api'
import type { VerificationListItem, Account, Verification } from '@/types'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { useCompany } from '@/contexts/CompanyContext'

export default function Verifications() {
  const { selectedCompany } = useCompany()
  const [allVerifications, setAllVerifications] = useState<VerificationListItem[]>([])
  const [verifications, setVerifications] = useState<VerificationListItem[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingVerification, setEditingVerification] = useState<Verification | null>(null)
  const { selectedFiscalYear, loadFiscalYears } = useFiscalYear()

  useEffect(() => {
    loadData()
  }, [selectedCompany])

  useEffect(() => {
    filterVerificationsByFiscalYear()
  }, [selectedFiscalYear, allVerifications])

  const loadData = async () => {
    if (!selectedCompany) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      // Load fiscal years for this company
      await loadFiscalYears(selectedCompany.id)

      const [verificationsRes, accountsRes] = await Promise.all([
        verificationApi.list(selectedCompany.id),
        accountApi.list(selectedCompany.id),
      ])
      setAllVerifications(verificationsRes.data)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load verifications:', error)
    } finally {
      setLoading(false)
    }
  }

  const filterVerificationsByFiscalYear = () => {
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
  }

  const handleDelete = async (id: number) => {
    if (!confirm(
      'VARNING: Radering av verifikationer är endast tillåtet i utvecklingsläge!\n\n' +
      'I produktion ska du istället använda korrigerande verifikationer enligt god redovisningssed.\n\n' +
      'Är du säker på att du vill radera denna verifikation?'
    )) return

    try {
      await verificationApi.delete(id)
      await loadData()
    } catch (error: any) {
      console.error('Failed to delete verification:', error)
      const errorMsg = error.response?.data?.detail || 'Kunde inte radera verifikationen'
      alert(errorMsg)
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
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Ny verifikation
        </button>
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
                <tr key={verification.id} className="hover:bg-gray-50">
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
                            onClick={() => {
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
                            onClick={() => handleDelete(verification.id)}
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
      {showCreateModal && selectedCompany && (
        <CreateVerificationModal
          companyId={selectedCompany.id}
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

// Common verification templates
interface VerificationTemplate {
  name: string
  description: string
  lines: Array<{
    accountNumber: number
    debit: boolean // true for debit, false for credit
    description: string
  }>
}

const TEMPLATES: VerificationTemplate[] = [
  {
    name: 'Inköp med 25% moms',
    description: 'Inköp av varor/tjänster med 25% moms',
    lines: [
      { accountNumber: 4000, debit: true, description: 'Inköp varor' },
      { accountNumber: 2640, debit: true, description: 'Ingående moms 25%' },
      { accountNumber: 2440, debit: false, description: 'Leverantörsskuld' },
    ],
  },
  {
    name: 'Försäljning med 25% moms',
    description: 'Försäljning av varor/tjänster med 25% moms',
    lines: [
      { accountNumber: 1510, debit: true, description: 'Kundfordran' },
      { accountNumber: 3001, debit: false, description: 'Försäljning 25% moms' },
      { accountNumber: 2611, debit: false, description: 'Utgående moms 25%' },
    ],
  },
  {
    name: 'Betalning till leverantör',
    description: 'Betala leverantörsfaktura från bank',
    lines: [
      { accountNumber: 2440, debit: true, description: 'Leverantörsskuld' },
      { accountNumber: 1930, debit: false, description: 'Betalning från bankkonto' },
    ],
  },
  {
    name: 'Betalning från kund',
    description: 'Kundfaktura betalad till bank',
    lines: [
      { accountNumber: 1930, debit: true, description: 'Inbetalning till bankkonto' },
      { accountNumber: 1510, debit: false, description: 'Kundfordran' },
    ],
  },
  {
    name: 'Lokalhyra',
    description: 'Betala hyra för lokaler',
    lines: [
      { accountNumber: 5010, debit: true, description: 'Lokalhyra' },
      { accountNumber: 1930, debit: false, description: 'Betalning från bankkonto' },
    ],
  },
  {
    name: 'Lön och avgifter',
    description: 'Löneutbetalning med arbetsgivaravgifter',
    lines: [
      { accountNumber: 7210, debit: true, description: 'Lön tjänstemän' },
      { accountNumber: 7510, debit: true, description: 'Arbetsgivaravgifter' },
      { accountNumber: 2710, debit: false, description: 'Personalskatt' },
      { accountNumber: 1930, debit: false, description: 'Utbetalning från bankkonto' },
    ],
  },
]

// Create/Edit Verification Modal Component
interface CreateVerificationModalProps {
  companyId: number
  accounts: Account[]
  verification: Verification | null
  onClose: () => void
  onSuccess: () => void
}

function CreateVerificationModal({
  companyId,
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

  // Helper to find account by account number
  const findAccountByNumber = (accountNumber: number): Account | undefined => {
    return accounts.find((acc) => acc.account_number === accountNumber)
  }

  // Apply template
  const applyTemplate = (template: VerificationTemplate, amount: number) => {
    setFormData({ ...formData, description: template.description })

    // Calculate amounts based on template structure
    const newLines = template.lines.map((line) => {
      const account = findAccountByNumber(line.accountNumber)
      let lineAmount = 0

      // Simple amount distribution
      if (template.name.includes('moms')) {
        // For VAT transactions
        if (line.accountNumber === 2640 || line.accountNumber === 2611) {
          // VAT is 20% of the amount (25% VAT means amount/(1+0.25) * 0.25)
          lineAmount = amount * 0.2
        } else if (line.accountNumber === 4000 || line.accountNumber === 3001) {
          // Net amount is 80% of the amount
          lineAmount = amount * 0.8
        } else {
          // Total amount (including VAT)
          lineAmount = amount
        }
      } else {
        // For non-VAT transactions, use the full amount
        lineAmount = amount
      }

      return {
        account_id: account?.id || 0,
        debit: line.debit ? lineAmount : 0,
        credit: line.debit ? 0 : lineAmount,
        description: line.description,
      }
    })

    setLines(newLines)
    setShowTemplates(false)
  }

  const addLine = () => {
    setLines([...lines, { account_id: 0, debit: 0, credit: 0, description: '' }])
  }

  const removeLine = (index: number) => {
    if (lines.length <= 2) return // Keep at least 2 lines
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: string, value: any) => {
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ett fel uppstod')
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
                <div className="mt-3 grid grid-cols-2 gap-3">
                  {TEMPLATES.map((template, idx) => (
                    <div key={idx} className="bg-white p-3 rounded border border-blue-200">
                      <h4 className="font-medium text-sm mb-1">{template.name}</h4>
                      <p className="text-xs text-gray-600 mb-2">{template.description}</p>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          placeholder="Belopp"
                          className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
                          id={`template-amount-${idx}`}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const amountInput = document.getElementById(
                              `template-amount-${idx}`
                            ) as HTMLInputElement
                            const amount = Number(amountInput.value) || 1000
                            applyTemplate(template, amount)
                          }}
                          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                        >
                          Använd
                        </button>
                      </div>
                    </div>
                  ))}
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
                  {lines.map((line, index) => (
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
                  ))}
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
