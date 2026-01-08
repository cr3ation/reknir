import { useState, useCallback, useRef } from 'react'

export interface UseDropZoneOptions {
  onFilesDropped: (files: File[]) => void
  acceptedFileTypes?: string  // e.g. ".pdf,.jpg,.jpeg,.png,.gif"
  maxFileSizeMB?: number
  disabled?: boolean
  onError?: (message: string) => void
}

export interface UseDropZoneReturn {
  isDraggedOver: boolean
  dropZoneProps: {
    onDragEnter: (e: React.DragEvent) => void
    onDragLeave: (e: React.DragEvent) => void
    onDragOver: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
  }
}

export function useDropZone({
  onFilesDropped,
  acceptedFileTypes = '.pdf,.jpg,.jpeg,.png,.gif',
  maxFileSizeMB = 30,
  disabled = false,
  onError,
}: UseDropZoneOptions): UseDropZoneReturn {
  const [isDraggedOver, setIsDraggedOver] = useState(false)
  const dragCounter = useRef(0)

  // Parse accepted file types into extensions and mime types
  const acceptedExtensions = acceptedFileTypes
    .split(',')
    .map(ext => ext.trim().toLowerCase())
    .filter(ext => ext.startsWith('.'))

  const isFileTypeAccepted = useCallback((file: File): boolean => {
    const fileName = file.name.toLowerCase()
    return acceptedExtensions.some(ext => fileName.endsWith(ext))
  }, [acceptedExtensions])

  const validateFile = useCallback((file: File): { valid: boolean; error?: string } => {
    // Check file type
    if (!isFileTypeAccepted(file)) {
      return {
        valid: false,
        error: `Ogiltig filtyp: ${file.name}. Godkända format: ${acceptedExtensions.join(', ')}`
      }
    }

    // Check file size
    const maxSizeBytes = maxFileSizeMB * 1024 * 1024
    if (file.size > maxSizeBytes) {
      return {
        valid: false,
        error: `Filen "${file.name}" är för stor. Max ${maxFileSizeMB} MB.`
      }
    }

    return { valid: true }
  }, [isFileTypeAccepted, maxFileSizeMB, acceptedExtensions])

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current++

    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDraggedOver(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current--

    if (dragCounter.current === 0) {
      setIsDraggedOver(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = disabled ? 'none' : 'copy'
  }, [disabled])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggedOver(false)
    dragCounter.current = 0

    if (disabled) {
      return
    }

    const droppedFiles = Array.from(e.dataTransfer.files)

    if (droppedFiles.length === 0) {
      return
    }

    // Validate all files
    const validFiles: File[] = []
    const errors: string[] = []

    for (const file of droppedFiles) {
      const validation = validateFile(file)
      if (validation.valid) {
        validFiles.push(file)
      } else if (validation.error) {
        errors.push(validation.error)
      }
    }

    // Report errors
    if (errors.length > 0 && onError) {
      onError(errors.join('\n'))
    }

    // Process valid files
    if (validFiles.length > 0) {
      onFilesDropped(validFiles)
    }
  }, [disabled, validateFile, onFilesDropped, onError])

  return {
    isDraggedOver,
    dropZoneProps: {
      onDragEnter: handleDragEnter,
      onDragLeave: handleDragLeave,
      onDragOver: handleDragOver,
      onDrop: handleDrop,
    },
  }
}
