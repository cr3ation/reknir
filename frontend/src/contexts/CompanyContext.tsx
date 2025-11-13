import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { companyApi } from '@/services/api'
import type { Company } from '@/types'

interface CompanyContextType {
  companies: Company[]
  selectedCompany: Company | null
  setSelectedCompany: (company: Company | null) => void
  loadCompanies: () => Promise<void>
  loading: boolean
}

const CompanyContext = createContext<CompanyContextType | undefined>(undefined)

const STORAGE_KEY = 'reknir_selected_company_id'

export function CompanyProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [selectedCompany, setSelectedCompanyState] = useState<Company | null>(null)
  const [loading, setLoading] = useState(true)

  const loadCompanies = async () => {
    try {
      setLoading(true)
      const response = await companyApi.list()
      const companiesList = response.data
      setCompanies(companiesList)

      // Try to restore previously selected company from localStorage
      const savedCompanyId = localStorage.getItem(STORAGE_KEY)
      if (savedCompanyId && companiesList.length > 0) {
        const savedCompany = companiesList.find((c) => c.id === parseInt(savedCompanyId))
        if (savedCompany) {
          setSelectedCompanyState(savedCompany)
        } else {
          // If saved company not found, select first one
          setSelectedCompanyState(companiesList[0])
        }
      } else if (companiesList.length > 0) {
        // No saved company, select first one
        setSelectedCompanyState(companiesList[0])
      }
    } catch (error) {
      console.error('Failed to load companies:', error)
    } finally {
      setLoading(false)
    }
  }

  const setSelectedCompany = (company: Company | null) => {
    setSelectedCompanyState(company)
    if (company) {
      localStorage.setItem(STORAGE_KEY, company.id.toString())
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  useEffect(() => {
    loadCompanies()
  }, [])

  return (
    <CompanyContext.Provider
      value={{
        companies,
        selectedCompany,
        setSelectedCompany,
        loadCompanies,
        loading,
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
