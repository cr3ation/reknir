import { useState, useRef, useCallback, useEffect } from 'react'
import { FileText, Download, Maximize2, X, ChevronLeft, ChevronRight, PanelRight, PanelRightClose, ZoomIn, ZoomOut } from 'lucide-react'
import DraggableModal from './DraggableModal'
import type { EntityAttachment } from '@/types'
import { ModalType } from '@/contexts/LayoutSettingsContext'

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface AttachmentPreviewPanelProps {
  attachment: EntityAttachment
  previewUrl: string | null
  previewLoading: boolean
  isMinimized: boolean
  onMinimize: () => void
  onClose: () => void
  onDownload: () => void
  // Multi-attachment navigation (optional)
  attachments?: EntityAttachment[]
  currentIndex?: number
  onNavigate?: (index: number) => void
  // Pinned mode (optional)
  isPinned?: boolean
  // Toggle pin callback (optional)
  onTogglePin?: () => void
}

// Default preview panel size (vertical/portrait format for PDFs and receipts)
const DEFAULT_PREVIEW_WIDTH = 420
const DEFAULT_PREVIEW_HEIGHT = 620

// Zoom constraints
const MIN_ZOOM = 0.5
const MAX_ZOOM = 5
const ZOOM_STEP = 0.25

// ============================================================================
// ImageViewer Component (with zoom and pan)
// ============================================================================

interface ImageViewerProps {
  src: string
  alt: string
}

