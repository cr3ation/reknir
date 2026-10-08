# MCP Server Status & Roadmap

## Current State (2026-04-07)

### Implemented Tools

#### Companies (`tools/companies.py`)
- [x] `get_company_info` — get company details
- [x] `list_companies` — list all companies

#### Suppliers (`tools/suppliers.py`)
- [x] `find_supplier` — search by org number or name
- [x] `create_supplier` — create new supplier
- [x] `list_suppliers` — list all suppliers

#### Supplier Invoices (`tools/invoices.py`)
- [x] `create_supplier_invoice` — create draft invoice with lines
- [x] `register_invoice` — book invoice (create verifications)
- [x] `mark_invoice_paid` — mark as paid
- [x] `list_supplier_invoices` — list invoices with filters
- [x] `get_invoice_details` — full invoice with line items

#### Accounts (`tools/accounts.py`)
- [x] `search_accounts` — search by number/name/type
- [x] `list_expense_accounts` — list expense accounts grouped by category
- [x] `get_account_balance` — get single account balance
- [x] `list_accounts_by_type` — list accounts filtered by type

#### Verifications (`tools/verifications.py`)
- [x] `create_verification` — create manual verification with balanced lines
- [x] `list_verifications` — list verifications with filters
- [x] `get_verification` — get verification with transaction lines
- [x] `get_fiscal_year` — get current fiscal year

#### Reports (`tools/reports.py`)
- [x] `get_account_balances` — account balances
- [x] `get_trial_balance` — saldobalans
- [x] `get_income_statement` — resultatrapport
- [x] `get_balance_sheet` — balansrapport

### Tests (`tests/`)
- [x] `test_required_params.py` — verifies all required backend query params are sent (16 tests)
- [x] `test_tool_handlers.py` — smoke tests for each tool handler (14 tests)

---

## Known Issues Fixed (2026-04-07)

1. **Missing `fiscal_year_id`** — `list_accounts`, `get_account_balances`, and all 3 report endpoints were not sending the required `fiscal_year_id` parameter, causing 422 errors. Fixed: auto-fetch current fiscal year when not provided.

2. **Field name mismatch in invoices** — MCP tools used `invoice_number` and `lines`, but the backend expects `supplier_invoice_number` and `supplier_invoice_lines`. Fixed: handler now remaps fields before sending to API.

---

## Not Yet Implemented

### High Priority — Attachments
Backend supports file attachments on supplier invoices, verifications, and expenses. Currently no MCP tool to upload/list/download attachments.

- [ ] `upload_supplier_invoice_attachment` — POST `/{invoice_id}/attachments` (multipart file upload)
- [ ] `list_supplier_invoice_attachments` — GET `/{invoice_id}/attachments`
- [ ] `upload_verification_attachment` — POST `/{verification_id}/attachments`
- [ ] `list_verification_attachments` — GET `/{verification_id}/attachments`

### High Priority — Fiscal Year Management
Had to create the 2026 fiscal year and seed accounts manually via curl. The MCP should handle this.

- [ ] `create_fiscal_year` — POST `/api/fiscal-years/`
- [ ] `seed_accounts` — POST `/api/companies/{id}/seed-bas` (seed BAS chart of accounts)
- [ ] `list_fiscal_years` — GET `/api/fiscal-years/`

### Medium Priority — Expenses
Full expense workflow exists in backend but not exposed via MCP.

- [ ] `create_expense` — create expense report
- [ ] `submit_expense` — submit for approval
- [ ] `approve_expense` / `reject_expense`
- [ ] `book_expense` — create accounting entries
- [ ] `mark_expense_paid`
- [ ] `list_expenses`
- [ ] `upload_expense_attachment` — attach receipt

### Medium Priority — Customer Invoices (Outgoing)
Backend has full customer invoice support.

- [ ] `create_invoice` — create customer invoice
- [ ] `send_invoice` — send/book
- [ ] `mark_invoice_paid`
- [ ] `list_invoices`
- [ ] `get_invoice_pdf`

### Medium Priority — Additional Reports
- [ ] `get_general_ledger` — huvudbok
- [ ] `get_vat_report` — momsrapport
- [ ] `get_monthly_statistics` — monthly overview

### Low Priority — Admin/Setup
- [ ] `create_account` — add custom account to chart
- [ ] `update_account` — modify account
- [ ] `list_posting_templates` — reusable booking templates
- [ ] `execute_posting_template` — apply a template
- [ ] SIE4 import/export
- [ ] Customer CRUD
- [ ] Dashboard data
