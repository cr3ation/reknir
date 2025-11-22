import axios from 'axios'
import type {
  Company,
  FiscalYear,
  Account,
  Verification,
  VerificationListItem,
  BalanceSheet,
  IncomeStatement,
  GeneralLedger,
  Customer,
  Supplier,
  Invoice,
  InvoiceListItem,
  SupplierInvoice,
  SupplierInvoiceListItem,
  DefaultAccount,
  SIE4ImportResponse,
  VATReport,
  VATPeriodsResponse,
  Expense,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle 401 unauthorized responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token is invalid or expired, clear it
      localStorage.removeItem('auth_token')
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Companies
export const companyApi = {
  list: () => api.get<Company[]>('/companies/'),
  get: (id: number) => api.get<Company>(`/companies/${id}`),
  create: (data: Omit<Company, 'id'>) => api.post<Company>('/companies/', data),
  update: (id: number, data: Partial<Company>) => api.patch<Company>(`/companies/${id}`, data),
  delete: (id: number) => api.delete(`/companies/${id}`),
  initializeDefaults: (id: number) =>
    api.post<{ message: string; default_accounts_configured: number }>(
      `/companies/${id}/initialize-defaults`
    ),
}

// Fiscal Years
export const fiscalYearApi = {
  list: (companyId: number) => api.get<FiscalYear[]>('/fiscal-years/', { params: { company_id: companyId } }),
  get: (id: number) => api.get<FiscalYear>(`/fiscal-years/${id}`),
  getCurrent: (companyId: number) => api.get<FiscalYear | null>(`/fiscal-years/current/by-company/${companyId}`),
  create: (data: Omit<FiscalYear, 'id' | 'is_current'>) => api.post<FiscalYear>('/fiscal-years/', data),
  update: (id: number, data: Partial<FiscalYear>) => api.patch<FiscalYear>(`/fiscal-years/${id}`, data),
  delete: (id: number) => api.delete(`/fiscal-years/${id}`),
  assignVerifications: (id: number) => api.post<{ message: string; verifications_assigned: number }>(`/fiscal-years/${id}/assign-verifications`),
}

// Accounts
export const accountApi = {
  list: (companyId: number, params?: { account_type?: string; active_only?: boolean }) =>
    api.get<Account[]>('/accounts/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Account>(`/accounts/${id}`),
  create: (data: Omit<Account, 'id' | 'current_balance'>) =>
    api.post<Account>('/accounts/', data),
  update: (id: number, data: Partial<Account>) => api.patch<Account>(`/accounts/${id}`, data),
  getLedger: (accountId: number, params?: { start_date?: string; end_date?: string }) =>
    api.get(`/accounts/${accountId}/ledger`, { params }),
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
    api.get<VerificationListItem[]>('/verifications/', {
      params: { company_id: companyId, ...params },
    }),
  get: (id: number) => api.get<Verification>(`/verifications/${id}`),
  create: (data: Omit<Verification, 'id'>) => api.post<Verification>('/verifications/', data),
  update: (id: number, data: Partial<Verification>) =>
    api.patch<Verification>(`/verifications/${id}`, data),
  delete: (id: number) => api.delete(`/verifications/${id}`),
}

// Reports
export const reportApi = {
  balanceSheet: (companyId: number) =>
    api.get<BalanceSheet>('/reports/balance-sheet', { params: { company_id: companyId } }),
  incomeStatement: (companyId: number) =>
    api.get<IncomeStatement>('/reports/income-statement', {
      params: { company_id: companyId },
    }),
  generalLedger: (companyId: number, fiscalYearId?: number, startDate?: string, endDate?: string, accountNumbers?: string) =>
    api.get<GeneralLedger>('/reports/general-ledger', {
      params: {
        company_id: companyId,
        fiscal_year_id: fiscalYearId,
        start_date: startDate,
        end_date: endDate,
        account_numbers: accountNumbers,
      },
    }),
  vatReport: (companyId: number, startDate?: string, endDate?: string, excludeVatSettlements?: boolean) =>
    api.get<VATReport>('/reports/vat-report', {
      params: {
        company_id: companyId,
        start_date: startDate,
        end_date: endDate,
        exclude_vat_settlements: excludeVatSettlements,
      },
    }),
  vatPeriods: (companyId: number, year: number) =>
    api.get<VATPeriodsResponse>('/reports/vat-periods', {
      params: { company_id: companyId, year },
    }),
}

// Customers
export const customerApi = {
  list: (companyId: number, activeOnly = true) =>
    api.get<Customer[]>('/customers/', { params: { company_id: companyId, active_only: activeOnly } }),
  get: (id: number) => api.get<Customer>(`/customers/${id}`),
  create: (data: Omit<Customer, 'id' | 'active'>) => api.post<Customer>('/customers/', data),
  update: (id: number, data: Partial<Customer>) => api.patch<Customer>(`/customers/${id}`, data),
  delete: (id: number) => api.delete(`/customers/${id}`),
}

// Suppliers
export const supplierApi = {
  list: (companyId: number, activeOnly = true) =>
    api.get<Supplier[]>('/suppliers/', { params: { company_id: companyId, active_only: activeOnly } }),
  get: (id: number) => api.get<Supplier>(`/suppliers/${id}`),
  create: (data: Omit<Supplier, 'id' | 'active'>) => api.post<Supplier>('/suppliers/', data),
  update: (id: number, data: Partial<Supplier>) => api.patch<Supplier>(`/suppliers/${id}`, data),
  delete: (id: number) => api.delete(`/suppliers/${id}`),
}

// Invoices (Outgoing)
export const invoiceApi = {
  list: (companyId: number, params?: { customer_id?: number; status?: string }) =>
    api.get<InvoiceListItem[]>('/invoices/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Invoice>(`/invoices/${id}`),
  create: (data: any) => api.post<Invoice>('/invoices/', data),
  update: (id: number, data: Partial<Invoice>) => api.patch<Invoice>(`/invoices/${id}`, data),
  send: (id: number) => api.post<Invoice>(`/invoices/${id}/send`),
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number; bank_account_id?: number }) =>
    api.post<Invoice>(`/invoices/${id}/mark-paid`, data),
  delete: (id: number) => api.delete(`/invoices/${id}`),
}

// Supplier Invoices (Incoming)
export const supplierInvoiceApi = {
  list: (companyId: number, params?: { supplier_id?: number; status?: string }) =>
    api.get<SupplierInvoiceListItem[]>('/supplier-invoices/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<SupplierInvoice>(`/supplier-invoices/${id}`),
  create: (data: any) => api.post<SupplierInvoice>('/supplier-invoices/', data),
  update: (id: number, data: Partial<SupplierInvoice>) =>
    api.patch<SupplierInvoice>(`/supplier-invoices/${id}`, data),
  register: (id: number) => api.post<SupplierInvoice>(`/supplier-invoices/${id}/register`),
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number; bank_account_id?: number }) =>
    api.post<SupplierInvoice>(`/supplier-invoices/${id}/mark-paid`, data),
  delete: (id: number) => api.delete(`/supplier-invoices/${id}`),
  uploadAttachment: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<SupplierInvoice>(`/supplier-invoices/${id}/upload-attachment`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadAttachment: (id: number) => api.get(`/supplier-invoices/${id}/attachment`, { responseType: 'blob' }),
  deleteAttachment: (id: number) => api.delete<SupplierInvoice>(`/supplier-invoices/${id}/attachment`),
}

// SIE4 Import/Export
export const sie4Api = {
  import: (companyId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<SIE4ImportResponse>(`/sie4/import/${companyId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
  export: (companyId: number, includeVerifications: boolean = true) => {
    return api.get(`/sie4/export/${companyId}`, {
      params: { include_verifications: includeVerifications },
      responseType: 'blob',
    })
  },
}

// Default Accounts
export const defaultAccountApi = {
  list: (companyId: number) =>
    api.get<DefaultAccount[]>('/default-accounts/', { params: { company_id: companyId } }),
  update: (companyId: number, accountType: string, accountId: number) =>
    api.post<DefaultAccount>('/default-accounts/', {
      company_id: companyId,
      account_type: accountType,
      account_id: accountId,
    }),
}

// Expenses
export const expenseApi = {
  list: (companyId: number, params?: { status_filter?: string; employee_name?: string; start_date?: string; end_date?: string }) =>
    api.get<Expense[]>('/expenses/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Expense>(`/expenses/${id}`),
  create: (data: any) => api.post<Expense>('/expenses/', data),
  update: (id: number, data: Partial<Expense>) => api.patch<Expense>(`/expenses/${id}`, data),
  delete: (id: number) => api.delete(`/expenses/${id}`),
  submit: (id: number) => api.post<Expense>(`/expenses/${id}/submit`),
  approve: (id: number) => api.post<Expense>(`/expenses/${id}/approve`),
  reject: (id: number) => api.post<Expense>(`/expenses/${id}/reject`),
  book: (id: number, employeePayableAccountId: number) =>
    api.post<Expense>(`/expenses/${id}/book`, null, { params: { employee_payable_account_id: employeePayableAccountId } }),
  markPaid: (id: number, paidDate: string, bankAccountId: number) =>
    api.post<Expense>(`/expenses/${id}/mark-paid`, null, { params: { paid_date: paidDate, bank_account_id: bankAccountId } }),
  uploadReceipt: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<Expense>(`/expenses/${id}/upload-receipt`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadReceipt: (id: number) => api.get(`/expenses/${id}/receipt`, { responseType: 'blob' }),
  deleteReceipt: (id: number) => api.delete<Expense>(`/expenses/${id}/receipt`),
}

export default api
