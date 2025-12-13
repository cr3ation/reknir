interface MonthlyData {
  month: string
  revenue: number
  expenses: number
  profit: number
}

interface RevenueExpenseChartProps {
  data: MonthlyData[]
  onMonthClick?: (month: string) => void
}

export default function RevenueExpenseChart({ data, onMonthClick }: RevenueExpenseChartProps) {
  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Intäkter & Kostnader</h3>
        <p className="text-gray-500 text-center py-8">Ingen data tillgänglig</p>
      </div>
    )
  }

  // Calculate max value for scaling
  const maxValue = Math.max(
    ...data.map(d => Math.max(d.revenue, d.expenses))
  )
  const scale = 200 / maxValue // 200px max height

  // Format month label (e.g., "2024-01" -> "Jan '24")
  const formatMonth = (monthStr: string) => {
    const [year, month] = monthStr.split('-')
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
    return `${monthNames[parseInt(month) - 1]} '${year.slice(2)}`
  }

  // Format currency
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Intäkter & Kostnader</h3>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded"></div>
            <span className="text-gray-600">Intäkter</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded"></div>
            <span className="text-gray-600">Kostnader</span>
          </div>
        </div>
      </div>

      <div className="relative">
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-8 w-16 flex flex-col justify-between text-xs text-gray-500 text-right pr-2">
          <span>{formatCurrency(maxValue)}</span>
          <span>{formatCurrency(maxValue * 0.75)}</span>
          <span>{formatCurrency(maxValue * 0.5)}</span>
          <span>{formatCurrency(maxValue * 0.25)}</span>
          <span>0 kr</span>
        </div>

        {/* Chart area */}
        <div className="ml-16">
          <div className="flex items-end justify-between gap-2 h-[200px] border-b border-gray-200">
            {data.map((item, index) => {
              const revenueHeight = item.revenue * scale
              const expensesHeight = item.expenses * scale

              return (
                <div
                  key={index}
                  className="flex-1 flex flex-col items-center gap-1 group cursor-pointer"
                  onClick={() => onMonthClick?.(item.month)}
                >
                  <div className="relative w-full flex items-end justify-center gap-1 h-full">
                    {/* Revenue bar */}
                    <div
                      className="w-full bg-green-500 rounded-t hover:bg-green-600 transition-colors relative group/bar"
                      style={{ height: `${revenueHeight}px` }}
                    >
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover/bar:opacity-100 transition-opacity whitespace-nowrap">
                        {formatCurrency(item.revenue)}
                      </div>
                    </div>

                    {/* Expenses bar */}
                    <div
                      className="w-full bg-red-500 rounded-t hover:bg-red-600 transition-colors relative group/bar"
                      style={{ height: `${expensesHeight}px` }}
                    >
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover/bar:opacity-100 transition-opacity whitespace-nowrap">
                        {formatCurrency(item.expenses)}
                      </div>
                    </div>
                  </div>

                  {/* Month label */}
                  <span className="text-xs text-gray-600 mt-2 whitespace-nowrap">
                    {formatMonth(item.month)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
