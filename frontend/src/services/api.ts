import axios from 'axios'
import type {
  Company,
  FiscalYear,
  Account,
  Verification,
  VerificationListItem,
  PostingTemplate,
  PostingTemplateListItem,
  TemplateExecutionRequest,
  TemplateExecutionResult,
  BalanceSheet,
  IncomeStatement,
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
  MonthlyStatistics,
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
  initializeDefaults: (id: number) =>
    api.post<{ message: string; default_accounts_configured: number }>(
      `/api/companies/${id}/initialize-defaults`
    ),
  getBasAccounts: () => api.get<{ version: string; description: string; accounts: any[] }>('/api/companies/bas-accounts'),
  uploadLogo: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<Company>(`/api/companies/${id}/logo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getLogo: (id: number) => `${API_BASE_URL}/api/companies/${id}/logo`,
  deleteLogo: (id: number) => api.delete<Company>(`/api/companies/${id}/logo`),
}

// Fiscal Years
export const fiscalYearApi = {
  list: (companyId: number) => api.get<FiscalYear[]>('/api/fiscal-years/', { params: { company_id: companyId } }),
  get: (id: number) => api.get<FiscalYear>(`/api/fiscal-years/${id}`),
  getCurrent: (companyId: number) => api.get<FiscalYear | null>(`/api/fiscal-years/current/by-company/${companyId}`),
  create: (data: Omit<FiscalYear, 'id' | 'is_current'>) => api.post<FiscalYear>('/api/fiscal-years/', data),
  update: (id: number, data: Partial<FiscalYear>) => api.patch<FiscalYear>(`/api/fiscal-years/${id}`, data),
  delete: (id: number) => api.delete(`/api/fiscal-years/${id}`),
  assignVerifications: (id: number) => api.post<{ message: string; verifications_assigned: number }>(`/api/fiscal-years/${id}/assign-verifications`),
  copyChartOfAccounts: (fiscalYearId: number, sourceFiscalYearId?: number) =>
    api.post<{
      message: string;
      source_fiscal_year_id: number;
      source_fiscal_year_label: string;
      target_fiscal_year_id: number;
      target_fiscal_year_label: string;
      accounts_copied: number;
    }>(`/api/fiscal-years/${fiscalYearId}/copy-chart-of-accounts`, null, {
      params: sourceFiscalYearId ? { source_fiscal_year_id: sourceFiscalYearId } : undefined,
    }),
}

// Accounts
export const accountApi = {
  list: (companyId: number, fiscalYearId: number, params?: { account_type?: string; active_only?: boolean }) =>
    api.get<Account[]>('/api/accounts/', { params: { company_id: companyId, fiscal_year_id: fiscalYearId, ...params } }),
  get: (id: number) => api.get<Account>(`/api/accounts/${id}`),
  create: (data: Omit<Account, 'id' | 'current_balance'>) =>
    api.post<Account>('/api/accounts/', data),
  update: (id: number, data: Partial<Account>) => api.patch<Account>(`/api/accounts/${id}`, data),
  delete: (id: number) => api.delete(`/api/accounts/${id}`),
  getLedger: (accountId: number, params?: { start_date?: string; end_date?: string }) =>
    api.get(`/api/accounts/${accountId}/ledger`, { params }),
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

// Posting Templates
export const postingTemplateApi = {
  list: (companyId: number, params?: { skip?: number; limit?: number }) =>
    api.get<PostingTemplateListItem[]>('/api/posting-templates/', {
      params: { company_id: companyId, ...params },
    }),
  get: (id: number) => api.get<PostingTemplate>(`/api/posting-templates/${id}`),
  create: (data: Omit<PostingTemplate, 'id' | 'created_at' | 'updated_at'>) =>
    api.post<PostingTemplate>('/api/posting-templates/', data),
  update: (id: number, data: Partial<PostingTemplate>) =>
    api.put<PostingTemplate>(`/api/posting-templates/${id}`, data),
  delete: (id: number) => api.delete(`/api/posting-templates/${id}`),
  execute: (id: number, request: TemplateExecutionRequest) =>
    api.post<TemplateExecutionResult>(`/api/posting-templates/${id}/execute`, request),
  reorder: (companyId: number, templateOrders: { id: number; sort_order: number }[]) =>
    api.patch(`/api/posting-templates/reorder?company_id=${companyId}`, templateOrders),
}

// Reports
export const reportApi = {
  balanceSheet: (companyId: number, fiscalYearId: number) =>
    api.get<BalanceSheet>('/api/reports/balance-sheet', { params: { company_id: companyId, fiscal_year_id: fiscalYearId } }),
  incomeStatement: (companyId: number, fiscalYearId: number) =>
    api.get<IncomeStatement>('/api/reports/income-statement', {
      params: { company_id: companyId, fiscal_year_id: fiscalYearId },
    }),
  vatReport: (companyId: number, fiscalYearId: number, startDate?: string, endDate?: string, excludeVatSettlements?: boolean) =>
    api.get<VATReport>('/api/reports/vat-report', {
      params: {
        company_id: companyId,
        fiscal_year_id: fiscalYearId,
        start_date: startDate,
        end_date: endDate,
        exclude_vat_settlements: excludeVatSettlements,
      },
    }),
  vatPeriods: (companyId: number, fiscalYearId: number, year: number) =>
    api.get<VATPeriodsResponse>('/api/reports/vat-periods', {
      params: { company_id: companyId, fiscal_year_id: fiscalYearId, year },
    }),
  monthlyStatistics: (companyId: number, fiscalYearId: number, year: number) =>
    api.get<MonthlyStatistics>('/api/reports/monthly-statistics', {
      params: { company_id: companyId, fiscal_year_id: fiscalYearId, year },
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
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number; bank_account_id?: number }) =>
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
  markPaid: (id: number, data: { paid_date: string; paid_amount?: number; bank_account_id?: number }) =>
    api.post<SupplierInvoice>(`/api/supplier-invoices/${id}/mark-paid`, data),
  delete: (id: number) => api.delete(`/api/supplier-invoices/${id}`),
  downloadAttachment: (id: number) => api.get(`/api/supplier-invoices/${id}/attachment`, { responseType: 'blob' }),
  deleteAttachment: (id: number) => api.delete<SupplierInvoice>(`/api/supplier-invoices/${id}/attachment`),
}

// SIE4 Import/Export
export const sie4Api = {
  import: (companyId: number, fiscalYearId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<SIE4ImportResponse>(`/api/sie4/import/${companyId}`, formData, {
      params: { fiscal_year_id: fiscalYearId },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
  export: (companyId: number, fiscalYearId: number, includeVerifications: boolean = true) => {
    return api.get(`/api/sie4/export/${companyId}`, {
      params: { fiscal_year_id: fiscalYearId, include_verifications: includeVerifications },
      responseType: 'blob',
    })
  },
}

// Default Accounts
export const defaultAccountApi = {
  list: (companyId: number) =>
    api.get<DefaultAccount[]>('/api/default-accounts/', { params: { company_id: companyId } }),
  update: (companyId: number, accountType: string, accountId: number) =>
    api.post<DefaultAccount>('/api/default-accounts/', {
      company_id: companyId,
      account_type: accountType,
      account_id: accountId,
    }),
}

// Expenses
export const expenseApi = {
  list: (companyId: number, params?: { status_filter?: string; employee_name?: string; start_date?: string; end_date?: string }) =>
    api.get<Expense[]>('/api/expenses/', { params: { company_id: companyId, ...params } }),
  get: (id: number) => api.get<Expense>(`/api/expenses/${id}`),
  create: (data: any) => api.post<Expense>('/api/expenses/', data),
  update: (id: number, data: Partial<Expense>) => api.patch<Expense>(`/api/expenses/${id}`, data),
  delete: (id: number) => api.delete(`/api/expenses/${id}`),
  submit: (id: number) => api.post<Expense>(`/api/expenses/${id}/submit`),
  approve: (id: number) => api.post<Expense>(`/api/expenses/${id}/approve`),
  reject: (id: number) => api.post<Expense>(`/api/expenses/${id}/reject`),
  book: (id: number, employeePayableAccountId: number) =>
    api.post<Expense>(`/api/expenses/${id}/book`, null, { params: { employee_payable_account_id: employeePayableAccountId } }),
  markPaid: (id: number, paidDate: string, bankAccountId: number) =>
    api.post<Expense>(`/api/expenses/${id}/mark-paid`, null, { params: { paid_date: paidDate, bank_account_id: bankAccountId } }),
  uploadReceipt: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<Expense>(`/api/expenses/${id}/upload-receipt`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadReceipt: (id: number) => api.get(`/api/expenses/${id}/receipt`, { responseType: 'blob' }),
  deleteReceipt: (id: number) => api.delete<Expense>(`/api/expenses/${id}/receipt`),
}

export default api
