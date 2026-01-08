import { useState, useCallback, useEffect, ReactNode, createElement } from 'react'
import { FileText, Download, ChevronLeft, ChevronRight, PanelRightClose, X } from 'lucide-react'
import { attachmentApi } from '@/services/api'
import { usePinnedModal, ModalType } from '@/contexts/LayoutSettingsContext'
import AttachmentPreviewPanel, { ImageViewer } from '@/components/AttachmentPreviewPanel'
import type { EntityAttachment } from '@/types'

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface UseAttachmentPreviewControllerOptions {
  modalType: ModalType
}

export interface UseAttachmentPreviewControllerResult {
  // Preview state
  selectedIndex: number
  selectedAttachment: EntityAttachment | null
  setSelectedIndex: (index: number) => void
  openPreview: (index: number) => void
  closePreview: () => void
  reset: () => void

  // Pin state (from usePinnedModal)
  isPinned: boolean
  togglePinned: () => void
  canPin: boolean

  // Preview data
  previewUrl: string | null
  previewLoading: boolean

  // Ready-to-render ReactNodes
  floatingPreview: ReactNode | null
  pinnedPreview: ReactNode | null
}

// ============================================================================
// Main Hook
// ============================================================================

export function useAttachmentPreviewController(
  attachments: EntityAttachment[],
  options: UseAttachmentPreviewControllerOptions
): UseAttachmentPreviewControllerResult {
  const { modalType } = options

  // Selection state
  const [selectedIndex, setSelectedIndexState] = useState<number | null>(null)
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)

  // Preview data
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewMinimized, setPreviewMinimized] = useState(false)

  // Pin state
  const { isPinned, togglePinned, unpinModal } = usePinnedModal(modalType)

  const canPin = attachments.length > 0
  const currentIndex = selectedIndex ?? 0
  const selectedAttachment = attachments[currentIndex] ?? null

  // Safe index setter with clamping
  const setSelectedIndex = useCallback((index: number) => {
    if (attachments.length === 0) {
      setSelectedIndexState(null)
    } else {
      setSelectedIndexState(Math.max(0, Math.min(index, attachments.length - 1)))
    }
  }, [attachments.length])

  // Open preview (when clicking attachment in list)
  const openPreview = useCallback((index: number) => {
    setSelectedIndex(index)
    setIsPreviewOpen(true)
    setPreviewMinimized(false)
  }, [setSelectedIndex])

  // Close preview
  const closePreview = useCallback(() => {
    setIsPreviewOpen(false)
    if (isPinned) {
      unpinModal()
    }
  }, [isPinned, unpinModal])

  // Reset function for modal closing
  const reset = useCallback(() => {
    setSelectedIndexState(null)
    setIsPreviewOpen(false)
    setPreviewMinimized(false)
    if (previewUrl) {
      window.URL.revokeObjectURL(previewUrl)
    }
    setPreviewUrl(null)
    unpinModal()
  }, [previewUrl, unpinModal])

  // Load preview data
  const loadPreview = useCallback(async (attachment: EntityAttachment) => {
    setPreviewLoading(true)
    try {
      const response = await attachmentApi.download(attachment.attachment_id)
      const blob = new Blob([response.data], { type: attachment.mime_type })
      // Revoke old URL before creating new one
      setPreviewUrl(prevUrl => {
        if (prevUrl) {
          window.URL.revokeObjectURL(prevUrl)
        }
        return window.URL.createObjectURL(blob)
      })
    } catch (error) {
      console.error('Failed to load preview:', error)
    } finally {
      setPreviewLoading(false)
    }
  }, [])

  // Load preview when attachment changes or when preview opens/pins
  useEffect(() => {
    const shouldLoad = (isPreviewOpen || isPinned) && selectedAttachment
    if (!shouldLoad) {
      return
    }
    loadPreview(selectedAttachment)
  }, [isPreviewOpen, isPinned, selectedAttachment?.attachment_id, loadPreview])

  // Auto-open preview when pinned if none is selected
  useEffect(() => {
    if (isPinned && !isPreviewOpen && attachments.length > 0) {
      setSelectedIndexState(0)
      setIsPreviewOpen(true)
    }
  }, [isPinned, isPreviewOpen, attachments.length])

  // Clamp selectedIndex when attachments change
  useEffect(() => {
    if (attachments.length === 0) {
      if (isPreviewOpen) {
        closePreview()
      }
      setSelectedIndexState(null)
    } else if (selectedIndex !== null && selectedIndex >= attachments.length) {
      setSelectedIndexState(attachments.length - 1)
    }
  }, [attachments.length, selectedIndex, isPreviewOpen, closePreview])

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        window.URL.revokeObjectURL(previewUrl)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Download handler
  const handleDownload = useCallback(async () => {
    if (!selectedAttachment) return

    try {
      const response = await attachmentApi.download(selectedAttachment.attachment_id)
      const blob = new Blob([response.data], { type: selectedAttachment.mime_type })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = selectedAttachment.original_filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download attachment:', error)
    }
  }, [selectedAttachment])

  // Navigate handler
  const handleNavigate = useCallback((index: number) => {
    setSelectedIndex(index)
  }, [setSelectedIndex])

  // Common props for preview panel
  const previewPanelProps = selectedAttachment ? {
    attachment: selectedAttachment,
    previewUrl,
    previewLoading,
    isMinimized: previewMinimized,
    onMinimize: () => setPreviewMinimized(prev => !prev),
    onClose: closePreview,
    onDownload: handleDownload,
    attachments,
    currentIndex,
    onNavigate: handleNavigate,
  } : null

  // Floating preview (for overlay, shown when open but NOT pinned)
  const floatingPreview = isPreviewOpen && !isPinned && previewPanelProps ? (
    <AttachmentPreviewPanel
      {...previewPanelProps}
      isPinned={false}
      onTogglePin={togglePinned}
    />
  ) : null

  // Pinned preview (for rightPanel in modal - simple content without DraggableModal wrapper)
  const pinnedPreview = isPinned && selectedAttachment ? (() => {
    const isImage = selectedAttachment.mime_type.startsWith('image/')
    const isPdf = selectedAttachment.mime_type === 'application/pdf'
    const totalAttachments = attachments.length
    const canGoPrev = currentIndex > 0
    const canGoNext = currentIndex < totalAttachments - 1

    return createElement('div', {
      className: 'h-full bg-white rounded-lg shadow-xl flex flex-col overflow-hidden'
    },
      // Header
      createElement('div', {
        className: 'px-4 py-3 border-b border-gray-200 bg-white flex justify-between items-center flex-shrink-0'
      },
        // Title with navigation
        createElement('div', { className: 'flex items-center gap-2 min-w-0 flex-1' },
          createElement(FileText, { className: 'w-4 h-4 text-gray-500 flex-shrink-0' }),
          createElement('span', {
            className: 'text-sm font-medium text-gray-900 truncate'
          }, selectedAttachment.original_filename),
          totalAttachments > 1 && createElement('div', {
            className: 'flex items-center gap-1 ml-2 flex-shrink-0'
          },
            createElement('button', {
              onClick: () => handleNavigate(currentIndex - 1),
              disabled: !canGoPrev,
              className: `p-1 rounded ${canGoPrev ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'}`,
              title: 'Föregående'
            }, createElement(ChevronLeft, { className: 'w-4 h-4' })),
            createElement('span', {
              className: 'text-xs text-gray-500 min-w-[3ch] text-center'
            }, `${currentIndex + 1}/${totalAttachments}`),
            createElement('button', {
              onClick: () => handleNavigate(currentIndex + 1),
              disabled: !canGoNext,
              className: `p-1 rounded ${canGoNext ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'}`,
              title: 'Nästa'
            }, createElement(ChevronRight, { className: 'w-4 h-4' }))
          )
        ),
        // Actions
        createElement('div', { className: 'flex items-center gap-1 ml-2' },
          createElement('button', {
            onClick: togglePinned,
            className: 'p-1.5 rounded transition-colors text-blue-600 bg-blue-50 hover:bg-blue-100',
            title: 'Avsluta delad vy'
          }, createElement(PanelRightClose, { className: 'w-4 h-4' })),
          createElement('button', {
            onClick: closePreview,
            className: 'p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors',
            title: 'Stäng'
          }, createElement(X, { className: 'w-4 h-4' }))
        )
      ),
      // Content
      createElement('div', {
        className: `flex-1 bg-gray-100 p-2 ${isImage ? 'overflow-hidden' : 'overflow-auto'}`
      },
        previewLoading
          ? createElement('div', { className: 'flex items-center justify-center h-full' },
              createElement('p', { className: 'text-gray-500' }, 'Laddar...'))
          : previewUrl
            ? (isImage
                ? createElement(ImageViewer, {
                    src: previewUrl,
                    alt: selectedAttachment.original_filename
                  })
                : isPdf
                  ? createElement('iframe', {
                      src: previewUrl,
                      title: selectedAttachment.original_filename,
                      className: 'w-full h-full bg-white rounded',
                      style: { minHeight: '100%' }
                    })
                  : createElement('div', { className: 'flex items-center justify-center h-full' },
                      createElement('p', { className: 'text-gray-500 text-center' }, 'Förhandsvisning stöds inte för denna filtyp')))
            : null
      ),
      // Footer
      createElement('div', {
        className: 'flex justify-end gap-3 px-4 py-3 border-t border-gray-200 bg-white flex-shrink-0'
      },
        createElement('button', {
          onClick: handleDownload,
          className: 'flex items-center gap-2 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-md transition-colors'
        },
          createElement(Download, { className: 'w-4 h-4' }),
          'Ladda ner'
        )
      )
    )
  })() : null

  return {
    selectedIndex: currentIndex,
    selectedAttachment,
    setSelectedIndex,
    openPreview,
    closePreview,
    reset,
    isPinned,
    togglePinned,
    canPin,
    previewUrl,
    previewLoading,
    floatingPreview,
    pinnedPreview,
  }
}
