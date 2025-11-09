// Swedish bookkeeping types

export enum AccountType {
  ASSET = 'asset',
  EQUITY_LIABILITY = 'equity_liability',
  REVENUE = 'revenue',
  COST_GOODS = 'cost_goods',
  COST_LOCAL = 'cost_local',
  COST_OTHER = 'cost_other',
  COST_PERSONNEL = 'cost_personnel',
  COST_MISC = 'cost_misc',
}

export enum AccountingBasis {
  ACCRUAL = 'accrual',
  CASH = 'cash',
}

export interface Company {
  id: number
  name: string
  org_number: string
  fiscal_year_start: string
  fiscal_year_end: string
  accounting_basis: AccountingBasis
}

export interface Account {
  id: number
  company_id: number
  account_number: number
  name: string
  description?: string
  account_type: AccountType
  opening_balance: number
  current_balance: number
  active: boolean
  is_bas_account: boolean
}

export interface TransactionLine {
  id?: number
  verification_id?: number
  account_id: number
  account_number?: number
  account_name?: string
  debit: number
  credit: number
  description?: string
}

export interface Verification {
  id?: number
  company_id: number
  verification_number?: number
  series: string
  transaction_date: string
  registration_date?: string
  description: string
  locked?: boolean
  created_at?: string
  updated_at?: string
  transaction_lines: TransactionLine[]
  is_balanced?: boolean
  total_amount?: number
}

export interface VerificationListItem {
  id: number
  verification_number: number
  series: string
  transaction_date: string
  description: string
  total_amount: number
  locked: boolean
}

export interface BalanceSheet {
  company_id: number
  report_type: string
  assets: {
    accounts: Array<{ account_number: number; name: string; balance: number }>
    total: number
  }
  liabilities: {
    accounts: Array<{ account_number: number; name: string; balance: number }>
    total: number
  }
  equity: {
    accounts: Array<{ account_number: number; name: string; balance: number }>
    total: number
  }
  total_liabilities_and_equity: number
  balanced: boolean
}

export interface IncomeStatement {
  company_id: number
  report_type: string
  revenue: {
    accounts: Array<{ account_number: number; name: string; balance: number }>
    total: number
  }
  expenses: {
    accounts: Array<{ account_number: number; name: string; balance: number }>
    total: number
  }
  profit_loss: number
}
