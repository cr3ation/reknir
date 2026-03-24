import { useState, useMemo } from 'react'

export type SortDirection = 'asc' | 'desc'

export interface SortConfig {
  key: string
  direction: SortDirection
}

/**
 * Get a nested value from an object using dot notation
 * e.g., getValue({ a: { b: 1 } }, 'a.b') returns 1
 */
function getValue<T>(obj: T, path: string): unknown {
  return path.split('.').reduce((acc: unknown, part) => {
    if (acc && typeof acc === 'object' && part in acc) {
      return (acc as Record<string, unknown>)[part]
    }
    return undefined
  }, obj)
}

/**
 * Compare two values for sorting
 */
function compareValues(a: unknown, b: unknown, direction: SortDirection): number {
  // Handle null/undefined
  if (a == null && b == null) return 0
  if (a == null) return direction === 'asc' ? 1 : -1
  if (b == null) return direction === 'asc' ? -1 : 1

  // Compare numbers
  if (typeof a === 'number' && typeof b === 'number') {
    return direction === 'asc' ? a - b : b - a
  }

  // Compare dates (strings in YYYY-MM-DD format)
  if (typeof a === 'string' && typeof b === 'string') {
    // Check if both are date strings
    const dateRegex = /^\d{4}-\d{2}-\d{2}/
    if (dateRegex.test(a) && dateRegex.test(b)) {
      const dateA = new Date(a).getTime()
      const dateB = new Date(b).getTime()
      return direction === 'asc' ? dateA - dateB : dateB - dateA
    }

    // Regular string comparison (Swedish locale)
    const comparison = a.localeCompare(b, 'sv-SE', { sensitivity: 'base' })
    return direction === 'asc' ? comparison : -comparison
  }

  // Fallback: convert to string and compare
  const strA = String(a)
  const strB = String(b)
  const comparison = strA.localeCompare(strB, 'sv-SE', { sensitivity: 'base' })
  return direction === 'asc' ? comparison : -comparison
}

export interface UseSortableTableResult<T> {
  sortedData: T[]
  sortConfig: SortConfig | null
  requestSort: (key: string) => void
  clearSort: () => void
}

/**
 * Hook for sorting table data
 *
 * @param data - Array of items to sort
 * @param defaultSort - Optional default sort configuration
 * @returns Object with sorted data, current sort config, and sort control functions
 *
 * @example
 * const { sortedData, sortConfig, requestSort } = useSortableTable(invoices, {
 *   key: 'invoice_date',
 *   direction: 'desc'
 * })
 */
export function useSortableTable<T>(
  data: T[],
  defaultSort?: SortConfig | null
): UseSortableTableResult<T> {
  const [sortConfig, setSortConfig] = useState<SortConfig | null>(defaultSort ?? null)

  const sortedData = useMemo(() => {
    if (!sortConfig) {
      return data
    }

    const sorted = [...data].sort((a, b) => {
      const aValue = getValue(a, sortConfig.key)
      const bValue = getValue(b, sortConfig.key)
      return compareValues(aValue, bValue, sortConfig.direction)
    })

    return sorted
  }, [data, sortConfig])

  const requestSort = (key: string) => {
    setSortConfig((current) => {
      // If clicking on a different column, start with ascending
      if (current?.key !== key) {
        return { key, direction: 'asc' }
      }

      // Same column: toggle asc -> desc -> null
      if (current.direction === 'asc') {
        return { key, direction: 'desc' }
      }

      // After desc, clear sorting
      return null
    })
  }

  const clearSort = () => {
    setSortConfig(null)
  }

  return {
    sortedData,
    sortConfig,
    requestSort,
    clearSort,
  }
}
