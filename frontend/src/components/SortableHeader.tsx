import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import type { SortConfig } from '@/hooks/useSortableTable'

interface SortableHeaderProps {
  label: string
  sortKey: string
  sortConfig: SortConfig | null
  onSort: (key: string) => void
  className?: string
  align?: 'left' | 'center' | 'right'
}

/**
 * Sortable table header cell component
 *
 * @example
 * <SortableHeader
 *   label="Datum"
 *   sortKey="invoice_date"
 *   sortConfig={sortConfig}
 *   onSort={requestSort}
 * />
 */
export default function SortableHeader({
  label,
  sortKey,
  sortConfig,
  onSort,
  className = '',
  align = 'left',
}: SortableHeaderProps) {
  const isActive = sortConfig?.key === sortKey
  const direction = isActive ? sortConfig.direction : null

  const alignClass = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }[align]

  const justifyClass = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
  }[align]

  return (
    <th
      className={`px-4 py-3 text-xs font-medium uppercase cursor-pointer select-none group transition-colors hover:bg-gray-100 ${alignClass} ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <div className={`flex items-center gap-1 ${justifyClass}`}>
        <span className={isActive ? 'text-indigo-600' : 'text-gray-500 group-hover:text-gray-700'}>
          {label}
        </span>
        <span className="w-4 h-4 flex items-center justify-center">
          {direction === 'asc' ? (
            <ChevronUp className="w-4 h-4 text-indigo-600" />
          ) : direction === 'desc' ? (
            <ChevronDown className="w-4 h-4 text-indigo-600" />
          ) : (
            <ChevronsUpDown className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          )}
        </span>
      </div>
    </th>
  )
}
