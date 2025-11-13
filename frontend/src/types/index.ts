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

export enum VATReportingPeriod {
  MONTHLY = 'monthly',
  QUARTERLY = 'quarterly',
  YEARLY = 'yearly',
}

export interface Company {
  id: number
  name: string
  org_number: string
  fiscal_year_start: string
  fiscal_year_end: string
  accounting_basis: AccountingBasis
  vat_reporting_period: VATReportingPeriod
}

export interface FiscalYear {
  id: number
  company_id: number
  year: number
  label: string
  start_date: string
  end_date: string
  is_closed: boolean
  is_current: boolean
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

export interface GeneralLedgerEntry {
  transaction_date: string
  verification_id: number
  verification_series: string
  verification_number: number
  account_number: number
  account_name: string
  description: string
  debit: number
  credit: number
}

export interface GeneralLedger {
  company_id: number
  report_type: string
  start_date: string
  end_date: string
  entries: GeneralLedgerEntry[]
  total_debit: number
  total_credit: number
  entry_count: number
  balanced: boolean
}

// Invoice management types

export enum InvoiceStatus {
  DRAFT = 'draft',
  SENT = 'sent',
  PAID = 'paid',
  PARTIAL = 'partial',
  OVERDUE = 'overdue',
  CANCELLED = 'cancelled',
}

export interface Customer {
  id: number
  company_id: number
  name: string
  org_number?: string
  contact_person?: string
  email?: string
  phone?: string
  address?: string
  postal_code?: string
  city?: string
  country: string
  payment_terms_days: number
  active: boolean
}

export interface Supplier {
  id: number
  company_id: number
  name: string
  org_number?: string
  contact_person?: string
  email?: string
  phone?: string
  address?: string
  postal_code?: string
  city?: string
  country: string
  payment_terms_days: number
  bank_account?: string
  bank_name?: string
  active: boolean
}

export interface InvoiceLine {
  id?: number
  invoice_id?: number
  description: string
  quantity: number
  unit: string
  unit_price: number
  vat_rate: number
  account_id?: number
  net_amount?: number
  vat_amount?: number
  total_amount?: number
}

export interface Invoice {
  id: number
  company_id: number
  customer_id: number
  invoice_number: number
  invoice_series: string
  invoice_date: string
  due_date: string
  paid_date?: string
  reference?: string
  our_reference?: string
  total_amount: number
  vat_amount: number
  net_amount: number
  status: InvoiceStatus
  paid_amount: number
  notes?: string
  message?: string
  invoice_verification_id?: number
  payment_verification_id?: number
  pdf_path?: string
  created_at: string
  updated_at: string
  sent_at?: string
  invoice_lines: InvoiceLine[]
}

export interface InvoiceListItem {
  id: number
  invoice_number: number
  invoice_series: string
  invoice_date: string
  due_date: string
  customer_id: number
  customer_name: string
  total_amount: number
  status: InvoiceStatus
  paid_amount: number
}

export interface SupplierInvoice {
  id: number
  company_id: number
  supplier_id: number
  supplier_invoice_number: string
  our_invoice_number?: number
  invoice_date: string
  due_date: string
  paid_date?: string
  total_amount: number
  vat_amount: number
  net_amount: number
  status: InvoiceStatus
  paid_amount: number
  ocr_number?: string
  reference?: string
  notes?: string
  invoice_verification_id?: number
  payment_verification_id?: number
  attachment_path?: string
  created_at: string
  updated_at: string
  supplier_invoice_lines: InvoiceLine[]
}

export interface SupplierInvoiceListItem {
  id: number
  our_invoice_number?: number
  supplier_invoice_number: string
  invoice_date: string
  due_date: string
  supplier_id: number
  supplier_name: string
  total_amount: number
  status: InvoiceStatus
  paid_amount: number
}

// Default Accounts & SIE4

export enum DefaultAccountType {
  REVENUE_25 = 'revenue_25',
  REVENUE_12 = 'revenue_12',
  REVENUE_6 = 'revenue_6',
  REVENUE_0 = 'revenue_0',
  VAT_OUTGOING_25 = 'vat_outgoing_25',
  VAT_OUTGOING_12 = 'vat_outgoing_12',
  VAT_OUTGOING_6 = 'vat_outgoing_6',
  VAT_INCOMING_25 = 'vat_incoming_25',
  VAT_INCOMING_12 = 'vat_incoming_12',
  VAT_INCOMING_6 = 'vat_incoming_6',
  ACCOUNTS_RECEIVABLE = 'accounts_receivable',
  ACCOUNTS_PAYABLE = 'accounts_payable',
  EXPENSE_DEFAULT = 'expense_default',
}

export interface DefaultAccount {
  id: number
  company_id: number
  account_type: DefaultAccountType
  account_id: number
  account_number?: number
  account_name?: string
}

export interface SIE4ImportResponse {
  success: boolean
  message: string
  accounts_created: number
  accounts_updated: number
  verifications_created: number
  default_accounts_configured: number
}

export interface VATReport {
  company_id: number
  report_type: string
  start_date: string | null
  end_date: string | null
  outgoing_vat: {
    accounts: Array<{ account_number: number; name: string; amount: number }>
    total: number
  }
  incoming_vat: {
    accounts: Array<{ account_number: number; name: string; amount: number }>
    total: number
  }
  net_vat: number
  pay_or_refund: 'pay' | 'refund' | 'zero'
  skv_3800?: {
    outgoing_25: {
      vat: number
      sales: number
      box_sales: string
      box_vat: string
    }
    outgoing_12: {
      vat: number
      sales: number
      box_sales: string
      box_vat: string
    }
    outgoing_6: {
      vat: number
      sales: number
      box_sales: string
      box_vat: string
    }
    incoming_total: {
      vat: number
      box: string
    }
    net_vat: {
      amount: number
      box: string
    }
  }
  debug_info?: {
    total_vat_accounts_found: number
    outgoing_vat_accounts: Array<{ number: number; name: string }>
    incoming_vat_accounts: Array<{ number: number; name: string }>
    transaction_groups_found: number
    accounts_with_transactions: Array<{
      number: number
      name: string
      debit: number
      credit: number
    }>
    verifications: Array<{
      id: number
      verification_number: number
      series: string
      transaction_date: string
      description: string
      transaction_lines: Array<{
        account_number: number
        account_name: string
        debit: number
        credit: number
        is_vat_account: boolean
      }>
    }>
  }
}

export interface VATPeriod {
  name: string
  start_date: string
  end_date: string
  period_type: 'monthly' | 'quarterly' | 'yearly'
}

export interface VATPeriodsResponse {
  company_id: number
  year: number
  reporting_period: string
  periods: VATPeriod[]
}

// Expenses

export enum ExpenseStatus {
  DRAFT = 'draft',
  SUBMITTED = 'submitted',
  APPROVED = 'approved',
  PAID = 'paid',
  REJECTED = 'rejected',
}

export interface Expense {
  id: number
  company_id: number
  employee_name: string
  expense_date: string
  description: string
  amount: number
  vat_amount: number
  expense_account_id?: number
  vat_account_id?: number
  receipt_filename?: string
  status: ExpenseStatus
  approved_date?: string
  paid_date?: string
  verification_id?: number
  created_at: string
  updated_at: string
}
