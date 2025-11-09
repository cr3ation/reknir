import { useEffect, useState } from 'react'
import { invoiceApi, customerApi, supplierInvoiceApi, supplierApi } from '@/services/api'
import type { InvoiceListItem, SupplierInvoiceListItem } from '@/types'

export default function Invoices() {
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([])
  const [supplierInvoices, setSupplierInvoices] = useState<SupplierInvoiceListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [companyId] = useState(1) // Single company mode for MVP

  useEffect(() => {
    loadInvoices()
  }, [])

  const loadInvoices = async () => {
    try {
      const [outgoingRes, incomingRes] = await Promise.all([
        invoiceApi.list(companyId),
        supplierInvoiceApi.list(companyId),
      ])
      setInvoices(outgoingRes.data)
      setSupplierInvoices(incomingRes.data)
    } catch (error) {
      console.error('Failed to load invoices:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      draft: 'bg-gray-200 text-gray-800',
      sent: 'bg-blue-200 text-blue-800',
      paid: 'bg-green-200 text-green-800',
      partial: 'bg-yellow-200 text-yellow-800',
      overdue: 'bg-red-200 text-red-800',
      cancelled: 'bg-gray-400 text-gray-900',
    }
    return (
      <span className={`px-2 py-1 text-xs rounded ${colors[status as keyof typeof colors] || 'bg-gray-200'}`}>
        {status.toUpperCase()}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar fakturor...</p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Fakturor</h1>

      {/* Outgoing Invoices */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">Kundfakturor (Utgående)</h2>
          <button className="btn btn-primary">+ Ny faktura</button>
        </div>

        {invoices.length === 0 ? (
          <div className="card">
            <p className="text-gray-600">Inga kundfakturor ännu. Skapa din första faktura!</p>
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fakturanr
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Kund
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Belopp
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Betalt
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">
                      {invoice.invoice_series}{invoice.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm">{invoice.invoice_date}</td>
                    <td className="px-4 py-3 text-sm">{invoice.customer_name}</td>
                    <td className="px-4 py-3 text-sm">{getStatusBadge(invoice.status)}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.total_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.paid_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Supplier Invoices */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">Leverantörsfakturor (Inkommande)</h2>
          <button className="btn btn-primary">+ Registrera faktura</button>
        </div>

        {supplierInvoices.length === 0 ? (
          <div className="card">
            <p className="text-gray-600">Inga leverantörsfakturor ännu.</p>
          </div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fakturanr
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Leverantör
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Belopp
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Betalt
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {supplierInvoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium">
                      {invoice.supplier_invoice_number}
                    </td>
                    <td className="px-4 py-3 text-sm">{invoice.invoice_date}</td>
                    <td className="px-4 py-3 text-sm">{invoice.supplier_name}</td>
                    <td className="px-4 py-3 text-sm">{getStatusBadge(invoice.status)}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.total_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      {invoice.paid_amount.toLocaleString('sv-SE', {
                        style: 'currency',
                        currency: 'SEK',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