export function ImageViewer({ src, alt }: ImageViewerProps) {
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartRef = useRef<{ x: number; y: number; posX: number; posY: number } | null>(null)

  // Reset zoom and position when image changes
  useEffect(() => {
    setZoom(1)
    setPosition({ x: 0, y: 0 })
  }, [src])

  // Zoom in
  const handleZoomIn = useCallback(() => {
    setZoom(prev => Math.min(prev + ZOOM_STEP, MAX_ZOOM))
  }, [])

  // Zoom out
  const handleZoomOut = useCallback(() => {
    setZoom(prev => {
      const newZoom = Math.max(prev - ZOOM_STEP, MIN_ZOOM)
      // Reset position if zooming back to 1 or less
      if (newZoom <= 1) {
        setPosition({ x: 0, y: 0 })
      }
      return newZoom
    })
  }, [])

  // Handle mouse wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
    setZoom(prev => {
      const newZoom = Math.max(MIN_ZOOM, Math.min(prev + delta, MAX_ZOOM))
      // Reset position if zooming back to 1 or less
      if (newZoom <= 1) {
        setPosition({ x: 0, y: 0 })
      }
      return newZoom
    })
  }, [])

  // Handle double-click to toggle between fit and 100%
  const handleDoubleClick = useCallback(() => {
    if (zoom === 1) {
      setZoom(2)
    } else {
      setZoom(1)
      setPosition({ x: 0, y: 0 })
    }
  }, [zoom])

  // Start dragging
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (zoom <= 1) return // No panning when not zoomed
    e.preventDefault()
    setIsDragging(true)
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: position.x,
      posY: position.y,
    }
  }, [zoom, position])

  // Handle dragging
  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current) return
      const deltaX = e.clientX - dragStartRef.current.x
      const deltaY = e.clientY - dragStartRef.current.y
      setPosition({
        x: dragStartRef.current.posX + deltaX,
        y: dragStartRef.current.posY + deltaY,
      })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      dragStartRef.current = null
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  const canZoomIn = zoom < MAX_ZOOM
  const canZoomOut = zoom > MIN_ZOOM

  return (
    <div className="relative h-full flex flex-col">
      {/* Zoom controls */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-white/90 backdrop-blur-sm rounded-lg shadow-md border border-gray-200 p-1">
        <button
          onClick={handleZoomOut}
          disabled={!canZoomOut}
          className={`p-1.5 rounded transition-colors ${
            canZoomOut ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'
          }`}
          title="Zooma ut"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-xs text-gray-600 min-w-[3rem] text-center font-medium">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={handleZoomIn}
          disabled={!canZoomIn}
          className={`p-1.5 rounded transition-colors ${
            canZoomIn ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'
          }`}
          title="Zooma in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
      </div>

      {/* Image container */}
      <div
        className={`flex-1 overflow-hidden flex items-center justify-center ${
          zoom > 1 ? (isDragging ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-zoom-in'
        }`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onDoubleClick={handleDoubleClick}
      >
        <img
          src={src}
          alt={alt}
          className="max-w-full max-h-full bg-white shadow-sm rounded select-none"
          style={{
            transform: `scale(${zoom}) translate(${position.x / zoom}px, ${position.y / zoom}px)`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.1s ease-out',
          }}
          draggable={false}
        />
      </div>

      {/* Hint text */}
      {zoom === 1 && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-xs text-gray-500 bg-white/80 backdrop-blur-sm px-2 py-1 rounded">
          Scrolla för att zooma • Dubbelklicka för 200%
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Minimized Bar Component
// ============================================================================

function MinimizedBar({
  filename,
  onRestore,
  onClose,
}: {
  filename: string
  onRestore: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed bottom-4 right-4 z-[60] bg-white rounded-lg shadow-lg border border-gray-200 flex items-center gap-3 px-4 py-2 max-w-xs">
      <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
      <span className="text-sm text-gray-900 truncate flex-1" title={filename}>
        {filename}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={onRestore}
          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
          title="Återställ"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          onClick={onClose}
          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
          title="Stäng"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export default function AttachmentPreviewPanel({
  attachment,
  previewUrl,
  previewLoading,
  isMinimized,
  onMinimize,
  onClose,
  onDownload,
  attachments,
  currentIndex = 0,
  onNavigate,
  isPinned = false,
  onTogglePin,
}: AttachmentPreviewPanelProps) {
  const isImage = attachment.mime_type.startsWith('image/')
  const isPdf = attachment.mime_type === 'application/pdf'

  // Navigation helpers
  const totalAttachments = attachments?.length ?? 1
  const canNavigate = totalAttachments > 1 && onNavigate
  const canGoPrev = currentIndex > 0
  const canGoNext = currentIndex < totalAttachments - 1

  // Custom title with file icon, navigation, and pin button
  const titleContent = (
    <div className="flex items-center gap-2 min-w-0 flex-1">
      <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
      <span className="text-sm font-medium text-gray-900 truncate">
        {attachment.original_filename}
      </span>
      {canNavigate && (
        <div className="flex items-center gap-1 ml-2 flex-shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); onNavigate(currentIndex - 1) }}
            disabled={!canGoPrev}
            className={`p-1 rounded ${canGoPrev ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'}`}
            title="Föregående"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-gray-500 min-w-[3ch] text-center">
            {currentIndex + 1}/{totalAttachments}
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onNavigate(currentIndex + 1) }}
            disabled={!canGoNext}
            className={`p-1 rounded ${canGoNext ? 'text-gray-600 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'}`}
            title="Nästa"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
      {onTogglePin && (
        <button
          onClick={(e) => { e.stopPropagation(); onTogglePin() }}
          className={`p-1 rounded ml-auto flex-shrink-0 ${
            isPinned
              ? 'text-blue-600 bg-blue-50 hover:bg-blue-100'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
          title={isPinned ? 'Avsluta delad vy' : 'Docka till delad vy'}
        >
          {isPinned ? <PanelRightClose className="w-4 h-4" /> : <PanelRight className="w-4 h-4" />}
        </button>
      )}
    </div>
  )

  // Preview content
  const previewContent = (
    <div className="h-full bg-gray-100 -mx-6 -my-4 p-2">
      {previewLoading ? (
        <div className="flex items-center justify-center h-full">
          <p className="text-gray-500">Laddar...</p>
        </div>
      ) : previewUrl ? (
        <>
          {isImage && (
            <ImageViewer
              src={previewUrl}
              alt={attachment.original_filename}
            />
          )}
          {isPdf && (
            <iframe
              src={previewUrl}
              title={attachment.original_filename}
              className="w-full h-full bg-white rounded"
              style={{ minHeight: '100%' }}
            />
          )}
          {!isImage && !isPdf && (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-500 text-center">Förhandsvisning stöds inte för denna filtyp</p>
            </div>
          )}
        </>
      ) : null}
    </div>
  )

  // Footer with download button
  const footerContent = (
    <button
      onClick={onDownload}
      className="flex items-center gap-2 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
    >
      <Download className="w-4 h-4" />
      Ladda ner
    </button>
  )

  // Minimized bar content
  const minimizedContent = (
    <MinimizedBar
      filename={attachment.original_filename}
      onRestore={onMinimize} // Toggle back to non-minimized
      onClose={onClose}
    />
  )

  return (
    <DraggableModal
      modalType={ModalType.ATTACHMENT_PREVIEW}
      title={titleContent}
      defaultWidth={DEFAULT_PREVIEW_WIDTH}
      defaultHeight={DEFAULT_PREVIEW_HEIGHT}
      minWidth={300}
      minHeight={200}
      persistPosition={!isPinned}
      storageKey="reknir_preview_panel_state"
      allowMinimize={!isPinned}
      isMinimized={isMinimized}
      onMinimize={onMinimize}
      minimizedContent={minimizedContent}
      onClose={onClose}
      footer={footerContent}
      showBackdrop={false}
      isPinned={isPinned}
    >
      {previewContent}
    </DraggableModal>
  )
}
