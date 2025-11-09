import axios from 'axios'
import type {
  Company,
  Account,
  Verification,
  VerificationListItem,
  BalanceSheet,
  IncomeStatement,
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

export default api
