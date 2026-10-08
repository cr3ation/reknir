import { useEffect, useState } from 'react'
import { History } from 'lucide-react'
import { auditApi } from '@/services/api'
import type { AuditLogEntry } from '@/types'

interface Props {
  companyId: number
  tableName?: string
  recordId?: number
  limit?: number
  title?: string
}

const ACTION_LABEL: Record<string, string> = {
  insert: 'Skapad',
  update: 'Ändrad',
  delete: 'Borttagen',
  note: 'Händelse',
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '–'
  return String(v)
}

export default function AuditHistory({ companyId, tableName, recordId, limit = 50, title = 'Behandlingshistorik' }: Props) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    auditApi
      .list({ company_id: companyId, table_name: tableName, record_id: recordId, limit })
      .then((res) => {
        if (!cancelled) setEntries(res.data)
      })
      .catch(() => {
        if (!cancelled) setEntries([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [companyId, tableName, recordId, limit])

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <History className="w-5 h-5 text-gray-600" />
        <h2 className="text-xl font-bold">{title}</h2>
      </div>
      {loading ? (
        <p className="text-sm text-gray-500">Laddar...</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-gray-500">Inga registrerade händelser.</p>
      ) : (
        <ul className="divide-y divide-gray-100 text-sm">
          {entries.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex flex-wrap justify-between gap-x-4">
                <span className="font-medium text-gray-900">
                  {ACTION_LABEL[e.action] ?? e.action}: {e.summary.replace(/^(insert|update|delete|note) /, '')}
                </span>
                <span className="text-gray-500 whitespace-nowrap">
                  {new Date(e.created_at + (e.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('sv-SE')}
                  {e.user_email ? ` · ${e.user_email}` : ''}
                </span>
              </div>
              {e.changes && (
                <ul className="mt-1 ml-4 text-xs text-gray-600 list-disc">
                  {Object.entries(e.changes).map(([field, [before, after]]) => (
                    <li key={field}>
                      {field}: {formatValue(before)} → {formatValue(after)}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
