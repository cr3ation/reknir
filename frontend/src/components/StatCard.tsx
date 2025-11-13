import { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple'
  trend?: {
    value: number
    label: string
  }
}

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'blue', trend }: StatCardProps) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    red: 'bg-red-100 text-red-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    purple: 'bg-purple-100 text-purple-600'
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mb-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500">{subtitle}</p>
          )}
          {trend && (
            <div className={`flex items-center gap-1 text-sm mt-2 ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              <span className="font-semibold">{trend.value > 0 ? '+' : ''}{trend.value}%</span>
              <span className="text-gray-500">{trend.label}</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}
