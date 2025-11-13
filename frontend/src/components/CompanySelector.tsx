import { useCompany } from '@/contexts/CompanyContext'
import { Building2 } from 'lucide-react'

export default function CompanySelector() {
  const { companies, selectedCompany, setSelectedCompany, loading } = useCompany()

  if (loading || companies.length === 0) {
    return null
  }

  // Don't show selector if there's only one company
  if (companies.length === 1) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-700 px-3 py-2 bg-gray-50 rounded-md">
        <Building2 className="w-4 h-4 text-gray-500" />
        <span className="font-medium">{selectedCompany?.name}</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <Building2 className="w-4 h-4 text-gray-500" />
      <select
        id="company-select"
        value={selectedCompany?.id || ''}
        onChange={(e) => {
          const company = companies.find((c) => c.id === Number(e.target.value))
          setSelectedCompany(company || null)
        }}
        className="flex-1 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
      >
        {companies.map((company) => (
          <option key={company.id} value={company.id}>
            {company.name}
          </option>
        ))}
      </select>
    </div>
  )
}
