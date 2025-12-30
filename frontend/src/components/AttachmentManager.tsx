import { useState, useEffect, useMemo, useRef } from 'react'
import { FileText, Download, Trash2, Upload, Lock, X, FolderOpen } from 'lucide-react'
import type { EntityAttachment, Attachment } from '@/types'
import { EntityType, AttachmentRole } from '@/types'
import { attachmentApi, supplierInvoiceApi, expenseApi, verificationApi } from '@/services/api'
import { useDropZone } from '@/hooks/useDropZone'
import AttachmentPreviewPanel from './AttachmentPreviewPanel'

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface AttachmentManagerConfig {
  maxAttachments?: number       // undefined = unlimited
  allowUpload: boolean          // Can upload new attachments
  allowDelete: boolean          // Can delete existing attachments
  acceptedFileTypes?: string    // Default: ".pdf,.jpg,.jpeg,.png,.gif"
  maxFileSizeMB?: number        // Default: 30
}

export interface AttachmentManagerLabels {
  title: string                 // Section heading
  emptyState: string            // Message when no attachments
  uploadButton: string          // Button text for first upload
  addMoreButton?: string        // Button text for additional uploads
  deleteConfirm: (filename: string) => string  // Confirmation message
  uploadSuccess?: string        // Success message after upload
  uploadError?: string          // Error message on upload failure
  deleteError?: string          // Error message on delete failure
  downloadError?: string        // Error message on download failure
  dropZoneText?: string
  dropZoneLockedText?: string
  selectExistingButton?: string
  selectExistingTitle?: string
  selectExistingEmpty?: string
  replaceConfirm?: string
}

export interface AttachmentManagerProps {
  attachments: EntityAttachment[]
  config: AttachmentManagerConfig
  labels: AttachmentManagerLabels
  onUpload: (file: File) => Promise<void>
  onDelete: (attachment: EntityAttachment) => Promise<void>
  onDownload: (attachment: EntityAttachment) => Promise<void>
  companyId?: number
  entityType?: EntityType
  entityId?: number
  onAttachmentsChange?: () => void
  isLoading?: boolean
  // Pending mode props (for use before entity is created)
  pendingMode?: boolean
  pendingAttachmentIds?: number[]
  onPendingSelectionChange?: (ids: number[]) => void
  // Callback when attachment is clicked (for external preview handling)
  onAttachmentClick?: (attachment: EntityAttachment, index: number) => void
  // Disable internal preview (when using external preview controller)
  disableInternalPreview?: boolean
  // Callback when visible attachments change (for external preview controller)
  onVisibleAttachmentsChange?: (attachments: EntityAttachment[]) => void
}

// ============================================================================
// Main Component
// ============================================================================

