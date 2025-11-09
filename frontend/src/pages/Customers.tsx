import { useEffect, useState } from 'react'
import { Plus, Edit2, Trash2, X, Save } from 'lucide-react'
import { customerApi, supplierApi, companyApi } from '@/services/api'
import type { Customer, Supplier } from '@/types'
import { getErrorMessage } from '@/utils/errors'

export default function Customers() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [companyId, setCompanyId] = useState<number | null>(null)
  const [showCreateCustomerModal, setShowCreateCustomerModal] = useState(false)
  const [showCreateSupplierModal, setShowCreateSupplierModal] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null)
  const [activeTab, setActiveTab] = useState<'customers' | 'suppliers'>('customers')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const companiesRes = await companyApi.list()
      if (companiesRes.data.length === 0) {
        setLoading(false)
        return
      }
      const company = companiesRes.data[0]
      setCompanyId(company.id)

      const [customersRes, suppliersRes] = await Promise.all([
        customerApi.list(company.id, false), // Load all customers (not just active)
        supplierApi.list(company.id, false), // Load all suppliers
      ])
      setCustomers(customersRes.data)
      setSuppliers(suppliersRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const deleteCustomer = async (id: number) => {
    if (!confirm('Är du säker på att du vill ta bort denna kund?')) return

    try {
      await customerApi.delete(id)
      await loadData()
    } catch (error) {
      console.error('Failed to delete customer:', error)
      alert('Kunde inte ta bort kunden')
    }
  }

  const deleteSupplier = async (id: number) => {
    if (!confirm('Är du säker på att du vill ta bort denna leverantör?')) return

    try {
      await supplierApi.delete(id)
      await loadData()
    } catch (error) {
      console.error('Failed to delete supplier:', error)
      alert('Kunde inte ta bort leverantören')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Laddar...</p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Kunder & Leverantörer</h1>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('customers')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'customers'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Kunder ({customers.length})
          </button>
          <button
            onClick={() => setActiveTab('suppliers')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'suppliers'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Leverantörer ({suppliers.length})
          </button>
        </nav>
      </div>

      {/* Customers Tab */}
      {activeTab === 'customers' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">Kunder</h2>
            <button
              onClick={() => setShowCreateCustomerModal(true)}
              className="btn btn-primary inline-flex items-center"
            >
              <Plus className="w-4 h-4 mr-2" />
              Ny kund
            </button>
          </div>

          {customers.length === 0 ? (
            <div className="card">
              <p className="text-gray-600">Inga kunder ännu. Skapa din första kund!</p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Namn
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Org.nr
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Kontaktperson
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      E-post
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Stad
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Betalvillkor
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Åtgärder
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {customers.map((customer) => (
                    <tr key={customer.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">{customer.name}</td>
                      <td className="px-4 py-3 text-sm">{customer.org_number || '-'}</td>
                      <td className="px-4 py-3 text-sm">{customer.contact_person || '-'}</td>
                      <td className="px-4 py-3 text-sm">{customer.email || '-'}</td>
                      <td className="px-4 py-3 text-sm">{customer.city || '-'}</td>
                      <td className="px-4 py-3 text-sm text-center">{customer.payment_terms_days} dagar</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-1 text-xs rounded ${customer.active ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-800'}`}>
                          {customer.active ? 'Aktiv' : 'Inaktiv'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => setEditingCustomer(customer)}
                            className="text-indigo-600 hover:text-indigo-800 p-1"
                            title="Redigera"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteCustomer(customer.id)}
                            className="text-red-600 hover:text-red-800 p-1"
                            title="Ta bort"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Suppliers Tab */}
      {activeTab === 'suppliers' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">Leverantörer</h2>
            <button
              onClick={() => setShowCreateSupplierModal(true)}
              className="btn btn-primary inline-flex items-center"
            >
              <Plus className="w-4 h-4 mr-2" />
              Ny leverantör
            </button>
          </div>

          {suppliers.length === 0 ? (
            <div className="card">
              <p className="text-gray-600">Inga leverantörer ännu. Skapa din första leverantör!</p>
            </div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Namn
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Org.nr
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Kontaktperson
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      E-post
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Stad
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Betalvillkor
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      Åtgärder
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {suppliers.map((supplier) => (
                    <tr key={supplier.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">{supplier.name}</td>
                      <td className="px-4 py-3 text-sm">{supplier.org_number || '-'}</td>
                      <td className="px-4 py-3 text-sm">{supplier.contact_person || '-'}</td>
                      <td className="px-4 py-3 text-sm">{supplier.email || '-'}</td>
                      <td className="px-4 py-3 text-sm">{supplier.city || '-'}</td>
                      <td className="px-4 py-3 text-sm text-center">{supplier.payment_terms_days} dagar</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-1 text-xs rounded ${supplier.active ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-800'}`}>
                          {supplier.active ? 'Aktiv' : 'Inaktiv'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => setEditingSupplier(supplier)}
                            className="text-indigo-600 hover:text-indigo-800 p-1"
                            title="Redigera"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteSupplier(supplier.id)}
                            className="text-red-600 hover:text-red-800 p-1"
                            title="Ta bort"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Create/Edit Customer Modal */}
      {(showCreateCustomerModal || editingCustomer) && companyId && (
        <CreateCustomerModal
          companyId={companyId}
          customer={editingCustomer}
          onClose={() => {
            setShowCreateCustomerModal(false)
            setEditingCustomer(null)
          }}
          onSuccess={() => {
            setShowCreateCustomerModal(false)
            setEditingCustomer(null)
            loadData()
          }}
        />
      )}

      {/* Create/Edit Supplier Modal */}
      {(showCreateSupplierModal || editingSupplier) && companyId && (
        <CreateSupplierModal
          companyId={companyId}
          supplier={editingSupplier}
          onClose={() => {
            setShowCreateSupplierModal(false)
            setEditingSupplier(null)
          }}
          onSuccess={() => {
            setShowCreateSupplierModal(false)
            setEditingSupplier(null)
            loadData()
          }}
        />
      )}
    </div>
  )
}

// Create/Edit Customer Modal
interface CreateCustomerModalProps {
  companyId: number
  customer?: Customer | null
  onClose: () => void
  onSuccess: () => void
}

function CreateCustomerModal({ companyId, customer, onClose, onSuccess }: CreateCustomerModalProps) {
  const [formData, setFormData] = useState({
    name: customer?.name || '',
    org_number: customer?.org_number || '',
    contact_person: customer?.contact_person || '',
    email: customer?.email || '',
    phone: customer?.phone || '',
    address: customer?.address || '',
    postal_code: customer?.postal_code || '',
    city: customer?.city || '',
    country: customer?.country || 'Sverige',
    payment_terms_days: customer?.payment_terms_days || 30,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!customer

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    try {
      // Convert empty strings to undefined for optional fields
      const payload: any = {
        name: formData.name,
        org_number: formData.org_number || undefined,
        contact_person: formData.contact_person || undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
        postal_code: formData.postal_code || undefined,
        city: formData.city || undefined,
        country: formData.country,
        payment_terms_days: formData.payment_terms_days,
      }

      if (isEditing) {
        await customerApi.update(customer!.id, payload)
      } else {
        payload.company_id = companyId
        await customerApi.create(payload)
      }
      onSuccess()
    } catch (err: any) {
      console.error(`Failed to ${isEditing ? 'update' : 'create'} customer:`, err)
      setError(getErrorMessage(err, `Kunde inte ${isEditing ? 'uppdatera' : 'skapa'} kund`))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold">{isEditing ? 'Redigera kund' : 'Ny kund'}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Namn *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Org.nummer
              </label>
              <input
                type="text"
                value={formData.org_number}
                onChange={(e) => setFormData({ ...formData, org_number: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="XXXXXX-XXXX"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Kontaktperson
              </label>
              <input
                type="text"
                value={formData.contact_person}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                E-post
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Telefon
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Adress
              </label>
              <input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Postnummer
              </label>
              <input
                type="text"
                value={formData.postal_code}
                onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="123 45"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stad
              </label>
              <input
                type="text"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Land
              </label>
              <input
                type="text"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Betalningsvillkor (dagar)
              </label>
              <input
                type="number"
                value={formData.payment_terms_days}
                onChange={(e) => setFormData({ ...formData, payment_terms_days: parseInt(e.target.value) || 30 })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                min="0"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Avbryt
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? (isEditing ? 'Uppdaterar...' : 'Skapar...') : (isEditing ? 'Uppdatera' : 'Skapa kund')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Create/Edit Supplier Modal
interface CreateSupplierModalProps {
  companyId: number
  supplier?: Supplier | null
  onClose: () => void
  onSuccess: () => void
}

function CreateSupplierModal({ companyId, supplier, onClose, onSuccess }: CreateSupplierModalProps) {
  const [formData, setFormData] = useState({
    name: supplier?.name || '',
    org_number: supplier?.org_number || '',
    contact_person: supplier?.contact_person || '',
    email: supplier?.email || '',
    phone: supplier?.phone || '',
    address: supplier?.address || '',
    postal_code: supplier?.postal_code || '',
    city: supplier?.city || '',
    country: supplier?.country || 'Sverige',
    payment_terms_days: supplier?.payment_terms_days || 30,
    bank_account: supplier?.bank_account || '',
    bank_name: supplier?.bank_name || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!supplier

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    try {
      // Convert empty strings to undefined for optional fields
      const payload: any = {
        name: formData.name,
        org_number: formData.org_number || undefined,
        contact_person: formData.contact_person || undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
        postal_code: formData.postal_code || undefined,
        city: formData.city || undefined,
        country: formData.country,
        payment_terms_days: formData.payment_terms_days,
        bank_account: formData.bank_account || undefined,
        bank_name: formData.bank_name || undefined,
      }

      if (isEditing) {
        await supplierApi.update(supplier!.id, payload)
      } else {
        payload.company_id = companyId
        await supplierApi.create(payload)
      }
      onSuccess()
    } catch (err: any) {
      console.error(`Failed to ${isEditing ? 'update' : 'create'} supplier:`, err)
      setError(getErrorMessage(err, `Kunde inte ${isEditing ? 'uppdatera' : 'skapa'} leverantör`))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold">{isEditing ? 'Redigera leverantör' : 'Ny leverantör'}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Namn *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Org.nummer
              </label>
              <input
                type="text"
                value={formData.org_number}
                onChange={(e) => setFormData({ ...formData, org_number: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="XXXXXX-XXXX"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Kontaktperson
              </label>
              <input
                type="text"
                value={formData.contact_person}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                E-post
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Telefon
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Adress
              </label>
              <input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Postnummer
              </label>
              <input
                type="text"
                value={formData.postal_code}
                onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="123 45"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stad
              </label>
              <input
                type="text"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Land
              </label>
              <input
                type="text"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Betalningsvillkor (dagar)
              </label>
              <input
                type="number"
                value={formData.payment_terms_days}
                onChange={(e) => setFormData({ ...formData, payment_terms_days: parseInt(e.target.value) || 30 })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                min="0"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bankkontonummer
              </label>
              <input
                type="text"
                value={formData.bank_account}
                onChange={(e) => setFormData({ ...formData, bank_account: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bank
              </label>
              <input
                type="text"
                value={formData.bank_name}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Avbryt
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? (isEditing ? 'Uppdaterar...' : 'Skapar...') : (isEditing ? 'Uppdatera' : 'Skapa leverantör')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
