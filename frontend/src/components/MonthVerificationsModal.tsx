import { X, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'

interface Verification {
  id: number
  verification_number: number
  series: string
  transaction_date: string
  description: string
  amount: number
  type: 'revenue' | 'expense'
}

interface MonthVerificationsModalProps {
  month: string
  verifications: Verification[]
  onClose: () => void
}

export default function MonthVerificationsModal({
  month,
  verifications,
  onClose
}: MonthVerificationsModalProps) {
  // Format month label
  const formatMonth = (monthStr: string) => {
    const [year, monthNum] = monthStr.split('-')
    const monthNames = [
      'Januari', 'Februari', 'Mars', 'April', 'Maj', 'Juni',
      'Juli', 'Augusti', 'September', 'Oktober', 'November', 'December'
    ]
    return `${monthNames[parseInt(monthNum) - 1]} ${year}`
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: 'SEK',
      minimumFractionDigits: 2
    }).format(value)
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('sv-SE')
  }

  // Separate verifications by type
  const revenueVerifications = verifications.filter(v => v.type === 'revenue')
  const expenseVerifications = verifications.filter(v => v.type === 'expense')

  const totalRevenue = revenueVerifications.reduce((sum, v) => sum + v.amount, 0)
  const totalExpenses = expenseVerifications.reduce((sum, v) => sum + v.amount, 0)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Verifikationer för {formatMonth(month)}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {verifications.length} verifikationer
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Revenue Section */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-green-700">
                  Intäkter
                </h3>
                <span className="text-lg font-bold text-green-700">
                  {formatCurrency(totalRevenue)}
                </span>
              </div>

              {revenueVerifications.length === 0 ? (
                <p className="text-gray-500 text-sm">Inga intäkter denna månad</p>
              ) : (
                <div className="space-y-2">
                  {revenueVerifications.map((verification) => (
                    <Link
                      key={verification.id}
                      to={`/verifications/${verification.id}`}
                      className="block bg-green-50 hover:bg-green-100 rounded-lg p-3 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2 flex-1">
                          <FileText className="w-4 h-4 text-green-600 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {verification.series}{verification.verification_number}
                            </p>
                            <p className="text-xs text-gray-600 truncate">
                              {verification.description}
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatDate(verification.transaction_date)}
                            </p>
                          </div>
                        </div>
                        <span className="text-sm font-semibold text-green-700 ml-2">
                          {formatCurrency(verification.amount)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Expenses Section */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-red-700">
                  Rörelsekostnader
                </h3>
                <span className="text-lg font-bold text-red-700">
                  {formatCurrency(totalExpenses)}
                </span>
              </div>

              {expenseVerifications.length === 0 ? (
                <p className="text-gray-500 text-sm">Inga kostnader denna månad</p>
              ) : (
                <div className="space-y-2">
                  {expenseVerifications.map((verification) => (
                    <Link
                      key={verification.id}
                      to={`/verifications/${verification.id}`}
                      className="block bg-red-50 hover:bg-red-100 rounded-lg p-3 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2 flex-1">
                          <FileText className="w-4 h-4 text-red-600 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {verification.series}{verification.verification_number}
                            </p>
                            <p className="text-xs text-gray-600 truncate">
                              {verification.description}
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatDate(verification.transaction_date)}
                            </p>
                          </div>
                        </div>
                        <span className="text-sm font-semibold text-red-700 ml-2">
                          {formatCurrency(verification.amount)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="mt-6 pt-6 border-t">
            <div className="flex items-center justify-between text-lg font-bold">
              <span className="text-gray-700">Rörelseresultat:</span>
              <span className={totalRevenue - totalExpenses >= 0 ? 'text-green-700' : 'text-red-700'}>
                {formatCurrency(totalRevenue - totalExpenses)}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Stäng
          </button>
        </div>
      </div>
    </div>
  )
}