export default function AttachmentManager({
  attachments,
  config,
  labels,
  onUpload,
  onDelete,
  onDownload,
  companyId,
  entityType,
  entityId,
  onAttachmentsChange,
  isLoading = false,
  pendingMode = false,
  pendingAttachmentIds = [],
  onPendingSelectionChange,
  onAttachmentClick,
  disableInternalPreview = false,
  onVisibleAttachmentsChange,
}: AttachmentManagerProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [previewAttachment, setPreviewAttachment] = useState<EntityAttachment | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)

  // Select existing file modal state
  const [showSelectModal, setShowSelectModal] = useState(false)
  const [availableAttachments, setAvailableAttachments] = useState<Attachment[]>([])
  const [modalAttachments, setModalAttachments] = useState<Attachment[]>([])  // Filtered list for modal
  const [loadingAvailable, setLoadingAvailable] = useState(false)

  // Track previous visible attachment ids to prevent unnecessary callback triggers
  const prevVisibleIdsRef = useRef<string>('')

  const {
    maxAttachments,
    allowUpload,
    allowDelete,
    acceptedFileTypes = '.pdf,.jpg,.jpeg,.png,.gif',
    maxFileSizeMB = 30,
  } = config

  const effectiveAttachmentCount = pendingMode ? pendingAttachmentIds.length : attachments.length
  const canUploadMore = allowUpload && (maxAttachments === undefined || effectiveAttachmentCount < maxAttachments)
  const isLocked = !allowUpload && !allowDelete

  // In pending mode, load available attachments on mount and compute selected ones
  useEffect(() => {
    if (pendingMode && companyId) {
      setLoadingAvailable(true)
      attachmentApi.list(companyId)
        .then(response => setAvailableAttachments(response.data))
        .catch(error => console.error('Failed to load attachments:', error))
        .finally(() => setLoadingAvailable(false))
    }
  }, [pendingMode, companyId])

  // Attachments to display in the UI (memoized to prevent infinite loops)
  const visibleAttachments: EntityAttachment[] = useMemo(() => {
    if (pendingMode) {
      return availableAttachments
        .filter(a => pendingAttachmentIds.includes(a.id))
        .map(a => ({
          link_id: a.id,
          attachment_id: a.id,
          original_filename: a.original_filename,
          mime_type: a.mime_type,
          size_bytes: a.size_bytes,
          role: AttachmentRole.ORIGINAL,
          sort_order: 0,
          created_at: a.created_at,
          status: a.status,
        }))
    }
    return attachments
  }, [pendingMode, availableAttachments, pendingAttachmentIds, attachments])

  // Notify parent when visible attachments change (content-based guard to prevent infinite loops)
  useEffect(() => {
    // Create stable signature from attachment ids
    const currentIds = visibleAttachments.map(a => a.attachment_id).join(',')

    // Only notify if content actually changed
    if (currentIds !== prevVisibleIdsRef.current) {
      prevVisibleIdsRef.current = currentIds
      onVisibleAttachmentsChange?.(visibleAttachments)
    }
  }, [visibleAttachments, onVisibleAttachmentsChange])

  // File handlers
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      if (file.size > maxFileSizeMB * 1024 * 1024) {
        alert(`Filen är för stor. Max ${maxFileSizeMB} MB.`)
        return
      }
      setSelectedFile(file)
    }
    event.target.value = ''
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    try {
      setUploading(true)
      await onUpload(selectedFile)
      setSelectedFile(null)

      // Reload available attachments in pending mode so the new upload appears
      if (pendingMode && companyId) {
        const response = await attachmentApi.list(companyId)
        setAvailableAttachments(response.data)
      }

      if (labels.uploadSuccess) alert(labels.uploadSuccess)
    } catch (error) {
      console.error('Failed to upload attachment:', error)
      alert(labels.uploadError || 'Kunde inte ladda upp bilagan')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (attachment: EntityAttachment) => {
    if (!confirm(labels.deleteConfirm(attachment.original_filename))) return
    try {
      await onDelete(attachment)
    } catch (error) {
      console.error('Failed to delete attachment:', error)
      alert(labels.deleteError || 'Kunde inte ta bort bilagan')
    }
  }

  const handleDownload = async (attachment: EntityAttachment) => {
    try {
      await onDownload(attachment)
    } catch (error) {
      console.error('Failed to download attachment:', error)
      alert(labels.downloadError || 'Kunde inte ladda ner bilagan')
    }
  }

  // Preview handlers
  const handlePreview = async (attachment: EntityAttachment) => {
    try {
      setPreviewLoading(true)
      setPreviewAttachment(attachment)
      setIsMinimized(false)
      const response = await attachmentApi.download(attachment.attachment_id)
      const blob = new Blob([response.data], { type: attachment.mime_type })
      const url = window.URL.createObjectURL(blob)
      setPreviewUrl(url)
    } catch (error) {
      console.error('Failed to load preview:', error)
      alert(labels.downloadError || 'Kunde inte ladda förhandsvisning')
      setPreviewAttachment(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const closePreview = () => {
    if (previewUrl) window.URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    setPreviewAttachment(null)
  }

  useEffect(() => {
    return () => {
      if (previewUrl) window.URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const isPreviewable = (mimeType: string) => mimeType.startsWith('image/') || mimeType === 'application/pdf'

  // Drag and drop handlers
  const handleFilesDropped = async (files: File[]) => {
    if (!allowUpload) return

    if (maxAttachments === 1 && attachments.length > 0) {
      const confirmMessage = labels.replaceConfirm || 'Det finns redan en bilaga. Vill du ersätta den?'
      if (!confirm(confirmMessage)) return
      try {
        await onDelete(attachments[0])
      } catch (error) {
        console.error('Failed to delete existing attachment:', error)
        alert(labels.deleteError || 'Kunde inte ta bort befintlig bilaga')
        return
      }
    }

    const remainingSlots = maxAttachments !== undefined ? maxAttachments - attachments.length : files.length
    const filesToUpload = files.slice(0, Math.max(0, remainingSlots))

    if (filesToUpload.length < files.length) {
      alert(`Endast ${filesToUpload.length} av ${files.length} filer kunde laddas upp (max ${maxAttachments} bilagor).`)
    }

    setUploading(true)
    try {
      for (const file of filesToUpload) await onUpload(file)

      // Reload available attachments in pending mode so the new uploads appear
      if (pendingMode && companyId) {
        const response = await attachmentApi.list(companyId)
        setAvailableAttachments(response.data)
      }
    } catch (error) {
      console.error('Failed to upload:', error)
      alert(labels.uploadError || 'Kunde inte ladda upp bilagan')
    } finally {
      setUploading(false)
    }
  }

  const { isDraggedOver, dropZoneProps } = useDropZone({
    onFilesDropped: handleFilesDropped,
    acceptedFileTypes,
    maxFileSizeMB,
    disabled: !allowUpload,
    onError: (message) => alert(message),
  })

  // Select existing file handlers
  const loadAvailableAttachments = async () => {
    if (!companyId) return
    setLoadingAvailable(true)
    try {
      const response = await attachmentApi.list(companyId)
      // Update full list for visibleAttachments computation
      setAvailableAttachments(response.data)
      // Compute filtered list for modal (excluding already selected)
      if (pendingMode) {
        const selectedIds = new Set(pendingAttachmentIds)
        setModalAttachments(response.data.filter(a => !selectedIds.has(a.id)))
      } else {
        const linkedIds = new Set(attachments.map(a => a.attachment_id))
        setModalAttachments(response.data.filter(a => !linkedIds.has(a.id)))
      }
    } catch (error) {
      console.error('Failed to load attachments:', error)
    } finally {
      setLoadingAvailable(false)
    }
  }

  const handleOpenSelectModal = () => {
    setShowSelectModal(true)
    loadAvailableAttachments()
  }

  const linkAttachmentToEntity = async (attachmentId: number): Promise<void> => {
    if (!entityType || !entityId) throw new Error('Entity type and ID required for linking')
    switch (entityType) {
      case EntityType.SUPPLIER_INVOICE:
        await supplierInvoiceApi.linkAttachment(entityId, attachmentId)
        break
      case EntityType.EXPENSE:
        await expenseApi.linkAttachment(entityId, attachmentId)
        break
      case EntityType.VERIFICATION:
        await verificationApi.linkAttachment(entityId, attachmentId)
        break
      default:
        throw new Error(`Unsupported entity type: ${entityType}`)
    }
  }

  const handleSelectExisting = async (attachment: Attachment) => {
    // In pending mode, just add to pendingAttachmentIds
    if (pendingMode) {
      if (pendingAttachmentIds.includes(attachment.id)) {
        onPendingSelectionChange?.(pendingAttachmentIds.filter(id => id !== attachment.id))
      } else {
        if (maxAttachments && pendingAttachmentIds.length >= maxAttachments) {
          alert(`Max ${maxAttachments} bilaga${maxAttachments > 1 ? 'or' : ''} tillåtna`)
          return
        }
        onPendingSelectionChange?.([...pendingAttachmentIds, attachment.id])
      }
      setShowSelectModal(false)
      return
    }

    if (!entityType || !entityId) return

    if (maxAttachments === 1 && attachments.length > 0) {
      const confirmMessage = labels.replaceConfirm || 'Det finns redan en bilaga. Vill du ersätta den?'
      if (!confirm(confirmMessage)) return
      try {
        await onDelete(attachments[0])
      } catch (error) {
        console.error('Failed to delete existing attachment:', error)
        alert(labels.deleteError || 'Kunde inte ta bort befintlig bilaga')
        return
      }
    }

    try {
      await linkAttachmentToEntity(attachment.id)
      setShowSelectModal(false)
      onAttachmentsChange?.()
    } catch (error) {
      console.error('Failed to link attachment:', error)
      alert(labels.uploadError || 'Kunde inte länka bilagan')
    }
  }

  const canSelectExisting = allowUpload && companyId !== undefined && (
    pendingMode || (entityType !== undefined && entityId !== undefined)
  )
  const formatFileSize = (bytes: number) => `${(bytes / 1024).toFixed(1)} KB`

  if (isLoading) {
    return (
      <div className="card">
        <h2 className="text-xl font-bold mb-4">{labels.title}</h2>
        <div className="text-center py-8 text-gray-500"><p>Laddar...</p></div>
      </div>
    )
  }

  return (
    <div
      className={`card relative transition-all ${
        isDraggedOver
          ? allowUpload
            ? 'ring-2 ring-blue-500 ring-offset-2 bg-blue-50/50'
            : 'ring-2 ring-red-300 ring-offset-2 bg-red-50/50'
          : ''
      }`}
      {...dropZoneProps}
    >
      {/* Drop zone overlay */}
      {isDraggedOver && (
        <div className={`absolute inset-0 flex items-center justify-center rounded-lg z-10 ${
          allowUpload
            ? 'bg-blue-50/90 border-2 border-dashed border-blue-500'
            : 'bg-red-50/90 border-2 border-dashed border-red-300'
        }`}>
          <div className="text-center">
            {allowUpload ? (
              <>
                <Upload className="w-12 h-12 mx-auto mb-2 text-blue-500" />
                <p className="text-blue-700 font-medium">{labels.dropZoneText || 'Släpp filer här för att ladda upp'}</p>
              </>
            ) : (
              <>
                <Lock className="w-12 h-12 mx-auto mb-2 text-red-400" />
                <p className="text-red-700 font-medium">{labels.dropZoneLockedText || 'Uppladdning ej tillåtet'}</p>
              </>
            )}
          </div>
        </div>
      )}

      <h2 className="text-xl font-bold mb-4">{labels.title}</h2>

      {/* Existing attachments list */}
      {visibleAttachments.length > 0 && (
        <div className="space-y-2 mb-4">
          {visibleAttachments.map((attachment, index) => (
            <div
              key={attachment.link_id}
              className={`flex items-center gap-3 p-3 ${pendingMode ? 'bg-indigo-50' : 'bg-gray-50'} rounded-lg ${
                isPreviewable(attachment.mime_type) ? 'cursor-pointer hover:bg-gray-100' : ''
              }`}
              onClick={() => {
                if (!isPreviewable(attachment.mime_type)) return
                // Use external handler if provided, otherwise internal preview
                if (onAttachmentClick) {
                  onAttachmentClick(attachment, index)
                } else if (!disableInternalPreview) {
                  handlePreview(attachment)
                }
              }}
            >
              <FileText className={`w-6 h-6 ${pendingMode ? 'text-indigo-600' : 'text-gray-400'}`} />
              <div className="flex-1">
                <p className="text-sm font-medium">{attachment.original_filename}</p>
                <p className="text-xs text-gray-500">{formatFileSize(attachment.size_bytes)}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDownload(attachment) }}
                className="p-2 text-blue-600 hover:text-blue-800"
                title="Ladda ner"
              >
                <Download className="w-4 h-4" />
              </button>
              {(allowDelete || pendingMode) && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (pendingMode) {
                      onPendingSelectionChange?.(pendingAttachmentIds.filter(id => id !== attachment.attachment_id))
                    } else {
                      handleDelete(attachment)
                    }
                  }}
                  className="p-2 text-red-600 hover:text-red-800"
                  title="Ta bort"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Selected file preview */}
      {selectedFile && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border-2 border-dashed border-blue-200">
            <FileText className="w-6 h-6 text-blue-600" />
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-900">{selectedFile.name}</p>
              <p className="text-xs text-blue-700">{formatFileSize(selectedFile.size)}</p>
            </div>
            <button onClick={() => setSelectedFile(null)} className="text-blue-600 hover:text-blue-800" title="Avbryt">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
          >
            {uploading ? 'Laddar upp...' : labels.uploadButton}
          </button>
        </div>
      )}

      {/* Empty state */}
      {visibleAttachments.length === 0 && !selectedFile && (
        <div className="text-center py-8 text-gray-500">
          <Upload className="w-12 h-12 mx-auto mb-2 text-gray-300" />
          <p className="mb-4">{labels.emptyState}</p>
        </div>
      )}

      {/* Upload buttons */}
      {canUploadMore && !selectedFile && (
        <div className="flex gap-2">
          <label className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer">
            <Upload className="w-4 h-4" />
            {visibleAttachments.length > 0 ? (labels.addMoreButton || labels.uploadButton) : labels.uploadButton}
            <input type="file" accept={acceptedFileTypes} onChange={handleFileSelect} className="hidden" />
          </label>
          {canSelectExisting && (
            <button
              onClick={handleOpenSelectModal}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
              title={labels.selectExistingButton || 'Välj befintlig fil'}
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Locked indicator */}
      {isLocked && visibleAttachments.length > 0 && (
        <div className="flex items-center justify-end gap-1 text-sm text-gray-400 mt-2">
          <Lock className="w-3 h-3" />
          <span>Låst</span>
        </div>
      )}

      {/* Help text */}
      {canUploadMore && (
        <p className="text-xs text-gray-500 mt-2">
          Godkända format: PDF, JPG, PNG, GIF (max {maxFileSizeMB}MB)
        </p>
      )}

      {/* Attachment Preview Panel (only when internal preview is enabled) */}
      {!disableInternalPreview && previewAttachment && (
        <AttachmentPreviewPanel
          attachment={previewAttachment}
          previewUrl={previewUrl}
          previewLoading={previewLoading}
          isMinimized={isMinimized}
          onMinimize={() => setIsMinimized(!isMinimized)}
          onClose={closePreview}
          onDownload={() => handleDownload(previewAttachment)}
        />
      )}

      {/* Select existing file modal */}
      {showSelectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={() => setShowSelectModal(false)}>
          <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">{labels.selectExistingTitle || 'Välj fil'}</h3>
              <button
                onClick={() => setShowSelectModal(false)}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full"
                title="Stäng"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 max-h-[60vh] overflow-auto">
              {loadingAvailable ? (
                <div className="flex items-center justify-center py-8">
                  <p className="text-gray-500">Laddar...</p>
                </div>
              ) : modalAttachments.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FolderOpen className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                  <p>{labels.selectExistingEmpty || 'Inga tillgängliga filer'}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {modalAttachments.map((attachment) => (
                    <button
                      key={attachment.id}
                      onClick={() => handleSelectExisting(attachment)}
                      className="w-full flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 text-left"
                    >
                      <FileText className="w-6 h-6 text-gray-400" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{attachment.original_filename}</p>
                        <p className="text-xs text-gray-500">{formatFileSize(attachment.size_bytes)}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 p-4 border-t">
              <button onClick={() => setShowSelectModal(false)} className="px-4 py-2 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-md">
                Avbryt
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
