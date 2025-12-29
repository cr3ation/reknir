import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { FileText, Download, Trash2, Upload, Lock, X, FolderOpen, Maximize2, Minus } from 'lucide-react'
import type { EntityAttachment, Attachment } from '@/types'
import { EntityType, AttachmentRole } from '@/types'
import { attachmentApi, supplierInvoiceApi, expenseApi, verificationApi } from '@/services/api'
import { useDropZone } from '@/hooks/useDropZone'
import { useLayoutSettings, PREVIEW_SIZE_PRESETS, type PreviewPosition } from '@/contexts/LayoutSettingsContext'

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
}

interface Position { x: number; y: number }
interface Size { width: number; height: number }

// ============================================================================
// Helper Functions
// ============================================================================

const SESSION_STORAGE_KEY = 'reknir_preview_panel_state'

function getInitialPosition(previewPosition: PreviewPosition, width: number, height: number): Position {
  const padding = 20
  const vw = window.innerWidth
  const vh = window.innerHeight

  switch (previewPosition) {
    case 'right': return { x: vw - width - padding, y: padding + 60 }
    case 'left': return { x: padding, y: padding + 60 }
    case 'bottom-right': return { x: vw - width - padding, y: vh - height - padding }
    case 'bottom-left': return { x: padding, y: vh - height - padding }
    default: return { x: vw - width - padding, y: padding + 60 }
  }
}

