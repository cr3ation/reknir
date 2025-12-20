import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { companyApi } from '@/services/api'
import type { Company } from '@/types'

interface CompanyContextType {
  selectedCompany: Company | null
  setSelectedCompany: (company: Company | null) => void
  companies: Company[]
  loadCompanies: () => Promise<void>
}

const CompanyContext = createContext<CompanyContextType | undefined>(undefined)

export function CompanyProvider({ children }: { children: ReactNode }) {
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])

  const loadCompanies = useCallback(async () => {
    try {
      const response = await companyApi.list()
      setCompanies(response.data)
      // Auto-select first company if none selected
      if (response.data.length > 0) {
        setSelectedCompany((prev) => prev ?? response.data[0])
      }
    } catch (error) {
      console.error('Failed to load companies:', error)
    }
  }, [])

  useEffect(() => {
    loadCompanies()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <CompanyContext.Provider
      value={{
        selectedCompany,
        setSelectedCompany,
        companies,
        loadCompanies,
      }}
    >
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const context = useContext(CompanyContext)
  if (context === undefined) {
    throw new Error('useCompany must be used within a CompanyProvider')
  }
  return context
}
