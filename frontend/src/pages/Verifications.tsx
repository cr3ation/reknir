import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Edit, Trash2, Lock, CheckCircle } from 'lucide-react'
import { verificationApi, accountApi } from '@/services/api'
import type { VerificationListItem, Account, Verification, EntityAttachment } from '@/types'
import { useFiscalYear } from '@/contexts/FiscalYearContext'
import { useCompany } from '@/contexts/CompanyContext'
import { getErrorMessage } from '@/utils/errors'
import DraggableModal from '@/components/DraggableModal'
import { ModalType } from '@/contexts/LayoutSettingsContext'
import VerificationForm from '@/components/forms/VerificationForm'
import FiscalYearSelector from '@/components/FiscalYearSelector'
import { useAttachmentPreviewController } from '@/hooks/useAttachmentPreviewController'

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

  // Track attachments from form for preview controller
  const [formAttachments, setFormAttachments] = useState<EntityAttachment[]>([])

  // Pending attachment IDs (lifted from VerificationForm to survive modal layout changes)
  const [pendingAttachmentIds, setPendingAttachmentIds] = useState<number[]>([])

  // Attachment preview controller
  const {
    openPreview,
    reset: resetPreview,
    floatingPreview,
    pinnedPreview,
    canPin,
    isPinned,
    togglePinned,
  } = useAttachmentPreviewController(formAttachments, {
    modalType: ModalType.VERIFICATION,
  })

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
        <DraggableModal
          modalType={ModalType.VERIFICATION}
          title={editingVerification ? 'Redigera verifikation' : 'Ny verifikation'}
          defaultWidth={1024}
          defaultHeight={Math.min(window.innerHeight * 0.9, 800)}
          minWidth={600}
          minHeight={400}
          onClose={() => {
            resetPreview()
            setFormAttachments([])
            setPendingAttachmentIds([])
            setShowCreateModal(false)
            setEditingVerification(null)
          }}
          rightPanel={pinnedPreview}
          canPin={canPin}
          isPinned={isPinned}
          onTogglePinned={togglePinned}
        >
          <VerificationForm
            companyId={selectedCompany.id}
            fiscalYearId={selectedFiscalYear.id}
            accounts={accounts}
            verification={editingVerification}
            onSuccess={() => {
              resetPreview()
              setFormAttachments([])
              setPendingAttachmentIds([])
              setShowCreateModal(false)
              setEditingVerification(null)
              loadData()
            }}
            onCancel={() => {
              resetPreview()
              setFormAttachments([])
              setPendingAttachmentIds([])
              setShowCreateModal(false)
              setEditingVerification(null)
            }}
            onAttachmentsChange={setFormAttachments}
            onAttachmentClick={(_, index) => openPreview(index)}
            pendingAttachmentIds={pendingAttachmentIds}
            onPendingAttachmentIdsChange={setPendingAttachmentIds}
          />
        </DraggableModal>
      )}

      {/* Floating attachment preview (outside modal) */}
      {floatingPreview}
    </div>
  )
}
