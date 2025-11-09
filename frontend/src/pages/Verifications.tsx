import { useEffect, useState } from 'react'
import { Plus, Edit, Trash2, Lock, CheckCircle, AlertCircle } from 'lucide-react'
import { verificationApi, accountApi } from '@/services/api'
import type { VerificationListItem, Account, Verification } from '@/types'

export default function Verifications() {
  const [verifications, setVerifications] = useState<VerificationListItem[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [companyId] = useState(1) // Single company mode for MVP
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingVerification, setEditingVerification] = useState<Verification | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [verificationsRes, accountsRes] = await Promise.all([
        verificationApi.list(companyId),
        accountApi.list(companyId),
      ])
      setVerifications(verificationsRes.data)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load verifications:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Är du säker på att du vill radera denna verifikation?')) return

    try {
      await verificationApi.delete(id)
      await loadData()
    } catch (error) {
      console.error('Failed to delete verification:', error)
      alert('Kunde inte radera verifikationen')
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
      {showCreateModal && (
        <CreateVerificationModal
          companyId={companyId}
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
          description: line.description || null,
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
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full my-8">
        <div className="px-6 py-4 border-b border-gray-200">
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

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
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
