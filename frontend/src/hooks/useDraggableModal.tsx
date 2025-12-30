import { useState, useCallback, useEffect, useRef } from 'react'

interface Position {
  x: number
  y: number
}

interface Size {
  width: number
  height: number
}

interface UseDraggableModalOptions {
  defaultWidth: number
  defaultHeight: number
  minWidth?: number
  minHeight?: number
  maxWidthPercent?: number
  maxHeightPercent?: number
}

interface UseDraggableModalReturn {
  // Position and size
  position: Position | null  // null = centered (default)
  size: Size
  // Drag state
  isDragging: boolean
  handleDragStart: (e: React.MouseEvent) => void
  // Resize state
  isResizing: boolean
  handleResizeStart: (e: React.MouseEvent, direction: string) => void
  // Reset to default
  resetPosition: () => void
  // Style helpers
  getModalStyle: () => React.CSSProperties
  getHeaderStyle: () => React.CSSProperties
}

export function useDraggableModal({
  defaultWidth,
  defaultHeight,
  minWidth = 400,
  minHeight = 300,
  maxWidthPercent = 95,
  maxHeightPercent = 95,
}: UseDraggableModalOptions): UseDraggableModalReturn {
  // Position null means centered (default state)
  const [position, setPosition] = useState<Position | null>(null)
  const [size, setSize] = useState<Size>({ width: defaultWidth, height: defaultHeight })

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

  // Reset to default centered position and size
  const resetPosition = useCallback(() => {
    setPosition(null)
    setSize({ width: defaultWidth, height: defaultHeight })
  }, [defaultWidth, defaultHeight])

  // Style helpers
  const getModalStyle = useCallback((): React.CSSProperties => {
    const effectivePos = getEffectivePosition()
    return {
      position: 'fixed',
      left: effectivePos.x,
      top: effectivePos.y,
      width: size.width,
      height: size.height,
      transition: isDragging || isResizing ? 'none' : 'box-shadow 0.2s',
    }
  }, [getEffectivePosition, size, isDragging, isResizing])

  const getHeaderStyle = useCallback((): React.CSSProperties => {
    return {
      cursor: isDragging ? 'grabbing' : 'grab',
    }
  }, [isDragging])

  return {
    position,
    size,
    isDragging,
    handleDragStart,
    isResizing,
    handleResizeStart,
    resetPosition,
    getModalStyle,
    getHeaderStyle,
  }
}

// Resize handle component helper
export function ResizeHandle({
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