function loadPanelState(): { position: Position; size: Size } | null {
  try {
    const stored = sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch { /* ignore */ }
  return null
}

function savePanelState(position: Position, size: Size): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ position, size }))
  } catch { /* ignore */ }
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
}: AttachmentManagerProps) {
  const { settings: layoutSettings } = useLayoutSettings()

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [previewAttachment, setPreviewAttachment] = useState<EntityAttachment | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  // Floating panel state
  const [previewMode, setPreviewMode] = useState<'floating' | 'modal'>('floating')
  const [isMinimized, setIsMinimized] = useState(false)
  const [panelPosition, setPanelPosition] = useState<Position>({ x: 0, y: 0 })
  const [panelSize, setPanelSize] = useState<Size>({ width: 420, height: 620 })
  const panelInitialized = useRef(false)

  // Drag state
  const [isDragging, setIsDragging] = useState(false)
  const dragStartRef = useRef<{ x: number; y: number; posX: number; posY: number } | null>(null)

  // Resize state
  const [isResizing, setIsResizing] = useState(false)
  const resizeStartRef = useRef<{ x: number; y: number; w: number; h: number; posX: number; posY: number; dir: string } | null>(null)

  // Select existing file modal state
  const [showSelectModal, setShowSelectModal] = useState(false)
  const [availableAttachments, setAvailableAttachments] = useState<Attachment[]>([])
  const [loadingAvailable, setLoadingAvailable] = useState(false)

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

  // Attachments to display in the UI.
  // - Normal mode: use `attachments` prop (already linked to the entity)
  // - Pending mode: convert `pendingAttachmentIds` to EntityAttachment format
  //   (these are selected but not yet linked - linking happens after entity creation)
  const visibleAttachments: EntityAttachment[] = pendingMode
    ? availableAttachments
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
    : attachments

  // Check if position is visible on screen
  const isPositionVisible = (pos: Position, size: Size): boolean => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    // At least 100px of the panel should be visible
    const minVisible = 100
    return (
      pos.x > -size.width + minVisible &&
      pos.x < vw - minVisible &&
      pos.y > 0 &&
      pos.y < vh - minVisible
    )
  }

  // Initialize panel position/size from session storage or settings
  useEffect(() => {
    if (!panelInitialized.current && previewAttachment) {
      const saved = loadPanelState()
      if (saved && isPositionVisible(saved.position, saved.size)) {
        setPanelPosition(saved.position)
        setPanelSize(saved.size)
      } else {
        // Reset to default if saved position is off-screen or doesn't exist
        const preset = PREVIEW_SIZE_PRESETS[layoutSettings.previewSize]
        setPanelSize({ width: preset.width, height: preset.height })
        setPanelPosition(getInitialPosition(layoutSettings.previewPosition, preset.width, preset.height))
        // Clear invalid saved state
        if (saved) {
          sessionStorage.removeItem(SESSION_STORAGE_KEY)
        }
      }
      panelInitialized.current = true
    }
  }, [previewAttachment, layoutSettings])

  // Drag handlers
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    e.preventDefault()
    dragStartRef.current = { x: e.clientX, y: e.clientY, posX: panelPosition.x, posY: panelPosition.y }
    setIsDragging(true)
  }, [panelPosition])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current) return
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      const newX = Math.max(50 - panelSize.width, Math.min(window.innerWidth - 50, dragStartRef.current.posX + dx))
      const newY = Math.max(0, Math.min(window.innerHeight - 50, dragStartRef.current.posY + dy))
      setPanelPosition({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      if (dragStartRef.current) {
        dragStartRef.current = null
        setIsDragging(false)
      }
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
    }
  }, [isDragging, panelPosition, panelSize])

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent, direction: string) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      w: panelSize.width,
      h: panelSize.height,
      posX: panelPosition.x,
      posY: panelPosition.y,
      dir: direction
    }
    setIsResizing(true)
  }, [panelSize, panelPosition])

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeStartRef.current) return
      const { x, y, w, h, posX, posY, dir } = resizeStartRef.current
      const dx = e.clientX - x
      const dy = e.clientY - y

      let newW = w, newH = h, newX = posX, newY = posY

      if (dir.includes('e')) {
        newW = Math.max(300, Math.min(window.innerWidth * 0.9, w + dx))
      }
      if (dir.includes('w')) {
        const proposedW = w - dx
        newW = Math.max(300, Math.min(window.innerWidth * 0.9, proposedW))
        // Adjust position based on actual width change
        newX = posX + (w - newW)
      }
      if (dir.includes('s')) {
        newH = Math.max(200, Math.min(window.innerHeight * 0.9, h + dy))
      }
      if (dir.includes('n')) {
        const proposedH = h - dy
        newH = Math.max(200, Math.min(window.innerHeight * 0.9, proposedH))
        // Adjust position based on actual height change
        newY = posY + (h - newH)
      }

      setPanelSize({ width: newW, height: newH })
      setPanelPosition({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      if (resizeStartRef.current) {
        resizeStartRef.current = null
        setIsResizing(false)
      }
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
    }
  }, [isResizing])

  // Save panel state when drag/resize ends
  useEffect(() => {
    if (!isDragging && !isResizing && panelInitialized.current) {
      savePanelState(panelPosition, panelSize)
    }
  }, [isDragging, isResizing, panelPosition, panelSize])

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
      setPreviewMode('floating')
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
    panelInitialized.current = false
  }

  useEffect(() => {
    return () => {
      if (previewUrl) window.URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && previewAttachment) closePreview()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [previewAttachment])

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
      // In pending mode, filter out already selected IDs; otherwise filter out already linked attachments
      if (pendingMode) {
        const selectedIds = new Set(pendingAttachmentIds)
        setAvailableAttachments(response.data.filter(a => !selectedIds.has(a.id)))
      } else {
        const linkedIds = new Set(attachments.map(a => a.attachment_id))
        setAvailableAttachments(response.data.filter(a => !linkedIds.has(a.id)))
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
        // Already selected, remove it
        onPendingSelectionChange?.(pendingAttachmentIds.filter(id => id !== attachment.id))
      } else {
        // Check max attachments
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

  // Render resize handle
  const ResizeHandle = ({ direction, className }: { direction: string; className: string }) => (
    <div
      onMouseDown={(e) => handleResizeStart(e, direction)}
      className={`absolute ${className} z-10`}
    />
  )

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
          {visibleAttachments.map((attachment) => (
            <div
              key={attachment.link_id}
              className={`flex items-center gap-3 p-3 ${pendingMode ? 'bg-indigo-50' : 'bg-gray-50'} rounded-lg ${
                isPreviewable(attachment.mime_type) ? 'cursor-pointer hover:bg-gray-100' : ''
              }`}
              onClick={() => isPreviewable(attachment.mime_type) && handlePreview(attachment)}
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

      {/* Floating Preview Panel */}
      {previewAttachment && previewMode === 'floating' && !isMinimized && createPortal(
        <div
          className="fixed z-[60] bg-white rounded-lg shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
          style={{
            left: panelPosition.x,
            top: panelPosition.y,
            width: panelSize.width,
            height: panelSize.height,
            transition: isDragging || isResizing ? 'none' : 'box-shadow 0.2s',
          }}
        >
          {/* Header - Draggable */}
          <div
            onMouseDown={handleDragStart}
            className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200 select-none"
            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
              <span className="text-sm font-medium text-gray-900 truncate">
                {previewAttachment.original_filename}
              </span>
            </div>
            <div className="flex items-center gap-1 ml-2">
              <button
                onClick={() => setIsMinimized(true)}
                className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded transition-colors"
                title="Minimera"
              >
                <Minus className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPreviewMode('modal')}
                className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded transition-colors"
                title="Maximera"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
              <button
                onClick={closePreview}
                className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded transition-colors"
                title="Stäng"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-auto bg-gray-100 p-2">
            {previewLoading ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-gray-500">Laddar...</p>
              </div>
            ) : previewUrl ? (
              <>
                {previewAttachment.mime_type.startsWith('image/') && (
                  <img
                    src={previewUrl}
                    alt={previewAttachment.original_filename}
                    className="max-w-full h-auto mx-auto bg-white shadow-sm rounded"
                  />
                )}
                {previewAttachment.mime_type === 'application/pdf' && (
                  <iframe
                    src={previewUrl}
                    title={previewAttachment.original_filename}
                    className="w-full h-full bg-white rounded"
                    style={{ minHeight: '100%' }}
                  />
                )}
                {!previewAttachment.mime_type.startsWith('image/') && previewAttachment.mime_type !== 'application/pdf' && (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-gray-500 text-center">Förhandsvisning stöds inte för denna filtyp</p>
                  </div>
                )}
              </>
            ) : null}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end px-4 py-2 bg-gray-50 border-t border-gray-200">
            <button
              onClick={() => handleDownload(previewAttachment)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
            >
              <Download className="w-4 h-4" />
              Ladda ner
            </button>
          </div>

          {/* Resize Handles */}
          <ResizeHandle direction="n" className="top-0 left-2 right-2 h-1 cursor-ns-resize" />
          <ResizeHandle direction="s" className="bottom-0 left-2 right-2 h-1 cursor-ns-resize" />
          <ResizeHandle direction="e" className="right-0 top-2 bottom-2 w-1 cursor-ew-resize" />
          <ResizeHandle direction="w" className="left-0 top-2 bottom-2 w-1 cursor-ew-resize" />
          <ResizeHandle direction="nw" className="top-0 left-0 w-3 h-3 cursor-nwse-resize" />
          <ResizeHandle direction="ne" className="top-0 right-0 w-3 h-3 cursor-nesw-resize" />
          <ResizeHandle direction="sw" className="bottom-0 left-0 w-3 h-3 cursor-nesw-resize" />
          <ResizeHandle direction="se" className="bottom-0 right-0 w-3 h-3 cursor-nwse-resize" />
        </div>,
        document.body
      )}

      {/* Minimized Preview Bar */}
      {previewAttachment && isMinimized && createPortal(
        <div className="fixed bottom-4 right-4 z-[60] bg-white rounded-lg shadow-lg border border-gray-200 flex items-center gap-3 px-4 py-2 max-w-xs">
          <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
          <span className="text-sm text-gray-900 truncate flex-1" title={previewAttachment.original_filename}>
            {previewAttachment.original_filename}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsMinimized(false)}
              className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
              title="Återställ"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
            <button
              onClick={closePreview}
              className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
              title="Stäng"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>,
        document.body
      )}

      {/* Full-screen Modal (maximized mode) */}
      {previewAttachment && previewMode === 'modal' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={closePreview}>
          <div
            className="relative bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold truncate pr-4">{previewAttachment.original_filename}</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPreviewMode('floating')}
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full"
                  title="Flytande panel"
                >
                  <Minus className="w-5 h-5" />
                </button>
                <button
                  onClick={closePreview}
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full"
                  title="Stäng"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-4 overflow-auto max-h-[calc(90vh-8rem)]">
              {previewLoading ? (
                <div className="flex items-center justify-center py-16">
                  <p className="text-gray-500">Laddar...</p>
                </div>
              ) : previewUrl ? (
                <>
                  {previewAttachment.mime_type.startsWith('image/') && (
                    <img src={previewUrl} alt={previewAttachment.original_filename} className="max-w-full h-auto mx-auto" />
                  )}
                  {previewAttachment.mime_type === 'application/pdf' && (
                    <iframe src={previewUrl} title={previewAttachment.original_filename} className="w-full h-[70vh]" />
                  )}
                  {!previewAttachment.mime_type.startsWith('image/') && previewAttachment.mime_type !== 'application/pdf' && (
                    <p className="text-gray-500 text-center py-8">Förhandsvisning stöds inte för denna filtyp</p>
                  )}
                </>
              ) : null}
            </div>

            <div className="flex items-center justify-end gap-2 p-4 border-t">
              <button
                onClick={() => handleDownload(previewAttachment)}
                className="flex items-center gap-2 px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-md"
              >
                <Download className="w-4 h-4" />
                Ladda ner
              </button>
              <button onClick={closePreview} className="px-4 py-2 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-md">
                Stäng
              </button>
            </div>
          </div>
        </div>
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
              ) : availableAttachments.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FolderOpen className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                  <p>{labels.selectExistingEmpty || 'Inga tillgängliga filer'}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {availableAttachments.map((attachment) => (
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
