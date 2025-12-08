import { createContext, useContext, useState, ReactNode } from 'react'
import { fiscalYearApi } from '@/services/api'
import type { FiscalYear } from '@/types'
import { useCompany } from './CompanyContext'

interface FiscalYearContextType {
  fiscalYears: FiscalYear[]
  selectedFiscalYear: FiscalYear | null
  setSelectedFiscalYear: (fiscalYear: FiscalYear | null) => void
  loadFiscalYears: (companyId: number) => Promise<void>
  loading: boolean
}

const FiscalYearContext = createContext<FiscalYearContextType | undefined>(undefined)

export function FiscalYearProvider({ children }: { children: ReactNode }) {
  const { selectedCompany } = useCompany()
  const [fiscalYears, setFiscalYears] = useState<FiscalYear[]>([])
  const [selectedFiscalYear, setSelectedFiscalYear] = useState<FiscalYear | null>(null)
  const [loading, setLoading] = useState(false)

  const loadFiscalYears = async (companyId: number) => {
    try {
      setLoading(true)
      const response = await fiscalYearApi.list(companyId)
      const years = response.data
      setFiscalYears(years)

      // Auto-select current fiscal year or most recent one
      if (years.length > 0) {
        const current = years.find((fy) => fy.is_current)
        setSelectedFiscalYear(current || years[0])
      } else {
        setSelectedFiscalYear(null)
      }
    } catch (error) {
      console.error('Failed to load fiscal years:', error)
    } finally {
      setLoading(false)
    }
  }

  // Auto-load fiscal years when selected company changes
  useEffect(() => {
    if (selectedCompany) {
      loadFiscalYears(selectedCompany.id)
    } else {
      setFiscalYears([])
      setSelectedFiscalYear(null)
    }
  }, [selectedCompany])

  return (
    <FiscalYearContext.Provider
      value={{
        fiscalYears,
        selectedFiscalYear,
        setSelectedFiscalYear,
        loadFiscalYears,
        loading,
      }}
    >
      {children}
    </FiscalYearContext.Provider>
  )
}

export function useFiscalYear() {
  const context = useContext(FiscalYearContext)
  if (context === undefined) {
    throw new Error('useFiscalYear must be used within a FiscalYearProvider')
  }
  return context
}
