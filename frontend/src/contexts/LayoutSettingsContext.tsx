import { createContext, useContext, useState, ReactNode, useCallback } from 'react'

export type PreviewPosition = 'right' | 'bottom-right' | 'left' | 'bottom-left'
export type PreviewSize = 'compact' | 'standard' | 'large'
export type ModalType = 'verification' | 'invoice' | 'supplierInvoice'

export interface ModalMaximizedSettings {
  verification: boolean
  invoice: boolean
  supplierInvoice: boolean
}

export interface LayoutSettings {
  previewPosition: PreviewPosition
  previewSize: PreviewSize
  modalMaximized: ModalMaximizedSettings
}

// Predefined size presets (vertical/portrait format for PDFs and receipts)
export const PREVIEW_SIZE_PRESETS: Record<PreviewSize, { width: number; height: number; label: string }> = {
  compact: { width: 340, height: 500, label: 'Kompakt' },
  standard: { width: 420, height: 620, label: 'Standard' },
  large: { width: 520, height: 760, label: 'Stor' },
}

const DEFAULT_SETTINGS: LayoutSettings = {
  previewPosition: 'right',
  previewSize: 'standard',
  modalMaximized: {
    verification: false,
    invoice: false,
    supplierInvoice: false,
  },
}

const STORAGE_KEY = 'reknir_layout_settings'

interface LayoutSettingsContextType {
  settings: LayoutSettings
  updateSettings: (updates: Partial<LayoutSettings>) => void
  resetSettings: () => void
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
