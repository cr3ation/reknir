import { useState, useEffect } from 'react'
import { Building2, ChevronDown } from 'lucide-react'
import api from '../services/api'

interface Company {
  id: number
  name: string
  org_number: string
}

interface CompanySelectorProps {
  selectedCompanyId: number | null
  onCompanyChange: (company: Company) => void
}

export default function CompanySelector({ selectedCompanyId, onCompanyChange }: CompanySelectorProps) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    loadCompanies()
  }, [])

  const loadCompanies = async () => {
    try {
      const response = await api.get('/api/auth/me/companies')
      setCompanies(response.data)

      // Auto-select first company if none selected
      if (response.data.length > 0 && !selectedCompanyId) {
        onCompanyChange(response.data[0])
      }
    } catch (error) {
      console.error('Failed to load companies:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectedCompany = companies.find(c => c.id === selectedCompanyId)

  if (loading) {
    return (
      <div className="px-3 py-2 text-sm text-gray-500">
        Laddar företag...
      </div>
    )
  }

  if (companies.length === 0) {
    return (
      <div className="px-3 py-2 text-sm text-gray-500">
        Inga företag tillgängliga
      </div>
    )
  }

  // If only one company, show it without dropdown
  if (companies.length === 1) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg">
        <Building2 className="w-4 h-4 text-gray-500" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-gray-900 truncate">
            {companies[0].name}
          </div>
          <div className="text-xs text-gray-500">{companies[0].org_number}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Building2 className="w-4 h-4 text-gray-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 text-left">
          {selectedCompany ? (
            <>
              <div className="text-sm font-medium text-gray-900 truncate">
                {selectedCompany.name}
              </div>
              <div className="text-xs text-gray-500">{selectedCompany.org_number}</div>
            </>
          ) : (
            <div className="text-sm text-gray-500">Välj företag...</div>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-64 overflow-y-auto">
            {companies.map((company) => (
              <button
                key={company.id}
                onClick={() => {
                  onCompanyChange(company)
                  setIsOpen(false)
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 transition-colors ${
                  company.id === selectedCompanyId ? 'bg-blue-50' : ''
                }`}
              >
                <Building2 className={`w-4 h-4 flex-shrink-0 ${
                  company.id === selectedCompanyId ? 'text-blue-600' : 'text-gray-400'
                }`} />
                <div className="flex-1 min-w-0 text-left">
                  <div className={`text-sm font-medium truncate ${
                    company.id === selectedCompanyId ? 'text-blue-900' : 'text-gray-900'
                  }`}>
                    {company.name}
                  </div>
                  <div className="text-xs text-gray-500">{company.org_number}</div>
                </div>
                {company.id === selectedCompanyId && (
                  <div className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
