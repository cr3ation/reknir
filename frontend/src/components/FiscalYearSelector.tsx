import { useFiscalYear } from '@/contexts/FiscalYearContext'

export default function FiscalYearSelector() {
  const { fiscalYears, selectedFiscalYear, setSelectedFiscalYear, loading } = useFiscalYear()

  if (loading || fiscalYears.length === 0) {
    return null
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="fiscal-year-select" className="text-sm font-medium text-gray-700">
        Räkenskapsår:
      </label>
      <select
        id="fiscal-year-select"
        value={selectedFiscalYear?.id || ''}
        onChange={(e) => {
          const year = fiscalYears.find((fy) => fy.id === Number(e.target.value))
          setSelectedFiscalYear(year || null)
        }}
        className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {fiscalYears.map((fy) => (
          <option key={fy.id} value={fy.id}>
            {fy.label} {fy.is_current && '(Aktuellt)'}
          </option>
        ))}
      </select>
    </div>
  )
}
