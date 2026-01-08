import { createContext, useContext, useState, ReactNode, useCallback } from 'react'

// Which side the attachment preview appears on in split-view mode
export type SplitViewAttachmentSide = 'left' | 'right'

export enum ModalType {
  VERIFICATION = 'verification',
  INVOICE = 'invoice',
  SUPPLIER_INVOICE = 'supplierInvoice',
  ATTACHMENT_PREVIEW = 'attachmentPreview',
}

export interface ModalMaximizedSettings {
  [ModalType.VERIFICATION]: boolean
  [ModalType.INVOICE]: boolean
  [ModalType.SUPPLIER_INVOICE]: boolean
  [ModalType.ATTACHMENT_PREVIEW]: boolean
}

export interface LayoutSettings {
  // Which side the attachment preview appears on in split-view
  splitViewAttachmentSide: SplitViewAttachmentSide
  modalMaximized: ModalMaximizedSettings
}

const DEFAULT_SETTINGS: LayoutSettings = {
  splitViewAttachmentSide: 'right',
  modalMaximized: {
    [ModalType.VERIFICATION]: false,
    [ModalType.INVOICE]: false,
    [ModalType.SUPPLIER_INVOICE]: false,
    [ModalType.ATTACHMENT_PREVIEW]: false,
  },
}

const STORAGE_KEY = 'reknir_layout_settings'

interface LayoutSettingsContextType {
  settings: LayoutSettings
  updateSettings: (updates: Partial<LayoutSettings>) => void
  resetSettings: () => void
  // Pinned modal state (not persisted - ephemeral)
  pinnedModal: ModalType | null
  setPinnedModal: (modal: ModalType | null) => void
}

const LayoutSettingsContext = createContext<LayoutSettingsContextType | undefined>(undefined)

function loadSettingsFromStorage(): LayoutSettings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return { ...DEFAULT_SETTINGS, ...parsed }
    }
  } catch (error) {
    console.error('Failed to load layout settings:', error)
  }
  return DEFAULT_SETTINGS
}

function saveSettingsToStorage(settings: LayoutSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch (error) {
    console.error('Failed to save layout settings:', error)
  }
}

export function LayoutSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<LayoutSettings>(loadSettingsFromStorage)
  const [pinnedModal, setPinnedModal] = useState<ModalType | null>(null)

  const updateSettings = useCallback((updates: Partial<LayoutSettings>) => {
    setSettings(prev => {
      const newSettings = { ...prev, ...updates }
      saveSettingsToStorage(newSettings)
      return newSettings
    })
  }, [])

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS)
    saveSettingsToStorage(DEFAULT_SETTINGS)
  }, [])

  return (
    <LayoutSettingsContext.Provider
      value={{
        settings,
        updateSettings,
        resetSettings,
        pinnedModal,
        setPinnedModal,
      }}
    >
      {children}
    </LayoutSettingsContext.Provider>
  )
}

export function useLayoutSettings() {
  const context = useContext(LayoutSettingsContext)
  if (context === undefined) {
    throw new Error('useLayoutSettings must be used within a LayoutSettingsProvider')
  }
  return context
}

export function useModalMaximized(modalType: ModalType) {
  const { settings, updateSettings } = useLayoutSettings()
  const isMaximized = settings.modalMaximized?.[modalType] ?? false

  const toggleMaximized = useCallback(() => {
    updateSettings({
      modalMaximized: {
        ...settings.modalMaximized,
        [modalType]: !isMaximized,
      },
    })
  }, [settings.modalMaximized, modalType, isMaximized, updateSettings])

  return { isMaximized, toggleMaximized }
}

export function usePinnedModal(modalType: ModalType) {
  const { pinnedModal, setPinnedModal } = useLayoutSettings()
  const isPinned = pinnedModal === modalType

  const togglePinned = useCallback(() => {
    setPinnedModal(isPinned ? null : modalType)
  }, [isPinned, modalType, setPinnedModal])

  const unpinModal = useCallback(() => {
    if (isPinned) {
      setPinnedModal(null)
    }
  }, [isPinned, setPinnedModal])

  return { isPinned, togglePinned, unpinModal }
}
