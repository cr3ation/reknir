import { useState, useCallback, useEffect, useRef, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X, Maximize2, Minimize2, Minus, PanelRight, PanelRightClose } from 'lucide-react'
import { useModalMaximized, useLayoutSettings, type ModalType } from '@/contexts/LayoutSettingsContext'

// ============================================================================
// Types & Interfaces
// ============================================================================

interface Position {
  x: number
  y: number
}

interface Size {
  width: number
  height: number
}

export interface DraggableModalProps {
  // Identity
  modalType: ModalType

  // Configuration
  title: string | ReactNode
  defaultWidth?: number
  defaultHeight?: number
  minWidth?: number
  minHeight?: number
  maxWidthPercent?: number
  maxHeightPercent?: number

  // Persistence (optional - only AttachmentPreview uses this now)
  persistPosition?: boolean
  storageKey?: string

  // Minimize support (for AttachmentPreview)
  allowMinimize?: boolean
  isMinimized?: boolean
  onMinimize?: () => void
  minimizedContent?: ReactNode

  // Callbacks
  onClose: () => void

  // Content
  children: ReactNode
  footer?: ReactNode

  // Extra header actions (before close button)
  headerActions?: ReactNode

  // Show backdrop (default true)
  showBackdrop?: boolean

  // Pin/split-screen support
  isPinned?: boolean
  onTogglePinned?: () => void
  canPin?: boolean  // Whether pin button should be enabled (e.g., has attachments)
  pinnedSide?: 'left' | 'right'  // Which side when pinned (default 'left' for forms)

  // Right panel for split-view (optional - alternative to separate modal)
  rightPanel?: ReactNode
}

// ============================================================================
// Helper Functions
// ============================================================================

function loadPanelState(storageKey: string): { position: Position; size: Size } | null {
  try {
    const stored = sessionStorage.getItem(storageKey)
    if (stored) return JSON.parse(stored)
  } catch { /* ignore */ }
  return null
}

function savePanelState(storageKey: string, position: Position, size: Size): void {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify({ position, size }))
  } catch { /* ignore */ }
}

function isPositionVisible(pos: Position, size: Size): boolean {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const minVisible = 100
  return (
    pos.x > -size.width + minVisible &&
    pos.x < vw - minVisible &&
    pos.y > 0 &&
    pos.y < vh - minVisible
  )
}

// ============================================================================
// ResizeHandle Component
// ============================================================================

function ResizeHandle({
  direction,
  className,
  onResizeStart,
}: {
  direction: string
  className: string
  onResizeStart: (e: React.MouseEvent, direction: string) => void
}) {
  return (
    <div
      onMouseDown={(e) => onResizeStart(e, direction)}
      className={`absolute ${className} z-10`}
    />
  )
}

// ============================================================================
// Main Component
// ============================================================================

