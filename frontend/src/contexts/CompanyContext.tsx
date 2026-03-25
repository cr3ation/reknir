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

      if (response.data.length > 0) {
        setSelectedCompany((prev) => {
          if (!prev) {
            // No company selected yet, select the first one
            return response.data[0]
          }
          // Company already selected, find it in fresh data
          const updated = response.data.find(c => c.id === prev.id)
          // If found, use fresh data; otherwise fall back to first company
          return updated ?? response.data[0]
        })
      } else {
        // No companies exist, clear selection
        setSelectedCompany(null)
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
