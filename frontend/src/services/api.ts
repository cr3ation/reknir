import axios from 'axios'
import type {
  Company,
  Account,
  Verification,
  VerificationListItem,
  BalanceSheet,
  IncomeStatement,
  Customer,
  Supplier,
  Invoice,
  InvoiceListItem,
  SupplierInvoice,
  SupplierInvoiceListItem,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Companies
export const companyApi = {
  list: () => api.get<Company[]>('/api/companies/'),
  get: (id: number) => api.get<Company>(`/api/companies/${id}`),
  create: (data: Omit<Company, 'id'>) => api.post<Company>('/api/companies/', data),
  update: (id: number, data: Partial<Company>) => api.patch<Company>(`/api/companies/${id}`, data),
  delete: (id: number) => api.delete(`/api/companies/${id}`),
}

// Accounts
export const accountApi = {
  list: (companyId: number, params?: { account_type?: string; active_only?: boolean }) =>
    api.get<Account[]>('/api/accounts/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Account>(`/api/accounts/${id}`),
  create: (data: Omit<Account, 'id' | 'current_balance'>) =>
    api.post<Account>('/api/accounts/', data),
  update: (id: number, data: Partial<Account>) => api.patch<Account>(`/api/accounts/${id}`, data),
}

// Verifications
export const verificationApi = {
  list: (
    companyId: number,
    params?: {
      start_date?: string
      end_date?: string
      series?: string
      limit?: number
      offset?: number
    }
  ) =>
    api.get<VerificationListItem[]>('/api/verifications/', {
      params: { company_id: companyId, ...params },
    }),
  get: (id: number) => api.get<Verification>(`/api/verifications/${id}`),
  create: (data: Omit<Verification, 'id'>) => api.post<Verification>('/api/verifications/', data),
  update: (id: number, data: Partial<Verification>) =>
    api.patch<Verification>(`/api/verifications/${id}`, data),
  delete: (id: number) => api.delete(`/api/verifications/${id}`),
}

// Reports
export const reportApi = {
  balanceSheet: (companyId: number) =>
    api.get<BalanceSheet>('/api/reports/balance-sheet', { params: { company_id: companyId } }),
  incomeStatement: (companyId: number) =>
    api.get<IncomeStatement>('/api/reports/income-statement', {
      params: { company_id: companyId },
    }),
}

// Customers
export const customerApi = {
  list: (companyId: number, activeOnly = true) =>
    api.get<Customer[]>('/api/customers/', { params: { company_id: companyId, active_only: activeOnly } }),
  get: (id: number) => api.get<Customer>(`/api/customers/${id}`),
  create: (data: Omit<Customer, 'id' | 'active'>) => api.post<Customer>('/api/customers/', data),
  update: (id: number, data: Partial<Customer>) => api.patch<Customer>(`/api/customers/${id}`, data),
  delete: (id: number) => api.delete(`/api/customers/${id}`),
}

// Suppliers
export const supplierApi = {
  list: (companyId: number, activeOnly = true) =>
    api.get<Supplier[]>('/api/suppliers/', { params: { company_id: companyId, active_only: activeOnly } }),
  get: (id: number) => api.get<Supplier>(`/api/suppliers/${id}`),
  create: (data: Omit<Supplier, 'id' | 'active'>) => api.post<Supplier>('/api/suppliers/', data),
  update: (id: number, data: Partial<Supplier>) => api.patch<Supplier>(`/api/suppliers/${id}`, data),
  delete: (id: number) => api.delete(`/api/suppliers/${id}`),
}

// Invoices (Outgoing)
export const invoiceApi = {
  list: (companyId: number, params?: { customer_id?: number; status?: string }) =>
    api.get<InvoiceListItem[]>('/api/invoices/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Invoice>(`/api/invoices/${id}`),
  create: (data: any) => api.post<Invoice>('/api/invoices/', data),
  update: (id: number, data: Partial<Invoice>) => api.patch<Invoice>(`/api/invoices/${id}`, data),
  send: (id: number) => api.post<Invoice>(`/api/invoices/${id}/send`),
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number }) =>
    api.post<Invoice>(`/api/invoices/${id}/mark-paid`, data),
  delete: (id: number) => api.delete(`/api/invoices/${id}`),
}

// Supplier Invoices (Incoming)
export const supplierInvoiceApi = {
  list: (companyId: number, params?: { supplier_id?: number; status?: string }) =>
    api.get<SupplierInvoiceListItem[]>('/api/supplier-invoices/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<SupplierInvoice>(`/api/supplier-invoices/${id}`),
  create: (data: any) => api.post<SupplierInvoice>('/api/supplier-invoices/', data),
  update: (id: number, data: Partial<SupplierInvoice>) =>
    api.patch<SupplierInvoice>(`/api/supplier-invoices/${id}`, data),
  register: (id: number) => api.post<SupplierInvoice>(`/api/supplier-invoices/${id}/register`),
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number }) =>
    api.post<SupplierInvoice>(`/api/supplier-invoices/${id}/mark-paid`, data),
  delete: (id: number) => api.delete(`/api/supplier-invoices/${id}`),
}

export default api