export default function DraggableModal({
  modalType,
  title,
  defaultWidth = 800,
  defaultHeight = 600,
  minWidth = 400,
  minHeight = 300,
  maxWidthPercent = 95,
  maxHeightPercent = 95,
  persistPosition = false,
  storageKey,
  allowMinimize = false,
  isMinimized = false,
  onMinimize,
  minimizedContent,
  onClose,
  children,
  footer,
  headerActions,
  showBackdrop = true,
  isPinned = false,
  onTogglePinned,
  canPin = false,
  pinnedSide = 'left',
  rightPanel,
}: DraggableModalProps) {
  const { isMaximized, toggleMaximized } = useModalMaximized(modalType)
  const { settings: layoutSettings } = useLayoutSettings()

  // Compute split-view mode (pinned with right panel)
  const isSplitView = isPinned && !!rightPanel
  // Determine if we should reverse the flex direction (attachment on left)
  const reverseFlexDirection = isSplitView && layoutSettings.splitViewAttachmentSide === 'left'

  // Position null means centered (default state)
  const [position, setPosition] = useState<Position | null>(null)
  const [size, setSize] = useState<Size>({ width: defaultWidth, height: defaultHeight })
  const panelInitialized = useRef(false)

  // Drag state
  const [isDragging, setIsDragging] = useState(false)
  const dragStartRef = useRef<{ x: number; y: number; posX: number; posY: number } | null>(null)

  // Resize state
  const [isResizing, setIsResizing] = useState(false)
  const resizeStartRef = useRef<{
    x: number
    y: number
    w: number
    h: number
    posX: number
    posY: number
    dir: string
  } | null>(null)

  // Calculate centered position
  const getCenteredPosition = useCallback((): Position => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    return {
      x: Math.max(0, (vw - size.width) / 2),
      y: Math.max(0, (vh - size.height) / 2),
    }
  }, [size.width, size.height])

  // Get effective position (centered if null)
  const getEffectivePosition = useCallback((): Position => {
    return position ?? getCenteredPosition()
  }, [position, getCenteredPosition])

  // Load position from storage on mount (if persistence enabled)
  useEffect(() => {
    if (!panelInitialized.current && persistPosition && storageKey) {
      const saved = loadPanelState(storageKey)
      if (saved && isPositionVisible(saved.position, saved.size)) {
        setPosition(saved.position)
        setSize(saved.size)
      }
      panelInitialized.current = true
    }
  }, [persistPosition, storageKey])

  // Save position to storage when drag/resize ends (if persistence enabled)
  useEffect(() => {
    if (!isDragging && !isResizing && panelInitialized.current && persistPosition && storageKey && position) {
      savePanelState(storageKey, position, size)
    }
  }, [isDragging, isResizing, position, size, persistPosition, storageKey])

  // Drag handlers
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    e.preventDefault()
    const effectivePos = getEffectivePosition()
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: effectivePos.x,
      posY: effectivePos.y,
    }
    setIsDragging(true)
  }, [getEffectivePosition])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current) return
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      const newX = Math.max(50 - size.width, Math.min(window.innerWidth - 50, dragStartRef.current.posX + dx))
      const newY = Math.max(0, Math.min(window.innerHeight - 50, dragStartRef.current.posY + dy))
      setPosition({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      dragStartRef.current = null
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
    }
  }, [isDragging, size.width])

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent, direction: string) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()
    const effectivePos = getEffectivePosition()
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      w: size.width,
      h: size.height,
      posX: effectivePos.x,
      posY: effectivePos.y,
      dir: direction,
    }
    setIsResizing(true)
  }, [size, getEffectivePosition])

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeStartRef.current) return
      const { x, y, w, h, posX, posY, dir } = resizeStartRef.current
      const dx = e.clientX - x
      const dy = e.clientY - y

      const maxW = window.innerWidth * (maxWidthPercent / 100)
      const maxH = window.innerHeight * (maxHeightPercent / 100)

      let newW = w
      let newH = h
      let newX = posX
      let newY = posY

      if (dir.includes('e')) {
        newW = Math.max(minWidth, Math.min(maxW, w + dx))
      }
      if (dir.includes('w')) {
        const proposedW = w - dx
        newW = Math.max(minWidth, Math.min(maxW, proposedW))
        newX = posX + (w - newW)
      }
      if (dir.includes('s')) {
        newH = Math.max(minHeight, Math.min(maxH, h + dy))
      }
      if (dir.includes('n')) {
        const proposedH = h - dy
        newH = Math.max(minHeight, Math.min(maxH, proposedH))
        newY = posY + (h - newH)
      }

      setSize({ width: newW, height: newH })
      setPosition({ x: newX, y: newY })
    }

    const handleMouseUp = () => {
      resizeStartRef.current = null
      setIsResizing(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.userSelect = ''
    }
  }, [isResizing, minWidth, minHeight, maxWidthPercent, maxHeightPercent])

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // Get pinned style (docked to left or right 50%)
  const getPinnedStyle = useCallback((): React.CSSProperties => {
    const margin = 8 // 8px margin around
    return {
      position: 'fixed',
      left: pinnedSide === 'left' ? margin : '50%',
      top: margin,
      width: `calc(50% - ${margin * 1.5}px)`,
      height: `calc(100% - ${margin * 2}px)`,
      transition: 'all 0.2s ease-out',
    }
  }, [pinnedSide])

  // Get modal panel style (handles all modes)
  const getModalPanelStyle = useCallback((): React.CSSProperties | undefined => {
    // Maximized mode (not in split-view) - CSS handles via fixed inset-2
    if (isMaximized && !isSplitView) return undefined
    // Split-view mode - CSS handles via w-1/2 h-full
    if (isSplitView) return undefined
    // Pinned mode (without right panel) - dock to side
    if (isPinned) return getPinnedStyle()
    // Floating mode - use position/size
    const effectivePos = getEffectivePosition()
    return {
      position: 'fixed',
      left: effectivePos.x,
      top: effectivePos.y,
      width: size.width,
      height: size.height,
      transition: isDragging || isResizing ? 'none' : 'box-shadow 0.2s',
    }
  }, [isMaximized, isSplitView, isPinned, getPinnedStyle, getEffectivePosition, size, isDragging, isResizing])

  // Render minimized bar (if minimized)
  if (allowMinimize && isMinimized && minimizedContent) {
    return createPortal(minimizedContent, document.body)
  }

  // Unified return - single JSX tree for all modes
  // Layout changes via CSS, children always in same position
  return createPortal(
    <div
      className={`fixed z-50 ${
        isSplitView || showBackdrop ? 'inset-0' : ''
      }`}
      style={!isSplitView && !showBackdrop && isMaximized ? { inset: 0 } : undefined}
    >
      {/* Backdrop */}
      {(showBackdrop || isSplitView) && (
        <div className="absolute inset-0 bg-black bg-opacity-50" />
      )}

      {/* Split-view container - layout changes via CSS */}
      <div
        className={isSplitView ? `absolute inset-2 flex gap-2 ${reverseFlexDirection ? 'flex-row-reverse' : ''}` : ''}
      >
        {/* Modal panel - ALWAYS same position in tree */}
        <div
          className={`bg-white rounded-lg shadow-xl flex flex-col overflow-hidden ${
            isMaximized && !isSplitView ? 'fixed inset-2' : ''
          } ${
            isSplitView ? 'w-1/2 h-full' : ''
          }`}
          style={getModalPanelStyle()}
        >
          {/* Draggable header */}
          <div
            className="px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center select-none flex-shrink-0"
            onMouseDown={isMaximized || isPinned ? undefined : handleDragStart}
            style={isMaximized || isPinned ? undefined : { cursor: isDragging ? 'grabbing' : 'grab' }}
          >
            <h2 className="text-2xl font-bold truncate flex-1">{title}</h2>
            <div className="flex items-center gap-2 ml-4">
              {/* Pin button (before other actions) */}
              {onTogglePinned && (
                <button
                  type="button"
                  onClick={onTogglePinned}
                  disabled={!canPin && !isPinned}
                  className={`p-1.5 rounded transition-colors ${
                    isPinned
                      ? 'text-blue-600 bg-blue-50 hover:bg-blue-100'
                      : canPin
                        ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                        : 'text-gray-300 cursor-not-allowed'
                  }`}
                  title={isPinned ? 'Avsluta delad vy' : canPin ? 'Visa med bilaga (delad vy)' : 'Lägg till bilaga för delad vy'}
                >
                  {isPinned ? <PanelRightClose className="w-5 h-5" /> : <PanelRight className="w-5 h-5" />}
                </button>
              )}
              {headerActions}
              {/* Minimize button - hide in split-view */}
              {allowMinimize && onMinimize && !isSplitView && (
                <button
                  type="button"
                  onClick={onMinimize}
                  className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                  title="Minimera"
                >
                  <Minus className="w-5 h-5" />
                </button>
              )}
              {/* Maximize button - hide in split-view */}
              {!isSplitView && (
                <button
                  type="button"
                  onClick={toggleMaximized}
                  className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                  title={isMaximized ? 'Återställ' : 'Maximera'}
                >
                  {isMaximized ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                title="Stäng"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Content area - children ALWAYS here, never remounted */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {children}
          </div>

          {/* Footer (if provided) */}
          {footer && (
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-white flex-shrink-0">
              {footer}
            </div>
          )}

          {/* Resize handles (only when not maximized or pinned) */}
          {!isMaximized && !isPinned && (
            <>
              <ResizeHandle direction="n" className="top-0 left-2 right-2 h-1 cursor-ns-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="s" className="bottom-0 left-2 right-2 h-1 cursor-ns-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="e" className="right-0 top-2 bottom-2 w-1 cursor-ew-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="w" className="left-0 top-2 bottom-2 w-1 cursor-ew-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="nw" className="top-0 left-0 w-3 h-3 cursor-nwse-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="ne" className="top-0 right-0 w-3 h-3 cursor-nesw-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="sw" className="bottom-0 left-0 w-3 h-3 cursor-nesw-resize" onResizeStart={handleResizeStart} />
              <ResizeHandle direction="se" className="bottom-0 right-0 w-3 h-3 cursor-nwse-resize" onResizeStart={handleResizeStart} />
            </>
          )}
        </div>

        {/* Right panel - only in split-view, but within same tree */}
        {isSplitView && (
          <div className="w-1/2 h-full">
            {rightPanel}
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}
